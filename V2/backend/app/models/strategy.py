"""Strategie-Modelle: CIF, Threat Actor Profile, Scenario Metadata."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.models.enums import ActorCategory, CapabilityLevel


class CriticalFunction(BaseModel):
    """Kritische Geschäftsfunktion (CIF) – Business und Technical View."""

    id: str
    name: str  # Business View (z.B. 'Payment Processing')
    sub_functions: List[str]
    supporting_assets: List[str]  # Technical View (Server/IPs)
    flags: List[str]  # Konkrete Beweise (z.B. 'Screenshot of DB')


class ThreatActorProfile(BaseModel):
    """Profil eines Bedrohungsakteurs für Szenario-Planung."""

    name: str  # z.B. 'APT29'
    category: ActorCategory
    motivation: List[str]
    targeted_cifs: List[str]  # Welche CIFs greift er an?
    capability: CapabilityLevel
    known_techniques: List[str]  # Liste von MITRE IDs
    description: str


class ScenarioMetadata(BaseModel):
    """Metadaten eines MSEL-Szenarios."""

    id: str
    name: str
    threat_actor: ThreatActorProfile
    target_cif: CriticalFunction
    is_scenario_x: bool = False
    constraints: List[str]  # Verbotene Aktionen
