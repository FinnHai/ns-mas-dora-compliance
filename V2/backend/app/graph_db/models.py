"""Graph-Modelle für MITRE ATT&CK."""
from dataclasses import dataclass


@dataclass
class Tactic:
    """MITRE ATT&CK Taktik."""

    id: str
    name: str
    short_name: str


@dataclass
class Technique:
    """MITRE ATT&CK Technik."""

    id: str
    name: str
    tactic_ids: list[str]
