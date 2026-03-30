"""State für NS-MAS Pipeline (Planner → Generator → Auditor → Human Review → Synthesizer)."""
from typing import TypedDict

from app.models.ns_mas_schemas import (
    AttackSketch,
    CorrectionHint,
    TTPScenario,
    UserInput,
    ValidationReport,
)


class NSMasPipelineState(TypedDict, total=False):
    """State für die NS-MAS Pipeline."""

    baseline_mode: bool  # True = Korrekturschleife deaktiviert (Evaluation-Baseline)
    user_input: UserInput
    attack_sketch: AttackSketch
    ttp_scenario: TTPScenario
    validation_report: ValidationReport
    correction_hints: list[CorrectionHint]
    auditor_iterations: int
    human_approved: bool
    report: dict
    error: str | None
