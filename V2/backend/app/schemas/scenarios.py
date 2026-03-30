"""Szenario-Schemas."""
from pydantic import BaseModel, Field
from enum import Enum

from app.schemas.agent_config import AgentConfig
from app.schemas.validation import ValidationResponse


class ExecutionStep(BaseModel):
    """Einzelner Schritt im Ausführungsablauf."""

    step: str  # "generator" | "auditor" | "retry"
    iteration: int
    timestamp: str
    detail: str
    payload: dict = Field(default_factory=dict)


class ScenarioStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScenarioGenerateRequest(BaseModel):
    """Request für Szenario-Generierung."""

    threat_context: str = Field(..., description="Beschreibung der Bedrohung oder des Angriffsvektors")
    duration_hours: int = Field(default=24, ge=1, le=168, description="Zeitrahmen in Stunden (1-168)")
    additional_context: str | None = Field(default=None, description="Zusätzlicher Kontext")
    agent_config: AgentConfig | None = Field(default=None, description="Optionale Agent-Konfiguration")


class ScenarioEvent(BaseModel):
    """Einzelnes Ereignis im Szenario."""

    order: int
    description: str
    tactic_id: str | None = None
    technique_id: str | None = None
    timestamp_offset_hours: float = 0.0


class ScenarioResponse(BaseModel):
    """Response für Szenario."""

    id: str
    status: ScenarioStatus
    events: list[ScenarioEvent] = Field(default_factory=list)
    threat_context: str = ""
    audit_feedback: list[str] = Field(default_factory=list)
    error_message: str | None = None
    execution_trace: list[ExecutionStep] = Field(default_factory=list)
    validation: ValidationResponse | None = Field(
        default=None,
        description="Quantitative Evaluation (Action Alignment Score) wenn include_validation=True",
    )
