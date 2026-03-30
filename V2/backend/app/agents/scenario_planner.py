"""Scenario Planner Agent: UserInput → AttackSketch."""
import json
import logging
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.config_loader import get_prompt
from app.models.ns_mas_schemas import AttackSketch, PhaseSketch, UserInput

logger = logging.getLogger(__name__)


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


def _parse_attack_sketch(content: str) -> AttackSketch | None:
    """Parst JSON-Antwort zu AttackSketch."""
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        phases = []
        for p in data.get("phases", []):
            phases.append(PhaseSketch(
                phase=p.get("phase", "in"),
                target_assets=p.get("target_assets", []),
                high_level_goals=p.get("high_level_goals", []),
            ))
        return AttackSketch(
            scenario_id=data.get("scenario_id", str(uuid.uuid4())),
            target_organization=data.get("target_organization", ""),
            threat_actor=data.get("threat_actor", ""),
            phases=phases,
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Parse-Fehler AttackSketch: %s", e)
        return None


async def run_scenario_planner(user_input: UserInput) -> AttackSketch:
    """
    Führt den Scenario Planner aus.
    Input: UserInput
    Output: AttackSketch (phases: in, through, out)
    """
    template = get_prompt("scenario_planner")
    if not template:
        template = (
            "Du bist ein Threat Intelligence Analyst. Erstelle eine Angriffsskizze für:\n"
            "- Zielorganisation: {target_organization}\n"
            "- Bedrohungsprofil: {threat_profile}\n"
            "- Scope: {scope_document}\n\n"
            "Antworte ausschließlich als JSON mit: scenario_id, target_organization, threat_actor, "
            "phases: [{phase, target_assets, high_level_goals}]. Phasen: in, through, out."
        )

    prompt = template.format(
        target_organization=user_input.target_organization,
        threat_profile=user_input.threat_profile,
        scope_document=user_input.scope_document or "(nicht angegeben)",
    )

    has_llm = bool(settings.openai_api_key) or (
        settings.llm_provider == "anthropic" and settings.anthropic_api_key
    )

    if has_llm:
        try:
            llm = _create_llm()
            structured = llm.with_structured_output(AttackSketch)
            result = await structured.ainvoke([
                HumanMessage(content=prompt),
            ])
            if result:
                logger.info("Scenario Planner: AttackSketch erstellt, %d Phasen", len(result.phases))
                return result
        except Exception as e:
            logger.warning("Structured Output fehlgeschlagen, Fallback: %s", e)

        try:
            llm = _create_llm()
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            result = _parse_attack_sketch(content)
            if result:
                return result
        except Exception as e:
            logger.warning("Fallback-Parse fehlgeschlagen: %s", e)

    # Fallback: Minimaler AttackSketch
    scenario_id = str(uuid.uuid4())
    return AttackSketch(
        scenario_id=scenario_id,
        target_organization=user_input.target_organization,
        threat_actor=user_input.threat_profile,
        phases=[
            PhaseSketch(phase="in", target_assets=[], high_level_goals=["Initial Access"]),
            PhaseSketch(phase="through", target_assets=[], high_level_goals=["Lateral Movement"]),
            PhaseSketch(phase="out", target_assets=[], high_level_goals=["Exfiltration"]),
        ],
    )
