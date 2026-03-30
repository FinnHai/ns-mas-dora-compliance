"""Validierungs-Schemas."""
from pydantic import BaseModel, Field


class ScenarioEventInput(BaseModel):
    """Eingabe-Ereignis für Validierung."""

    order: int
    description: str
    tactic_id: str | None = None
    technique_id: str | None = None


class ValidationRequest(BaseModel):
    """Request für Szenario-Validierung."""

    events: list[ScenarioEventInput] = Field(..., description="Zu validierende Ereignisse")


class ValidationResult(BaseModel):
    """Einzelnes Validierungsergebnis."""

    order: int
    is_valid: bool
    message: str
    suggested_tactic_id: str | None = None
    suggested_technique_id: str | None = None


class ValidationResponse(BaseModel):
    """Response der Validierung."""

    overall_valid: bool
    action_alignment_score: float = Field(ge=0, le=1, description="Mapping-Accuracy nach SECURE")
    results: list[ValidationResult] = Field(default_factory=list)
    sequence_valid: bool = True
    sequence_message: str = ""
    tactic_coverage: float = 0.0
    technique_validity: float = 0.0
    technique_mapping: float = 0.0
