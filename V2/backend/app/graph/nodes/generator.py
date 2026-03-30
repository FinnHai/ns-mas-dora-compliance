"""Generator-Node für MSEL-Schritt-Generierung via LLM.

Generiert kreativ einen neuen MSEL-Schritt. Keine Validierung – der Validator fängt Fehler.
TIBER-EU Red Team Operator mit Szenario-X, Phase-OUT und Leg-Up-Unterstützung.
"""
import json
import logging
import re
import uuid

logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.graph.state import ScenarioState
from app.models.enums import LegUpStatus, LegUpType, Phase, SecurityGoal, StepStatus
from app.models.msel import LegUp, MSELItem
from app.models.strategy import CriticalFunction, ThreatActorProfile
from app.schemas.graph import LegUpDraft, MSELItemDraft


def _build_system_prompt(state: ScenarioState) -> str:
    """Baut den TIBER-EU System-Prompt dynamisch aus State."""
    parts: list[str] = []
    config = state.get("agent_config")

    # Custom System-Prompt überschreibt Standard
    if config and getattr(config, "generator_system_prompt", None):
        return config.generator_system_prompt or ""

    # 1. Rollen-Definition
    parts.append("Du bist ein TIBER-EU Red Team Operator.")

    # 2. Szenario-X (f-strings)
    scenario_meta = state.get("scenario_metadata")
    is_scenario_x = scenario_meta.is_scenario_x if scenario_meta else False
    if is_scenario_x:
        parts.append(
            "Szenario X: Du darfst kreative, futuristische Techniken nutzen (Non-Threat-Led)."
        )
    else:
        parts.append(
            "Szenario: Du musst dich STRIKT an die known_techniques des Threat Actors halten."
        )

    # 3. Phase-OUT-Regeln
    parts.append(
        """Phase OUT: Wenn du einen Schritt in Phase 'OUT' planst, musst du:
- Konkrete 'Actions on Objectives' planen (z.B. Exfiltration von Dummy-Daten)
- Für diesen Schritt eine 'Restoration Action' definieren (z.B. 'Delete malware file')
- Das Feld restoration_action im Output befüllen."""
    )

    # 4. Leg-Up-Regel
    parts.append(
        """Leg-Ups: Wenn du nicht weiterkommst (z.B. validation_error sagt 'Blocked'), darfst du proaktiv einen Leg-Up vorschlagen.
Setze dann leg_up im JSON mit: owner='Control Team', justification='Time constraint/Technical block'."""
    )

    return "\n\n".join(parts)


def _build_prompt(state: ScenarioState) -> str:
    """Baut den Kontext-Prompt für das LLM aus State-Daten."""
    parts: list[str] = []

    # 1. ThreatActorProfile (Wer bin ich?)
    threat_actor = state.get("threat_actor")
    if threat_actor:
        known = threat_actor.known_techniques or []
        techniques_str = ", ".join(known) if known else "beliebige MITRE ATT&CK Techniken (Format T####)"
        parts.append(
            f"## Bedrohungsakteur (Wer bin ich?)\n"
            f"- Name: {threat_actor.name}\n"
            f"- Kategorie: {threat_actor.category.value}\n"
            f"- Fähigkeit: {threat_actor.capability.value}\n"
            f"- Motivation: {', '.join(threat_actor.motivation or [])}\n"
            f"- Beschreibung: {threat_actor.description}\n"
            f"- Erlaubte Techniken: {techniques_str}"
        )

    # 2. CriticalFunction und Flags (Was ist das Ziel?)
    target_cif = state.get("target_cif")
    if target_cif:
        flags_str = ", ".join(target_cif.flags or [])
        parts.append(
            f"## Ziel (Was ist das Ziel?)\n"
            f"- Kritische Funktion: {target_cif.name}\n"
            f"- Sub-Funktionen: {', '.join(target_cif.sub_functions or [])}\n"
            f"- Unterstützende Assets: {', '.join(target_cif.supporting_assets or [])}\n"
            f"- Flags (Erfolgskriterien): {flags_str}"
        )

    # 3. History (Was ist bisher passiert?)
    msel_items = state.get("msel_items") or []
    if msel_items:
        history_lines = []
        for i, item in enumerate(msel_items, 1):
            desc = getattr(item, "action_description", "") or (item.get("action_description", "") if isinstance(item, dict) else "")
            tech = getattr(item, "technique_id", "") or (item.get("technique_id", "") if isinstance(item, dict) else "")
            phase = getattr(item, "phase", Phase.IN) if not isinstance(item, dict) else Phase(item.get("phase", "IN"))
            phase_val = phase.value if hasattr(phase, "value") else str(phase)
            history_lines.append(f"  {i}. [{phase_val}] {tech}: {desc}")
        parts.append(f"## Bisheriger Verlauf\n" + "\n".join(history_lines))
    else:
        parts.append("## Bisheriger Verlauf\n  (Noch keine Schritte – du startest den Angriff.)")

    # 4. Scope Constraints (aus scenario_metadata)
    scenario_meta = state.get("scenario_metadata")
    if scenario_meta and scenario_meta.constraints:
        constraints_str = "\n".join(f"- {c}" for c in scenario_meta.constraints)
        parts.append(f"## Scope Constraints (Verbotene Aktionen)\n{constraints_str}")

    # 5. Ziel-Anzahl Schritte (aus AgentConfig)
    config = state.get("agent_config")
    msel_items = state.get("msel_items") or []
    if config:
        min_e = getattr(config, "min_events", 5)
        max_e = getattr(config, "max_events", 10)
        parts.append(f"\n## Ziel: Erzeuge {min_e}–{max_e} Schritte insgesamt. Aktuell: {len(msel_items)}.")

    # 6. Erlaubte Techniken (bereits in ThreatActorProfile; bei leerem known_techniques: alle erlaubt)
    if threat_actor and threat_actor.known_techniques:
        parts.append(f"\nNutze NUR Techniken aus dieser Liste: {', '.join(threat_actor.known_techniques)}")

    # 7. Phase-OUT-Hinweis (wenn letzter Schritt OUT war oder nächster OUT sein soll)
    msel_items = state.get("msel_items") or []
    if msel_items:
        last_item = msel_items[-1]
        last_phase = getattr(last_item, "phase", Phase.IN) if not isinstance(last_item, dict) else Phase(last_item.get("phase", "IN"))
        if last_phase == Phase.OUT:
            parts.append(
                "\n## Phase OUT – Du bist in der Ausführungsphase. "
                "Plane konkrete Actions on Objectives und gib restoration_action an."
            )

    # 7. Retry-Feedback und Leg-Up-Trigger
    validation_error = state.get("validation_error")
    if validation_error:
        parts.append(
            f"## WICHTIG – Vorheriger Schritt abgelehnt\n"
            f"Der letzte generierte Schritt wurde abgelehnt: {validation_error}\n"
            f"Erzeuge einen neuen, korrigierten Schritt, der diese Validierung besteht."
        )
        if "blocked" in validation_error.lower() or "blockiert" in validation_error.lower():
            parts.append(
                "\nDu kannst einen Leg-Up vorschlagen (leg_up im JSON setzen): "
                "owner='Control Team', justification='Time constraint/Technical block'."
            )

    return "\n\n".join(parts)


def _normalize_technique_id(tech_id: str) -> str:
    """Sichert MITRE-Format (T-Prefix). Keine Validierung – nur Normalisierung."""
    s = (tech_id or "").strip().upper()
    if s and not s.startswith("T"):
        return "T" + s.lstrip("0") if s.isdigit() else "T" + s
    return s or "T0000"


def _draft_to_msel_item(
    draft: MSELItemDraft,
    step_index: int,
    scenario_id: str,
) -> MSELItem:
    """Konvertiert MSELItemDraft zu vollständigem MSELItem inkl. Leg-Up und restoration_action."""
    tech_id = _normalize_technique_id(draft.technique_id)
    item_id = uuid.uuid4()

    leg_up: LegUp | None = None
    if draft.leg_up:
        lu = draft.leg_up
        leg_up = LegUp(
            id=uuid.uuid4(),
            linked_step_id=item_id,
            description=lu.description,
            justification=lu.justification,
            type=lu.type,
            status=LegUpStatus.REQUESTED,
            owner=lu.owner,
            protocol=lu.protocol or "To be defined",
        )

    return MSELItem(
        id=item_id,
        step_index=step_index,
        scenario_id=scenario_id,
        time_planned=f"T+{step_index}h",
        time_actual_start=None,
        time_actual_end=None,
        phase=draft.phase,
        source=draft.source,
        target=draft.target,
        action_description=draft.action_description,
        technique_id=tech_id,
        tactic=draft.tactic,
        tools_used=draft.tools_used or [],
        security_goal=draft.security_goal,
        success_criteria=draft.success_criteria,
        result=draft.result,
        leg_up=leg_up,
        restoration_action=draft.restoration_action,
        detection_status=None,
        blue_team_response=None,
        log_reference=None,
    )


def _parse_json_fallback(content: str) -> MSELItemDraft | None:
    """Fallback: JSON aus LLM-Antwort extrahieren und parsen."""
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        leg_up_draft: LegUpDraft | None = None
        if data.get("leg_up"):
            lu = data["leg_up"]
            leg_up_draft = LegUpDraft(
                description=lu.get("description", ""),
                justification=lu.get("justification", "Time constraint/Technical block"),
                type=LegUpType(lu.get("type", "ACCESS")),
                owner=lu.get("owner", "Control Team"),
                protocol=lu.get("protocol", "To be defined"),
            )
        return MSELItemDraft(
            phase=Phase(data.get("phase", "IN")),
            source=data.get("source", ""),
            target=data.get("target", ""),
            action_description=data.get("action_description", ""),
            technique_id=data.get("technique_id", "T0000"),
            tactic=data.get("tactic", ""),
            tools_used=data.get("tools_used", []),
            security_goal=SecurityGoal(data.get("security_goal", "CONFIDENTIALITY")),
            success_criteria=data.get("success_criteria", ""),
            result=StepStatus(data.get("result", "PLANNED")),
            leg_up=leg_up_draft,
            restoration_action=data.get("restoration_action"),
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def _create_llm(temperature: float = 0.7):
    """Erstellt ChatAnthropic (Claude 3.5 Sonnet) oder ChatOpenAI."""
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=settings.llm_model or "claude-3-5-sonnet-20241022",
                api_key=settings.anthropic_api_key,
                temperature=temperature,
            )
        except ImportError:
            pass
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )


async def generate_step(state: ScenarioState) -> ScenarioState:
    """
    Generator-Node: Generiert einen neuen MSEL-Schritt und fügt ihn msel_items hinzu.

    - Context Building aus ThreatActorProfile, CriticalFunction, History
    - LLM-Call mit mit_structured_output(MSELItemDraft)
    - State Update: neues MSELItem an msel_items anhängen

    Keine Validierung – der Validator fängt Fehler.
    """
    threat_actor = state.get("threat_actor")
    scenario_id = state.get("scenario_id") or ""
    if not threat_actor:
        raise ValueError("ScenarioState muss threat_actor enthalten für den Generator.")
    if not scenario_id:
        raise ValueError("ScenarioState muss scenario_id enthalten für den Generator.")

    msel_items = list(state.get("msel_items") or [])
    step_index = len(msel_items) + 1

    logger.info("📝 Generator: Starte Generierung von Schritt %d (bisher %d Schritte)", step_index, len(msel_items))

    system_prompt = _build_system_prompt(state)
    user_prompt = _build_prompt(state)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"{user_prompt}\n\n"
            "Generiere den nächsten MSEL-Schritt als JSON. "
            "Antworte NUR mit gültigem JSON gemäß MSELItemDraft-Schema: "
            "phase (IN/THROUGH/OUT), source, target, action_description, technique_id (MITRE T####), "
            "tactic, tools_used (Liste), security_goal (CONFIDENTIALITY/INTEGRITY/AVAILABILITY), "
            "success_criteria (das Flag), result (PLANNED/SUCCESS/FAILED/BLOCKED/SKIPPED). "
            "Optional: leg_up (bei Blockierung: object mit description, justification, type, owner, protocol), "
            "restoration_action (Phase OUT: z.B. 'Delete malware file')."
        ),
    ]

    draft: MSELItemDraft | None = None
    has_llm = bool(settings.openai_api_key) or (
        settings.llm_provider == "anthropic" and settings.anthropic_api_key
    )

    if has_llm:
        config = state.get("agent_config")
        temp = getattr(config, "llm_temperature", 0.7) if config else 0.7
        logger.info("🤖 Generator: Rufe LLM auf (Structured Output, temp=%.2f)...", temp)
        llm = _create_llm(temperature=temp)
        try:
            structured_llm = llm.with_structured_output(MSELItemDraft)
            draft = await structured_llm.ainvoke(messages)
            if draft:
                logger.info("✅ Generator: LLM lieferte Schritt: %s – %s", draft.technique_id, draft.action_description[:60] + "..." if len(draft.action_description) > 60 else draft.action_description)
        except Exception as e:
            logger.warning("⚠️ Generator: Structured Output fehlgeschlagen, versuche Fallback: %s", e)
            pass

    if draft is None and has_llm:
        try:
            config = state.get("agent_config")
            temp = getattr(config, "llm_temperature", 0.7) if config else 0.7
            logger.info("🔄 Generator: Fallback – parse JSON aus LLM-Antwort...")
            llm = _create_llm(temperature=temp)
            response = await llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            draft = _parse_json_fallback(content)
            if draft:
                logger.info("✅ Generator: JSON-Fallback erfolgreich: %s", draft.technique_id)
        except Exception as e:
            logger.warning("⚠️ Generator: JSON-Fallback fehlgeschlagen: %s", e)
            pass

    if draft is None:
        logger.info("📌 Generator: Kein LLM verfügbar – verwende Platzhalter-Schritt")
        # Fallback: Minimaler Platzhalter-Schritt
        draft = MSELItemDraft(
            phase=Phase.IN if step_index == 1 else Phase.THROUGH,
            source="Extern",
            target="Zielsystem",
            action_description="Angriffsschritt (LLM nicht verfügbar)",
            technique_id="T1566",
            tactic="initial-access",
            tools_used=[],
            security_goal=SecurityGoal.CONFIDENTIALITY,
            success_criteria="Flag erreicht",
            result=StepStatus.PLANNED,
            leg_up=None,
            restoration_action=None,
        )

    new_item = _draft_to_msel_item(draft, step_index, scenario_id)
    msel_items.append(new_item)
    phase_val = getattr(draft.phase, "value", str(draft.phase))
    logger.info("➕ Generator: Schritt %d hinzugefügt [%s] %s – %s", step_index, phase_val, draft.technique_id, draft.action_description[:50] + "..." if len(draft.action_description) > 50 else draft.action_description)
    return {**state, "msel_items": msel_items}
