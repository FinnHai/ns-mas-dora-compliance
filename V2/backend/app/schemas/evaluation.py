"""Evaluation-Schemas."""
from pydantic import BaseModel, Field

from app.schemas.scenarios import ScenarioEvent, ScenarioResponse
from app.schemas.validation import ValidationResponse


class EvaluationCompareResponse(BaseModel):
    """Response fuer Neuro vs. Baseline Vergleich."""

    neuro: ScenarioResponse = Field(..., description="Neuro-symbolisches Szenario")
    baseline: ScenarioResponse = Field(..., description="Baseline (reines LLM)")
    neuro_validation: ValidationResponse = Field(..., description="Validation neuro-symbolisch")
    baseline_validation: ValidationResponse = Field(..., description="Validation Baseline")
