"""Unit Tests für KG Auditor (mit Mocks, benötigt MOCK_NEO4J=1)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.kg_auditor import run_kg_auditor
from app.models.ns_mas_schemas import PhaseSteps, TTPScenario, TTPStep


@pytest.fixture
def mock_neo4j():
    """Mock Neo4jService."""
    with patch("app.agents.kg_auditor.Neo4jService") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


@pytest.fixture
def mock_nvd():
    """Mock NVDClient."""
    with patch("app.agents.kg_auditor.NVDClient") as m:
        instance = MagicMock()
        instance.validate_cve.return_value = True
        m.return_value = instance
        yield instance


@pytest.mark.asyncio
async def test_kg_auditor_id_not_exists(mock_neo4j, mock_nvd):
    """technique_id T99999 → passed=False, correction_hint."""
    mock_neo4j.technique_exists.return_value = False
    mock_neo4j.get_technique_tactics.return_value = []

    ttp = TTPScenario(
        scenario_id="sc-1",
        target_organization="Org",
        threat_actor="APT29",
        phases=[
            PhaseSteps(phase="in", steps=[
                TTPStep(step_id=1, technique_id="T99999", tactic="initial-access"),
            ]),
        ],
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is False
    assert any("existiert nicht" in h.message for h in report.correction_hints)


@pytest.mark.asyncio
async def test_kg_auditor_path_invalid(mock_neo4j, mock_nvd):
    """validate_path False → passed=False."""
    mock_neo4j.technique_exists.return_value = True
    mock_neo4j.get_technique_tactics.return_value = ["initial-access"]
    mock_neo4j.validate_path.return_value = False

    ttp = TTPScenario(
        scenario_id="sc-1",
        target_organization="Org",
        threat_actor="APT29",
        phases=[
            PhaseSteps(phase="in", steps=[
                TTPStep(step_id=1, technique_id="T1566", tactic="initial-access"),
            ]),
        ],
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is False
    assert any("Pfad" in h.message for h in report.correction_hints)


@pytest.mark.asyncio
async def test_kg_auditor_duplicate_technique(mock_neo4j, mock_nvd):
    """Benachbarte gleiche technique_id → passed=False."""
    mock_neo4j.technique_exists.return_value = True
    mock_neo4j.get_technique_tactics.return_value = ["initial-access"]
    mock_neo4j.validate_path.return_value = True

    ttp = TTPScenario(
        scenario_id="sc-1",
        target_organization="Org",
        threat_actor="APT29",
        phases=[
            PhaseSteps(phase="in", steps=[
                TTPStep(step_id=1, technique_id="T1566", tactic="initial-access"),
                TTPStep(step_id=2, technique_id="T1566", tactic="initial-access"),
            ]),
        ],
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is False
    assert any("Duplikat" in h.message for h in report.correction_hints)


@pytest.mark.asyncio
async def test_kg_auditor_valid_scenario(mock_neo4j, mock_nvd):
    """Alle Prüfungen OK → passed=True."""
    mock_neo4j.technique_exists.return_value = True
    mock_neo4j.get_technique_tactics.return_value = ["initial-access"]
    mock_neo4j.validate_path.return_value = True

    ttp = TTPScenario(
        scenario_id="sc-1",
        target_organization="Org",
        threat_actor="APT29",
        phases=[
            PhaseSteps(phase="in", steps=[
                TTPStep(step_id=1, technique_id="T1566", tactic="initial-access"),
            ]),
        ],
    )

    report = await run_kg_auditor(ttp)

    assert report.passed is True
    assert len(report.correction_hints) == 0
