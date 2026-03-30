"""Validator-Node für MSEL-Schritt-Validierung."""
import logging

from app.graph.state import ScenarioState

logger = logging.getLogger(__name__)
from app.models.enums import StepStatus
from app.models.msel import MSELItem
from app.models.strategy import CriticalFunction
from app.services.neo4j_connector import Neo4jService

# DORA Hard Constraints: Verbotene Begriffe in action_description
DESTRUCTIVE_ACTION_WORDS = ("destroy", "wipe", "delete")

# Zusätzliche Begriffe für Technik-Destruktivität (Neo4j name/description)
DESTRUCTIVE_TECHNIQUE_WORDS = ("destroy", "wipe", "delete", "corrupt")

# Keywords die auf Zielerreichung in Phase OUT hindeuten
SUCCESS_ACTION_KEYWORDS = ("exfiltrate", "flag", "success", "screenshot")


def _get_attr(step: MSELItem | dict, key: str) -> str:
    """Holt Attribut aus MSELItem oder dict."""
    if hasattr(step, key):
        return getattr(step, key) or ""
    return step.get(key, "") if isinstance(step, dict) else ""


def _get_result(step: MSELItem | dict) -> StepStatus:
    """Holt result aus MSELItem oder dict."""
    if hasattr(step, "result"):
        val = getattr(step, "result")
        return val if isinstance(val, StepStatus) else StepStatus(val) if val else StepStatus.PLANNED
    raw = step.get("result", "PLANNED") if isinstance(step, dict) else "PLANNED"
    return StepStatus(raw) if raw else StepStatus.PLANNED


def _is_flag_achieved(
    success_criteria: str,
    result: StepStatus,
    target_cif: CriticalFunction | None,
) -> bool:
    """Prüft ob ein Flag erreicht wurde (success_criteria enthält Flag, result=SUCCESS)."""
    if result != StepStatus.SUCCESS or not target_cif or not target_cif.flags:
        return False
    criteria_lower = success_criteria.lower()
    return any(flag.lower() in criteria_lower for flag in target_cif.flags)


def _target_is_critical_function(target: str, cif: CriticalFunction | None) -> bool:
    """Prüft ob target zur Critical Function gehört."""
    if not cif:
        return False
    target_lower = target.lower().strip()
    if target_lower == cif.name.lower():
        return True
    if any(sf.lower() == target_lower for sf in cif.sub_functions):
        return True
    if any(sa.lower() == target_lower for sa in cif.supporting_assets):
        return True
    return False


def _action_suggests_success(action_description: str) -> bool:
    """Prüft ob action_description auf Zielerreichung hindeutet."""
    desc_lower = action_description.lower()
    return any(kw in desc_lower for kw in SUCCESS_ACTION_KEYWORDS)


def _is_destructive_action(action_description: str) -> bool:
    """Prüft ob action_description destruktive Begriffe enthält."""
    desc_lower = action_description.lower()
    return any(word in desc_lower for word in DESTRUCTIVE_ACTION_WORDS)


def _is_destructive_technique(neo4j: Neo4jService, technique_id: str) -> bool:
    """Prüft ob Technik (name/description) destruktiv wirkt."""
    details = neo4j.get_technique_details(technique_id)
    combined = f"{details.get('name', '')} {details.get('description', '')}".lower()
    return any(word in combined for word in DESTRUCTIVE_TECHNIQUE_WORDS)


def validate_step(state: ScenarioState) -> ScenarioState:
    """
    Validiert den letzten hinzugefügten MSEL-Schritt.

    - Graph Check: Neo4j validate_path
    - DORA: Keine destruktiven Begriffe in action_description
    - DORA: Keine destruktive Technik auf Critical Function
    """
    msel_items = list(state.get("msel_items") or [])
    if not msel_items:
        return state

    current = msel_items[-1]
    step_num = len(msel_items)
    tech = _get_attr(current, "technique_id")
    action = _get_attr(current, "action_description")[:50]
    logger.info("🔍 Validator: Prüfe Schritt %d – %s: %s...", step_num, tech, action)
    prev = msel_items[-2] if len(msel_items) >= 2 else None
    prev_tech: str | None = _get_attr(prev, "technique_id") if prev else None
    if prev_tech == "":
        prev_tech = None

    current_tech = _get_attr(current, "technique_id")
    if not current_tech:
        logger.warning("❌ Validator: Schritt abgelehnt – Technik-ID fehlt")
        msel_items.pop()
        return {**state, "msel_items": msel_items, "validation_error": "Technique ID missing."}

    neo4j = Neo4jService()
    if not neo4j.validate_path(prev_tech, current_tech):
        logger.warning("❌ Validator: Schritt abgelehnt – ungültiger Pfad %s → %s (MITRE Kill Chain)", prev_tech or "Start", current_tech)
        msel_items.pop()
        return {**state, "msel_items": msel_items, "validation_error": "Technically impossible path between techniques."}

    action_desc = _get_attr(current, "action_description")
    if _is_destructive_action(action_desc):
        logger.warning("❌ Validator: Schritt abgelehnt – destruktive Aktion (DORA)")
        msel_items.pop()
        return {
            **state,
            "msel_items": msel_items,
            "validation_error": "Destructive action not allowed in action description (DORA).",
        }

    target = _get_attr(current, "target")
    target_cif = state.get("target_cif")
    if _target_is_critical_function(target, target_cif) and _is_destructive_technique(
        neo4j, current_tech
    ):
        logger.warning("❌ Validator: Schritt abgelehnt – destruktive Technik auf kritische Funktion (DORA)")
        msel_items.pop()
        return {
            **state,
            "msel_items": msel_items,
            "validation_error": "Destructive technique on critical function not allowed (DORA).",
        }

    success_criteria = _get_attr(current, "success_criteria")
    result = _get_result(current)
    flag_achieved = _is_flag_achieved(success_criteria, result, target_cif)

    if not flag_achieved:
        phase_val = getattr(current, "phase", None) or (
            current.get("phase") if isinstance(current, dict) else None
        )
        phase_str = phase_val.value if hasattr(phase_val, "value") else str(phase_val) if phase_val else ""
        if phase_str == "OUT" and _action_suggests_success(action_desc):
            flag_achieved = True

    if flag_achieved:
        logger.info("🏁 Validator: Schritt %d OK – Flag erreicht, Szenario abgeschlossen!", step_num)
    else:
        logger.info("✅ Validator: Schritt %d OK – Pfad valide, weiter zum nächsten Schritt", step_num)
    return {**state, "validation_error": None, "flag_achieved": flag_achieved}
