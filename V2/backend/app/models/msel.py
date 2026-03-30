"""MSEL-Pydantic-Modelle für TIBER-EU Szenarioschritte."""
from __future__ import annotations

from uuid import UUID
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.enums import (
    DetectionStatus,
    LegUpStatus,
    LegUpType,
    Phase,
    SecurityGoal,
    StepStatus,
)


class LegUp(BaseModel):
    """Unterstützungsanfrage (Leg-Up) für das Red Team."""

    id: UUID
    linked_step_id: UUID  # Verweis auf den Angriffsschritt
    description: str  # Was wird gewährt?
    justification: str  # Warum? z.B. Timeout
    type: LegUpType
    status: LegUpStatus
    owner: str  # Wer genehmigt das? z.B. 'Control Team'
    protocol: str  # Wie wird übergeben? z.B. 'Encrypted Email'


class MSELItem(BaseModel):
    """Ein MSEL-Szenarioschritt mit Admin-, Timing-, MITRE- und Blue-Team-Daten."""

    # Admin
    id: UUID
    step_index: int
    scenario_id: str

    # Timing
    time_planned: str
    time_actual_start: Optional[str] = None
    time_actual_end: Optional[str] = None

    # Core Logic
    phase: Phase
    source: str
    target: str
    action_description: str

    # MITRE
    technique_id: str  # Validierung: muss mit 'T' starten
    tactic: str
    tools_used: list[str]

    # Objective
    security_goal: SecurityGoal
    success_criteria: str  # das Flag
    result: StepStatus

    # Relations
    leg_up: Optional[LegUp] = None
    restoration_action: Optional[str] = None  # Phase OUT: z.B. 'Delete malware file'

    # Blue Team (Optional)
    detection_status: Optional[DetectionStatus] = None
    blue_team_response: Optional[str] = None
    log_reference: Optional[str] = None

    @field_validator("technique_id")
    @classmethod
    def validate_technique_id(cls, v: str) -> str:
        if not v or not v.upper().startswith("T"):
            raise ValueError(
                "technique_id muss mit 'T' starten (MITRE ATT&CK Format)"
            )
        return v
