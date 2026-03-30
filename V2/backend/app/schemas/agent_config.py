"""Agent-Konfiguration für Generator und Auditor."""
from pydantic import BaseModel, Field

DEFAULT_KILL_CHAIN = [
    "reconnaissance",
    "resource-development",
    "initial-access",
    "execution",
    "persistence",
    "privilege-escalation",
    "defense-evasion",
    "credential-access",
    "discovery",
    "lateral-movement",
    "collection",
    "command-and-control",
    "exfiltration",
    "impact",
]


class AgentConfig(BaseModel):
    """Konfiguration für die Agenten (Generator, Auditor)."""

    max_audit_iterations: int = Field(default=5, ge=1, le=20)
    llm_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    min_events: int = Field(default=5, ge=1, le=50)
    max_events: int = Field(default=10, ge=1, le=50)
    kill_chain_order: list[str] = Field(default_factory=lambda: DEFAULT_KILL_CHAIN.copy())
    require_tactic_per_event: bool = True
    generator_system_prompt: str | None = None
