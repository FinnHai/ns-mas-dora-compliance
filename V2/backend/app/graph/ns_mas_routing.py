"""Routing-Logik für NS-MAS Pipeline (leichtgewichtig, für Unit-Tests)."""
from langgraph.graph import END

from app.config import settings

MAX_AUDITOR_ITERATIONS = 3


def _route_after_auditor(state: dict) -> str:
    """Routing nach KG Auditor: human_review oder ttp_generator (Retry) oder human_review (Fallback)."""
    if state.get("baseline_mode"):
        return "human_review"  # Baseline: Auditor misst, aber keine Korrekturschleife
    report = state.get("validation_report")
    iterations = state.get("auditor_iterations", 0)
    max_iter = getattr(settings, "max_audit_iterations", MAX_AUDITOR_ITERATIONS)

    if report and report.passed:
        return "human_review"
    if iterations < max_iter:
        return "ttp_generator"
    return "human_review"


def _route_after_human_review(state: dict) -> str:
    """Routing nach Human Review: report_synthesizer oder END."""
    if state.get("human_approved"):
        return "report_synthesizer"
    return END
