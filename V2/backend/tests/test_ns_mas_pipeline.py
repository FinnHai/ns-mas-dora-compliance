"""Unit Tests für NS-MAS Pipeline.

Routing-Logik wird inline getestet, um LangGraph-Import zu vermeiden (Hang auf macOS).
"""
import pytest

from app.models.ns_mas_schemas import ValidationReport


def _route_after_auditor(state: dict, max_iter: int = 3) -> str:
    """Routing-Logik (Kopie für Unit-Test ohne LangGraph-Import)."""
    report = state.get("validation_report")
    iterations = state.get("auditor_iterations", 0)
    if report and report.passed:
        return "human_review"
    if iterations < max_iter:
        return "ttp_generator"
    return "human_review"


def _route_after_human_review(state: dict) -> str:
    """Routing-Logik (Kopie für Unit-Test ohne LangGraph-Import)."""
    return "report_synthesizer" if state.get("human_approved") else "__END__"


class TestBuildNSMasGraph:
    @pytest.mark.slow
    def test_build_ns_mas_graph(self):
        """build_ns_mas_graph() kompiliert ohne Fehler (langsam wegen LangChain-Import)."""
        from app.graph.ns_mas_pipeline import build_ns_mas_graph

        app = build_ns_mas_graph()
        assert app is not None


class TestRouteAfterAuditor:
    def test_route_after_auditor_passed(self):
        """report.passed → 'human_review'."""
        state = {
            "validation_report": ValidationReport(passed=True, steps=[], auditor_iterations=0),
            "auditor_iterations": 0,
        }
        result = _route_after_auditor(state, max_iter=3)
        assert result == "human_review"

    def test_route_after_auditor_retry(self):
        """not passed, iterations=1, max=3 → 'ttp_generator'."""
        state = {
            "validation_report": ValidationReport(passed=False, steps=[], auditor_iterations=1),
            "auditor_iterations": 1,
        }
        result = _route_after_auditor(state, max_iter=3)
        assert result == "ttp_generator"

    def test_route_after_auditor_fallback(self):
        """not passed, iterations=3 → 'human_review'."""
        state = {
            "validation_report": ValidationReport(passed=False, steps=[], auditor_iterations=3),
            "auditor_iterations": 3,
        }
        result = _route_after_auditor(state, max_iter=3)
        assert result == "human_review"


class TestRouteAfterHumanReview:
    def test_route_after_human_review_approved(self):
        """human_approved=True → 'report_synthesizer'."""
        state = {"human_approved": True}
        result = _route_after_human_review(state)
        assert result == "report_synthesizer"

    def test_route_after_human_review_rejected(self):
        """human_approved=False → END."""
        state = {"human_approved": False}
        result = _route_after_human_review(state)
        assert result == "__END__"
