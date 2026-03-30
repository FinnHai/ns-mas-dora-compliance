"""Gemeinsamer ScenarioState für MSEL-Graph (Generator, Validator)."""
from typing import TypedDict

from app.models.msel import MSELItem
from app.models.strategy import CriticalFunction, ScenarioMetadata, ThreatActorProfile
from app.schemas.agent_config import AgentConfig


class ScenarioState(TypedDict, total=False):
    """State für den MSEL-Graph mit Generierung und Validierung."""

    msel_items: list[MSELItem]
    validation_error: str | None
    target_cif: CriticalFunction | None
    threat_actor: ThreatActorProfile
    scenario_metadata: ScenarioMetadata | None
    scenario_id: str
    flag_achieved: bool
    max_steps: int
    agent_config: AgentConfig
