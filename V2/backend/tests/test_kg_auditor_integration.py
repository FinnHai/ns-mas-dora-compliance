"""
KG Auditor Integration Tests – gegen echten Neo4j (keine Mocks).

Erwartung:
- 2a: Fake technique_id T9999 + CVE-9999-9999 → id_exists=False, cve_valid=False
- 2b: Phasenreihenfolge verletzt (in → out → in) → phase_conform=False

Voraussetzung: Neo4j läuft (bolt://localhost:7688 oder NEO4J_URI).
"""
from __future__ import annotations

import pytest

from app.agents.kg_auditor import run_kg_auditor
from app.models.ns_mas_schemas import PhaseSteps, TTPScenario, TTPStep
from app.services.neo4j_connector import Neo4jService


def _neo4j_available() -> bool:
    try:
        return Neo4jService().verify_connectivity()
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _neo4j_available(), reason="Neo4j nicht erreichbar")
@pytest.mark.asyncio
async def test_kg_auditor_fake_technique_id_and_cve():
    """
    Fake technique_id T9999 und CVE-9999-9999 → Prüfschritt 1 (ID-Existenz) FAIL,
    Prüfschritt 5 (CVE-Validität) FAIL.
    """
    fake_step = TTPStep(
        step_id=1,
        technique_id="T9999",
        technique_name="Fake Technique",
        tactic="Initial Access",
        description="Test",
        cve_references=["CVE-9999-9999"],
    )
    ttp = TTPScenario(
        scenario_id="sc-fake",
        target_organization="Test Org",
        threat_actor="APT29",
        phases=[PhaseSteps(phase="in", steps=[fake_step])],
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is False
    # Prüfschritt 1: ID existiert nicht
    assert any("existiert nicht" in h.message for h in report.correction_hints)
    step_val = next((s for s in report.steps if s.step_id == 1), None)
    assert step_val is not None
    assert step_val.id_exists is False
    # Prüfschritt 5: CVE ungültig (NVD lehnt CVE-9999-9999 ab)
    assert step_val.cve_valid is False


@pytest.mark.integration
@pytest.mark.skipif(not _neo4j_available(), reason="Neo4j nicht erreichbar")
@pytest.mark.skip(reason="TTPScenario.get_all_steps_flat() sortiert Phasen immer in→through→out; "
    "Phase 'out' vor 'in' ist mit dem Modell nicht darstellbar.")
@pytest.mark.asyncio
async def test_kg_auditor_phase_order_violation():
    """
    Phasenreihenfolge verletzt: in → out → in (Rücksprung).
    Prüfschritt 4 (Phasenkonformität) = FAIL.
    Hinweis: Mit TTPScenario nicht testbar, da Phasen immer sortiert werden.
    """
    steps = [
        PhaseSteps(
            phase="in",
            steps=[
                TTPStep(
                    step_id=1,
                    technique_id="T1566",
                    tactic="initial-access",
                    description="Initial Access",
                ),
            ],
        ),
        PhaseSteps(
            phase="out",
            steps=[
                TTPStep(
                    step_id=2,
                    technique_id="T1048",
                    tactic="exfiltration",
                    description="Exfiltration",
                ),
            ],
        ),
        PhaseSteps(
            phase="in",
            steps=[
                TTPStep(
                    step_id=3,
                    technique_id="T1190",
                    tactic="initial-access",
                    description="Rücksprung in Phase in",
                ),
            ],
        ),
    ]
    ttp = TTPScenario(
        scenario_id="sc-phase",
        target_organization="Test Org",
        threat_actor="APT29",
        phases=steps,
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is False
    assert any("Phasenreihenfolge" in h.message for h in report.correction_hints)
    # Schritt 3 hat phase_conform=False (in nach out)
    step3 = next((s for s in report.steps if s.step_id == 3), None)
    assert step3 is not None
    assert step3.phase_conform is False
