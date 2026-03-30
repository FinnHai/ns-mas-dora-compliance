"""TTP Generator Agent: AttackSketch → TTPScenario."""
import json
import logging
import re

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.config_loader import get_prompt
from app.models.ns_mas_schemas import (
    AttackSketch,
    CorrectionHint,
    PhaseSteps,
    TTPScenario,
    TTPStep,
)
from app.rag.retriever import TechniqueRetriever
from app.rag.reranker import rerank
from app.services.neo4j_connector import Neo4jService

logger = logging.getLogger(__name__)

PHASE_ORDER = {"in": 0, "through": 1, "out": 2}


def _create_llm():
    """LLM mit temperature=0 für Reproduzierbarkeit (DR4)."""
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=settings.llm_model or "claude-3-5-sonnet-20241022",
                api_key=settings.anthropic_api_key,
                temperature=settings.llm_temperature,
            )
        except ImportError:
            pass
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
    )


def _build_technique_context(neo4j: Neo4jService) -> str:
    """Baut Kontext-String aus KG-Techniken (statisch, ohne RAG)."""
    techniques = neo4j.get_all_techniques()
    if not techniques:
        return "Keine Techniken im Graph. Nutze Standard MITRE ATT&CK IDs (z.B. T1566, T1059, T1078)."
    lines = []
    for t in techniques[:80]:  # Begrenzen für Kontext
        tac = ", ".join(t.get("tactic_ids", [])[:3])
        lines.append(f"- {t['id']}: {t.get('name', '')} ({tac})")
    return "\n".join(lines)


def _build_rag_context(attack_sketch: AttackSketch) -> str:
    """RAG: BM25 Top-40 → Re-Ranker Top-3 pro Phase."""
    retriever = TechniqueRetriever(top_k=40)
    lines = []
    for idx, phase in enumerate(attack_sketch.phases):
        query = f"Techniques for {phase.phase} phase {attack_sketch.threat_actor} " + " ".join(phase.high_level_goals)
        docs = retriever.retrieve(query)
        # Validierungsplan Punkt 4: RAG-Kontext-Logging (einmal pro Aufruf)
        if idx == 0:
            corpus_size = len(retriever._corpus) if retriever._corpus else 0
            top3_preview = [
                f"{d.get('id', '')}: {(d.get('name', '') or '')[:50]}"
                for d in docs[:3]
            ]
            logger.info(
                "RAG corpus size: %d | Top-3 retrieved: %s",
                corpus_size,
                top3_preview,
            )
        top = rerank(docs, query, top_k=3)
        for t in top:
            tac = ", ".join(t.get("tactic_ids", [])[:3])
            lines.append(f"- [{phase.phase}] {t['id']}: {t.get('name', '')} ({tac})")
    return "\n".join(lines) if lines else _build_technique_context(Neo4jService())


def _parse_ttp_scenario(content: str, sketch: AttackSketch) -> TTPScenario | None:
    """Parst JSON zu TTPScenario."""
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        phases = []
        step_id = 1
        for p in data.get("phases", []):
            steps = []
            for s in p.get("steps", []):
                steps.append(TTPStep(
                    step_id=step_id,
                    technique_id=s.get("technique_id", "T0000"),
                    technique_name=s.get("technique_name", ""),
                    tactic=s.get("tactic", ""),
                    description=s.get("description", ""),
                    cve_references=s.get("cve_references", []),
                    temporal_relation_to_next=s.get("temporal_relation_to_next"),
                ))
                step_id += 1
            phases.append(PhaseSteps(
                phase=p.get("phase", "through"),
                steps=steps,
            ))
        return TTPScenario(
            scenario_id=data.get("scenario_id", sketch.scenario_id),
            target_organization=data.get("target_organization", sketch.target_organization),
            threat_actor=data.get("threat_actor", sketch.threat_actor),
            phases=phases,
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Parse TTPScenario: %s", e)
        return None


def _sort_phases(ttp: TTPScenario) -> TTPScenario:
    """Prozedurale Neuordnung: in → through → out."""
    sorted_phases = sorted(ttp.phases, key=lambda p: PHASE_ORDER.get(p.phase, 1))
    return TTPScenario(
        scenario_id=ttp.scenario_id,
        target_organization=ttp.target_organization,
        threat_actor=ttp.threat_actor,
        phases=sorted_phases,
    )


async def run_ttp_generator(
    attack_sketch: AttackSketch,
    correction_hints: list[CorrectionHint] | None = None,
    use_rag: bool = True,
    use_actor_context: bool = True,
) -> TTPScenario:
    """
    Generiert TTPScenario aus AttackSketch.
    Mit RAG: BM25 + Re-Ranker für phasespezifischen Kontext.
    Ohne RAG: statischer KG-Kontext.
    use_actor_context=False: Kein Akteursprofil aus KG (Baseline-Modus).
    """
    if use_rag:
        try:
            technique_context = _build_rag_context(attack_sketch)
        except Exception as e:
            logger.warning("RAG fehlgeschlagen, Fallback statisch: %s", e)
            technique_context = _build_technique_context(Neo4jService())
    else:
        technique_context = _build_technique_context(Neo4jService())

    # Akteursspezifische Techniken aus KG für Prompt-Kontext (Baseline: leer)
    if not use_actor_context:
        actor_context = ""
    else:
        neo4j = Neo4jService()
        actor_techniques = neo4j.get_techniques_for_group(attack_sketch.threat_actor)

        if actor_techniques:
            techniques_by_tactic: dict[str, list[str]] = {}
            for t in actor_techniques:
                tactic = t.get("tactic") or "unknown"
                if tactic not in techniques_by_tactic:
                    techniques_by_tactic[tactic] = []
                techniques_by_tactic[tactic].append(f"{t['id']} ({t['name']})")

            actor_context = f"""
BEDROHUNGSAKTEUR-PROFIL aus der MITRE ATT&CK-Datenbank:
Der Akteur {attack_sketch.threat_actor} nutzt historisch folgende Techniken:

"""
            for tactic, techs in techniques_by_tactic.items():
                actor_context += f"  {tactic}: {', '.join(techs)}\n"

            actor_context += """
ANWEISUNG: Wähle Techniken PRIMÄR aus dieser Liste.
Verwende bevorzugt Sub-Techniken (z.B. T1566.001 statt T1566) für höhere Spezifität.
Wenn du von der Liste abweichst, begründe warum im description-Feld.
"""
        else:
            actor_context = f"""
HINWEIS: Für den Akteur {attack_sketch.threat_actor} liegen keine spezifischen Technik-Daten im Knowledge Graph vor.
Wähle Techniken basierend auf deinem allgemeinen Wissen über diesen Akteur.
"""

    hints_str = ""
    if correction_hints:
        hints_str = "\n".join(
            f"- Schritt {h.step_id} ({h.technique_id}): {h.message}"
            + (f" → Vorschlag: {h.suggested_technique_id}" if h.suggested_technique_id else "")
            for h in correction_hints
        )

    template = get_prompt("ttp_generator")
    if not template:
        template = (
            "Generiere TTP-Schritte für die Angriffsskizze.\n"
            "Angriffsskizze: {attack_sketch_json}\n"
            "Bedrohungsakteur-Profil: {actor_context}\n"
            "Techniken: {technique_context}\n"
            "Korrekturhinweise: {correction_hints}\n"
            "Antworte als JSON mit phases: [{phase, steps: [{step_id, technique_id, technique_name, tactic, description, cve_references}]}]"
        )

    prompt = template.format(
        attack_sketch_json=attack_sketch.model_dump_json(indent=2),
        actor_context=actor_context,
        technique_context=technique_context,
        correction_hints=hints_str or "(keine)",
    )

    has_llm = bool(settings.openai_api_key) or (
        settings.llm_provider == "anthropic" and settings.anthropic_api_key
    )

    if has_llm:
        try:
            llm = _create_llm()
            # Validierungsplan Punkt 5: Temperature-Verifikation
            temp = getattr(llm, "temperature", getattr(llm, "model_kwargs", {}).get("temperature", "N/A"))
            logger.info("LLM temperature: %s (config: %s)", temp, settings.llm_temperature)
            structured = llm.with_structured_output(TTPScenario)
            result = await structured.ainvoke([HumanMessage(content=prompt)])
            if result:
                return _sort_phases(result)
        except Exception as e:
            logger.warning("TTP Generator structured output: %s", e)

        try:
            llm = _create_llm()
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            result = _parse_ttp_scenario(content, attack_sketch)
            if result:
                return _sort_phases(result)
        except Exception as e:
            logger.warning("TTP Generator fallback: %s", e)

    # Fallback: Minimales TTPScenario
    return _sort_phases(TTPScenario(
        scenario_id=attack_sketch.scenario_id,
        target_organization=attack_sketch.target_organization,
        threat_actor=attack_sketch.threat_actor,
        phases=[
            PhaseSteps(phase="in", steps=[
                TTPStep(step_id=1, technique_id="T1566", technique_name="Phishing", tactic="initial-access", description="Phishing-E-Mail"),
            ]),
            PhaseSteps(phase="through", steps=[
                TTPStep(step_id=2, technique_id="T1059", technique_name="Command and Scripting Interpreter", tactic="execution", description="PowerShell-Ausführung"),
            ]),
            PhaseSteps(phase="out", steps=[
                TTPStep(step_id=3, technique_id="T1048", technique_name="Exfiltration Over Alternative Protocol", tactic="exfiltration", description="Datenexfiltration"),
            ]),
        ],
    ))
