"""NS-MAS Pipeline: Planner → Generator → Auditor (max 3x) → Human Review → Synthesizer."""
import logging

print("[Startup]   ns_mas: Lade LangGraph...", flush=True)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
print("[Startup]   ns_mas: LangGraph OK, lade Agents...", flush=True)
print("[Startup]   ns_mas: → kg_auditor...", flush=True)
from app.agents.kg_auditor import run_kg_auditor
print("[Startup]   ns_mas: kg_auditor OK", flush=True)
# report_synthesizer, scenario_planner, ttp_generator: Lazy-Import (LangChain blockiert sonst 5+ Min)
print("[Startup]   ns_mas: Pipeline-Skeleton OK (LangChain-Agents lazy)", flush=True)
from app.graph.ns_mas_routing import (
    _route_after_auditor,
    _route_after_human_review,
)
from app.graph.ns_mas_state import NSMasPipelineState
from app.models.ns_mas_schemas import TTPScenario, UserInput

logger = logging.getLogger(__name__)


async def scenario_planner_node(state: NSMasPipelineState) -> NSMasPipelineState:
    """Scenario Planner: UserInput → AttackSketch."""
    from app.agents.scenario_planner import run_scenario_planner
    logger.info("NS-MAS: Scenario Planner startet…")
    raw = state.get("user_input")
    if not raw:
        return {**state, "error": "user_input fehlt"}
    user_input = UserInput(**raw) if isinstance(raw, dict) else raw
    logger.info(
        "NS-MAS: Scenario Planner Input – Org=%s, Threat=%s",
        getattr(user_input, "target_organization", raw.get("target_organization", "?")),
        getattr(user_input, "threat_profile", raw.get("threat_profile", "?")),
    )
    sketch = await run_scenario_planner(user_input)
    logger.info("NS-MAS: Scenario Planner fertig → TTP Generator")
    return {**state, "attack_sketch": sketch, "error": None}


async def ttp_generator_node(state: NSMasPipelineState) -> NSMasPipelineState:
    """TTP Generator: AttackSketch + CorrectionHints → TTPScenario."""
    from app.agents.ttp_generator import run_ttp_generator
    iterations = state.get("auditor_iterations", 0)
    logger.info("NS-MAS: TTP Generator startet (RAG, Iteration %d)…", iterations + 1)
    sketch = state.get("attack_sketch")
    if not sketch:
        return {**state, "error": "attack_sketch fehlt"}
    hints = state.get("correction_hints") or []
    ttp = await run_ttp_generator(sketch, correction_hints=hints, use_rag=True)
    phases = ttp.get("phases", []) if isinstance(ttp, dict) else getattr(ttp, "phases", [])
    steps_count = sum(
        len(ps.get("steps", []) if isinstance(ps, dict) else getattr(ps, "steps", []))
        for ps in phases
    )
    logger.info("NS-MAS: TTP Generator fertig – %d Phasen, %d Steps → KG Auditor", len(phases), steps_count)
    return {**state, "ttp_scenario": ttp, "error": None}


async def kg_auditor_node(state: NSMasPipelineState) -> NSMasPipelineState:
    """KG Auditor: TTPScenario → ValidationReport."""
    iterations = state.get("auditor_iterations", 0)
    logger.info("NS-MAS: KG Auditor startet (Iteration %d/3)…", iterations + 1)
    ttp = state.get("ttp_scenario")
    if not ttp:
        return {**state, "error": "ttp_scenario fehlt"}
    report = await run_kg_auditor(ttp, auditor_iterations=iterations)
    next_iter = iterations + 1 if not report.passed else iterations
    logger.info("NS-MAS: KG Auditor fertig – %s", "PASS" if report.passed else f"FAIL (→ Korrektur {next_iter}/3)")

    # Validierungsplan Punkt 3: Logging nach jedem Auditor-Durchlauf
    ttp_obj = state.get("ttp_scenario")
    technique_ids = []
    if ttp_obj:
        phases = ttp_obj.get("phases", []) if isinstance(ttp_obj, dict) else getattr(ttp_obj, "phases", [])
        for ps in phases:
            steps = ps.get("steps", []) if isinstance(ps, dict) else getattr(ps, "steps", [])
            for s in steps:
                technique_ids.append(s.get("technique_id", "") if isinstance(s, dict) else getattr(s, "technique_id", ""))
    hints_msgs = [h.message if hasattr(h, "message") else h.get("message", "") for h in (report.correction_hints or [])]
    logger.info(
        "Auditor Iteration %d | Passed: %s | Hints: %s | Technique IDs: %s",
        next_iter,
        report.passed,
        hints_msgs,
        technique_ids,
    )

    return {
        **state,
        "validation_report": report,
        "correction_hints": report.correction_hints,
        "auditor_iterations": next_iter,
        "error": None,
    }


async def human_review_node(state: NSMasPipelineState) -> NSMasPipelineState:
    """Human Review Gate: Pausiert bis Nutzer freigibt (DR5)."""
    logger.info("NS-MAS: Human Review Gate – warte auf Freigabe im Frontend")
    ttp = state.get("ttp_scenario")
    scenario_id = ttp.scenario_id if hasattr(ttp, "scenario_id") else (ttp.get("scenario_id", "") if isinstance(ttp, dict) else "")
    approved = interrupt({
        "message": "Bitte Szenario prüfen und freigeben oder ablehnen.",
        "ttp_scenario_id": scenario_id,
    })
    return {**state, "human_approved": bool(approved)}


async def report_synthesizer_node(state: NSMasPipelineState) -> NSMasPipelineState:
    """Report Synthesizer: TTPScenario + UserInput → MSEL Report."""
    from app.agents.report_synthesizer import run_report_synthesizer
    logger.info("NS-MAS: Report Synthesizer startet…")
    ttp = state.get("ttp_scenario")
    raw_ui = state.get("user_input")
    if not ttp or not raw_ui:
        return {**state, "error": "ttp_scenario oder user_input fehlt"}
    user_input = UserInput(**raw_ui) if isinstance(raw_ui, dict) else raw_ui
    ttp_obj = TTPScenario(**ttp) if isinstance(ttp, dict) else ttp
    report = await run_report_synthesizer(ttp_obj, user_input)
    if isinstance(report, dict):
        msel = report.get("msel", {})
        events = msel.get("events", []) if isinstance(msel, dict) else []
        narrative = report.get("narrative", "") or ""
        logger.info(
            "NS-MAS: Report Synthesizer fertig – %d MSEL-Events, %d Zeichen Narrative – Pipeline abgeschlossen",
            len(events),
            len(narrative),
        )
    else:
        logger.info("NS-MAS: Report Synthesizer fertig – Pipeline abgeschlossen")
    return {**state, "report": report, "error": None}


def build_ns_mas_graph(checkpointer=None):
    """Baut den NS-MAS LangGraph."""
    workflow = StateGraph(NSMasPipelineState)

    workflow.add_node("scenario_planner", scenario_planner_node)
    workflow.add_node("ttp_generator", ttp_generator_node)
    workflow.add_node("kg_auditor", kg_auditor_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("report_synthesizer", report_synthesizer_node)

    workflow.set_entry_point("scenario_planner")
    workflow.add_edge("scenario_planner", "ttp_generator")
    workflow.add_edge("ttp_generator", "kg_auditor")
    workflow.add_conditional_edges("kg_auditor", _route_after_auditor)
    workflow.add_conditional_edges("human_review", _route_after_human_review)
    workflow.add_edge("report_synthesizer", END)

    # Human Review Gate: interrupt() in human_review_node (DR5) - Checkpointer erforderlich
    cp = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=cp)