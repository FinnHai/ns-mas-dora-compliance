"""Unit Tests für NS-MAS Pydantic-Schemas."""
import pytest

from app.models.ns_mas_schemas import (
    AttackSketch,
    CorrectionHint,
    PhaseSketch,
    PhaseSteps,
    StepValidation,
    TTPScenario,
    TTPStep,
    UserInput,
    ValidationReport,
)


class TestUserInput:
    def test_user_input_valid(self):
        """UserInput mit target_organization, threat_profile."""
        ui = UserInput(
            target_organization="Finanzinstitut XY",
            threat_profile="APT29",
        )
        assert ui.target_organization == "Finanzinstitut XY"
        assert ui.threat_profile == "APT29"
        assert ui.scope_document is None

    def test_user_input_with_scope(self):
        """UserInput mit scope_document."""
        ui = UserInput(
            target_organization="Bank",
            threat_profile="Ransomware",
            scope_document="Scope-Dokument Text",
        )
        assert ui.scope_document == "Scope-Dokument Text"


class TestAttackSketch:
    def test_attack_sketch_phases_order(self):
        """AttackSketch Phasen in Reihenfolge in, through, out."""
        sketch = AttackSketch(
            scenario_id="sc-1",
            target_organization="Org",
            threat_actor="APT29",
            phases=[
                PhaseSketch(phase="out", target_assets=["DB"], high_level_goals=["Exfiltrate"]),
                PhaseSketch(phase="in", target_assets=["Gateway"], high_level_goals=["Access"]),
                PhaseSketch(phase="through", target_assets=["Server"], high_level_goals=["Move"]),
            ],
        )
        phase_order = {"in": 0, "through": 1, "out": 2}
        sorted_phases = sorted(sketch.phases, key=lambda p: phase_order.get(p.phase, 0))
        assert [p.phase for p in sorted_phases] == ["in", "through", "out"]


class TestTTPScenario:
    def test_ttp_scenario_get_all_steps_flat(self):
        """TTPScenario mit mehreren PhaseSteps."""
        ttp = TTPScenario(
            scenario_id="sc-1",
            target_organization="Org",
            threat_actor="APT29",
            phases=[
                PhaseSteps(phase="through", steps=[
                    TTPStep(step_id=2, technique_id="T1059", tactic="execution"),
                ]),
                PhaseSteps(phase="in", steps=[
                    TTPStep(step_id=1, technique_id="T1566", tactic="initial-access"),
                ]),
                PhaseSteps(phase="out", steps=[
                    TTPStep(step_id=3, technique_id="T1048", tactic="exfiltration"),
                ]),
            ],
        )
        flat = ttp.get_all_steps_flat()
        assert len(flat) == 3
        assert flat[0].technique_id == "T1566"
        assert flat[1].technique_id == "T1059"
        assert flat[2].technique_id == "T1048"


class TestValidationReport:
    def test_validation_report_passed(self):
        """ValidationReport mit passed=True/False."""
        report_fail = ValidationReport(passed=False, steps=[], correction_hints=[])
        assert report_fail.passed is False

        report_ok = ValidationReport(passed=True, steps=[], auditor_iterations=1)
        assert report_ok.passed is True


class TestCorrectionHint:
    def test_correction_hint_suggested_technique(self):
        """CorrectionHint mit suggested_technique_id."""
        hint = CorrectionHint(
            step_id=1,
            technique_id="T99999",
            message="Technik existiert nicht",
            suggested_technique_id="T1566",
        )
        assert hint.suggested_technique_id == "T1566"
        assert hint.step_id == 1
