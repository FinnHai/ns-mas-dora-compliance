"""NS-MAS Pydantic-Schemas für Agenten-Kommunikation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- UserInput → Scenario Planner ---
class UserInput(BaseModel):
    """Input für Scenario Planner."""

    target_organization: str = Field(..., description="Zielorganisation")
    scope_document: str | None = Field(default=None, description="Pfad oder Text des Scope-Dokuments")
    threat_profile: str = Field(..., description="z.B. APT29, Ransomware")
    additional_context: dict | None = Field(default=None)


# --- Scenario Planner → TTP Generator (Angriffsskizze) ---
class PhaseSketch(BaseModel):
    """High-Level-Phase einer Angriffsskizze."""

    phase: Literal["in", "through", "out"]
    target_assets: list[str] = Field(default_factory=list)
    high_level_goals: list[str] = Field(default_factory=list)


class AttackSketch(BaseModel):
    """Angriffsskizze vom Scenario Planner."""

    scenario_id: str
    target_organization: str
    threat_actor: str
    phases: list[PhaseSketch] = Field(default_factory=list)


# --- TTP Generator → KG Auditor ---
class TTPStep(BaseModel):
    """Einzelner TTP-Schritt."""

    step_id: int
    technique_id: str = Field(..., description="z.B. T1566.001")
    technique_name: str = ""
    tactic: str = ""
    description: str = ""
    cve_references: list[str] = Field(default_factory=list)
    temporal_relation_to_next: Literal["BEFORE", "SIM_OV", "CONCURRENT"] | None = None


class PhaseSteps(BaseModel):
    """Schritte einer Phase."""

    phase: Literal["in", "through", "out"]
    steps: list[TTPStep] = Field(default_factory=list)


class TTPScenario(BaseModel):
    """TTP-Sequenz vom TTP Generator."""

    scenario_id: str
    target_organization: str
    threat_actor: str
    phases: list[PhaseSteps] = Field(default_factory=list)

    def get_all_steps(self) -> list[tuple[tuple[int, str], TTPStep]]:
        """Liefert alle Schritte als (phase, step_index), TTPStep."""
        result: list[tuple[tuple[int, str], TTPStep]] = []
        phase_order = {"in": 0, "through": 1, "out": 2}
        for ps in sorted(self.phases, key=lambda p: phase_order.get(p.phase, 0)):
            for step in ps.steps:
                result.append(((phase_order.get(ps.phase, 0), ps.phase), step))
        return result

    def get_all_steps_flat(self) -> list[TTPStep]:
        """Liefert alle Schritte flach in Phasen-Reihenfolge."""
        return [s for _, s in self.get_all_steps()]


# --- KG Auditor → TTP Generator / Report Synthesizer ---
class StepValidation(BaseModel):
    """Validierung pro Schritt."""

    step_id: int
    technique_id: str
    id_exists: bool
    tactic_match: bool
    path_reachable: bool
    phase_conform: bool
    cve_valid: bool
    eligibility_score: int | None = None


class CorrectionHint(BaseModel):
    """Korrekturhinweis für TTP Generator."""

    step_id: int
    technique_id: str
    message: str
    suggested_technique_id: str | None = None


class ValidationReport(BaseModel):
    """Validierungsbericht vom KG Auditor."""

    passed: bool
    steps: list[StepValidation] = Field(default_factory=list)
    correction_hints: list[CorrectionHint] = Field(default_factory=list)
    auditor_iterations: int = 0
