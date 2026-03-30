"""Graph-Schemas."""
from pydantic import BaseModel

from app.models.enums import LegUpType, Phase, SecurityGoal, StepStatus


class LegUpDraft(BaseModel):
    """LLM-Output-Schema für einen Leg-Up-Vorschlag (bei Blockierung)."""

    description: str  # Was wird gewährt?
    justification: str  # z.B. "Time constraint/Technical block"
    type: LegUpType = LegUpType.ACCESS
    owner: str = "Control Team"
    protocol: str = "To be defined"


class MSELItemDraft(BaseModel):
    """LLM-Output-Schema für einen MSEL-Schritt. Keine Validierung – kreativ, Validator prüft später."""

    phase: Phase
    source: str
    target: str
    action_description: str
    technique_id: str
    tactic: str
    tools_used: list[str] = []
    security_goal: SecurityGoal
    success_criteria: str
    result: StepStatus
    leg_up: LegUpDraft | None = None  # Optional: Vorschlag bei Blockierung
    restoration_action: str | None = None  # Phase OUT: z.B. 'Delete malware file'


class TacticInfo(BaseModel):
    """MITRE ATT&CK Taktik."""

    id: str
    name: str
    short_name: str


class TechniqueInfo(BaseModel):
    """MITRE ATT&CK Technik."""

    id: str
    name: str
    tactic_ids: list[str] = []


class TacticsResponse(BaseModel):
    """Response mit Taktiken."""

    tactics: list[TacticInfo]


class TechniqueResponse(BaseModel):
    """Response mit Techniken."""

    techniques: list[TechniqueInfo]
