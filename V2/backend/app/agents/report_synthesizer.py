"""Report Synthesizer: Validierte TTPScenario → TIBER-EU MSEL."""
import logging

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.config_loader import get_prompt
from app.models.ns_mas_schemas import TTPScenario, UserInput

logger = logging.getLogger(__name__)


def _create_llm():
    """LLM mit temperature=0 für Reproduzierbarkeit."""
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


def ttp_to_msel_json(ttp: TTPScenario) -> dict:
    """Konvertiert TTPScenario in TIBER-EU MSEL JSON-Format."""
    events = []
    order = 1
    for ps in ttp.phases:
        for step in ps.steps:
            events.append({
                "order": order,
                "phase": ps.phase,
                "technique_id": step.technique_id,
                "technique_name": step.technique_name,
                "tactic": step.tactic,
                "description": step.description,
                "cve_references": step.cve_references,
            })
            order += 1
    return {
        "scenario_id": ttp.scenario_id,
        "target_organization": ttp.target_organization,
        "threat_actor": ttp.threat_actor,
        "events": events,
    }


async def run_report_synthesizer(
    ttp_scenario: TTPScenario,
    user_input: UserInput,
) -> dict:
    """
    Erstellt MSEL-Dokument (JSON + optional narrativer Text).
    """
    msel_json = ttp_to_msel_json(ttp_scenario)
    narrative = ""

    template = get_prompt("report_synthesizer")
    has_llm = bool(settings.openai_api_key) or (
        settings.llm_provider == "anthropic" and settings.anthropic_api_key
    )

    if has_llm and template:
        try:
            prompt = template.format(
                ttp_scenario_json=ttp_scenario.model_dump_json(indent=2),
                target_organization=user_input.target_organization,
                threat_profile=user_input.threat_profile,
            )
            llm = _create_llm()
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            narrative = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning("Report Synthesizer LLM: %s", e)

    if not narrative:
        # Fallback: Kurze Zusammenfassung
        steps = ttp_scenario.get_all_steps_flat()
        techs = [s.technique_id for s in steps]
        narrative = f"Szenario {ttp_scenario.scenario_id}: Angriffssequenz über {len(steps)} Schritte ({', '.join(techs[:5])}{'...' if len(techs) > 5 else ''})."

    return {
        "msel": msel_json,
        "narrative": narrative,
    }
