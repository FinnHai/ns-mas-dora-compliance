"""LangGraph MSEL-Generator-Validator-Graph: Haupt-Orchestrierung."""
import logging

from langgraph.graph import StateGraph, END

from app.graph.state import ScenarioState
from app.graph.nodes import generate_step, validate_step

logger = logging.getLogger(__name__)


def _route_after_validation(state: ScenarioState) -> str:
    """Routing nach Validator: END oder zurück zu generator."""
    if state.get("flag_achieved"):
        return END

    msel_items = state.get("msel_items") or []
    steps = len(msel_items)

    if steps >= state.get("max_steps", 20):
        return END

    if len(msel_items) >= 2:
        last = msel_items[-1]
        prev = msel_items[-2]
        if isinstance(last, dict):
            phase_val = last.get("phase")
        else:
            p = getattr(last, "phase", None)
            phase_val = p.value if p and hasattr(p, "value") else str(p) if p else None
        last_tech = getattr(last, "technique_id", None) or (
            last.get("technique_id") if isinstance(last, dict) else None
        )
        prev_tech = getattr(prev, "technique_id", None) or (
            prev.get("technique_id") if isinstance(prev, dict) else None
        )
        if phase_val == "OUT" and last_tech and last_tech == prev_tech:
            return END

    return "generator"


graph = StateGraph(ScenarioState)
graph.add_node("generator", generate_step)
graph.add_node("validator", validate_step)

graph.set_entry_point("generator")
graph.add_edge("generator", "validator")
graph.add_conditional_edges("validator", _route_after_validation)

app = graph.compile()


async def run_scenario(initial_state: ScenarioState) -> ScenarioState:
    """
    Führt das MSEL-Szenario mit dem initialen State aus.
    Gibt den Final-State zurück.
    """
    logger.info("🚀 Szenario-Generierung gestartet (max. %d Schritte)", initial_state.get("max_steps", 20))
    final_state = await app.ainvoke(initial_state)
    msel_count = len(final_state.get("msel_items", []))
    logger.info("✅ Szenario-Generierung abgeschlossen – %d MSEL-Schritte erzeugt", msel_count)
    return final_state


async def run_scenario_stream(initial_state: ScenarioState):
    """
    Streamt die Szenario-Generierung und liefert (node_name, data) nach jedem Schritt.
    Für Live-Logs und Fortschrittsanzeige.
    Nutzt stream_mode=updates: event = {node_name: state_update}
    """
    logger.info("🚀 Szenario-Generierung gestartet (Streaming-Modus)")
    merged_state = dict(initial_state)
    prev_items = 0

    async for event in app.astream(initial_state, stream_mode="updates"):
        for node_name, state_update in event.items():
            upd = state_update if isinstance(state_update, dict) else dict(state_update)
            merged_state.update(upd)
            msel_items = merged_state.get("msel_items") or []
            val_err = merged_state.get("validation_error")
            flag_ok = merged_state.get("flag_achieved", False)

            if node_name == "generator" and len(msel_items) > prev_items:
                prev_items = len(msel_items)
                last = msel_items[-1] if msel_items else None
                if isinstance(last, dict):
                    tech = last.get("technique_id", "")
                    desc_raw = last.get("action_description", "")
                else:
                    tech = getattr(last, "technique_id", "") if last else ""
                    desc_raw = getattr(last, "action_description", "") if last else ""
                desc = (desc_raw or "")[:60]
                yield "generator", {"step": prev_items, "technique_id": tech, "action": desc, "state": dict(merged_state)}
            elif node_name == "validator":
                yield "validator", {"approved": val_err is None, "error": val_err, "flag_achieved": flag_ok, "state": dict(merged_state)}
