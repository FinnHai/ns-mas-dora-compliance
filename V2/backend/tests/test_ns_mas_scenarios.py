"""
NS-MAS Pipeline Test-Szenarien.

Testet die Pipeline über die API mit verschiedenen UserInput-Szenarien.
Agenten werden gemockt – keine OpenAI/Neo4j nötig.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.ns_mas_schemas import (
    AttackSketch,
    PhaseSketch,
    PhaseSteps,
    TTPScenario,
    TTPStep,
    UserInput,
    ValidationReport,
)


# --- Test-Szenarien (UserInput) ---
SCENARIO_APT29 = {
    "target_organization": "Finanzinstitut AG",
    "threat_profile": "APT29",
    "scope_document": "Kritische Infrastruktur Bankensektor",
}

SCENARIO_RANSOMWARE = {
    "target_organization": "Krankenhausverbund Nord",
    "threat_profile": "Ransomware-as-a-Service",
    "scope_document": None,
}

SCENARIO_INSIDER = {
    "target_organization": "Tech-Startup GmbH",
    "threat_profile": "Insider Threat",
    "scope_document": "Cloud-Infrastruktur AWS",
}

SCENARIO_MINIMAL = {
    "target_organization": "Test-Org",
    "threat_profile": "Generic Adversary",
}


def _make_attack_sketch(org: str, actor: str, scenario_id: str | None = None) -> AttackSketch:
    return AttackSketch(
        scenario_id=scenario_id or str(uuid.uuid4()),
        target_organization=org,
        threat_actor=actor,
        phases=[
            PhaseSketch(phase="in", target_assets=["Mail-Server"], high_level_goals=["Initial Access"]),
            PhaseSketch(phase="through", target_assets=["AD"], high_level_goals=["Lateral Movement"]),
            PhaseSketch(phase="out", target_assets=[], high_level_goals=["Exfiltration"]),
        ],
    )


def _make_ttp_scenario(org: str, actor: str, scenario_id: str) -> TTPScenario:
    return TTPScenario(
        scenario_id=scenario_id,
        target_organization=org,
        threat_actor=actor,
        phases=[
            PhaseSteps(
                phase="in",
                steps=[
                    TTPStep(step_id=1, technique_id="T1566.001", technique_name="Phishing", tactic="initial-access", description="Spear Phishing"),
                ],
            ),
            PhaseSteps(
                phase="through",
                steps=[
                    TTPStep(step_id=2, technique_id="T1078", technique_name="Valid Accounts", tactic="persistence", description="Domain Account"),
                ],
            ),
            PhaseSteps(
                phase="out",
                steps=[
                    TTPStep(step_id=3, technique_id="T1048", technique_name="Exfiltration Over Alternative Protocol", tactic="exfiltration", description="DNS"),
                ],
            ),
        ],
    )


def _make_validation_report(passed: bool) -> ValidationReport:
    return ValidationReport(passed=passed, steps=[], correction_hints=[], auditor_iterations=0)


@pytest.fixture(autouse=True)
def reset_ns_mas_app():
    """Stellt sicher, dass der Graph pro Test neu gebaut wird (mit Mocks)."""
    import app.api.routes.ns_mas as ns_mas_route
    ns_mas_route._ns_mas_app = None
    yield
    ns_mas_route._ns_mas_app = None


@pytest.fixture
def mock_agents():
    """Mockt alle Agenten für schnelle Tests ohne LLM/Neo4j."""
    with (
        patch("app.graph.ns_mas_pipeline.run_scenario_planner", new_callable=AsyncMock) as m_planner,
        patch("app.graph.ns_mas_pipeline.run_ttp_generator", new_callable=AsyncMock) as m_ttp,
        patch("app.graph.ns_mas_pipeline.run_kg_auditor", new_callable=AsyncMock) as m_auditor,
        patch("app.graph.ns_mas_pipeline.run_report_synthesizer", new_callable=AsyncMock) as m_report,
    ):
        def _planner_side_effect(user_input):
            if isinstance(user_input, dict):
                org = user_input.get("target_organization", "Org")
                profile = user_input.get("threat_profile", "Actor")
            else:
                org = user_input.target_organization
                profile = user_input.threat_profile
            return _make_attack_sketch(org, profile)

        def _ttp_side_effect(sketch, **kwargs):
            sid = sketch.scenario_id if hasattr(sketch, "scenario_id") else str(uuid.uuid4())
            org = sketch.target_organization if hasattr(sketch, "target_organization") else "Org"
            actor = sketch.threat_actor if hasattr(sketch, "threat_actor") else "Actor"
            return _make_ttp_scenario(org, actor, sid)

        def _auditor_side_effect(ttp, **kwargs):
            return _make_validation_report(passed=True)

        def _report_side_effect(ttp, user_input):
            return {
                "msel": {"scenario_id": ttp.scenario_id, "events": []},
                "narrative": f"Test-MSEL für {ttp.scenario_id}",
            }

        m_planner.side_effect = _planner_side_effect
        m_ttp.side_effect = _ttp_side_effect
        m_auditor.side_effect = _auditor_side_effect
        m_report.side_effect = _report_side_effect
        yield {"planner": m_planner, "ttp": m_ttp, "auditor": m_auditor, "report": m_report}


@pytest.mark.asyncio
async def test_scenario_apt29_full_pipeline(client, mock_agents):
    """Szenario: APT29 gegen Finanzinstitut – vollständiger Durchlauf inkl. Human Review."""
    res = await client.post("/ns-mas/run", json=SCENARIO_APT29, params={"thread_id": "test-apt29"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "awaiting_approval"
    assert "state" in data

    res2 = await client.post("/ns-mas/resume", params={"approved": "true", "thread_id": "test-apt29"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "completed"
    assert "result" in data2
    result = data2["result"]
    assert "report" in result
    assert "msel" in result["report"]
    assert "narrative" in result["report"]


@pytest.mark.asyncio
async def test_scenario_ransomware_full_pipeline(client, mock_agents):
    """Szenario: Ransomware gegen Krankenhaus – Pipeline durchläuft alle Schritte."""
    res = await client.post("/ns-mas/run", json=SCENARIO_RANSOMWARE, params={"thread_id": "test-ransomware"})
    assert res.status_code == 200
    assert res.json()["status"] == "awaiting_approval"

    res2 = await client.post("/ns-mas/resume", params={"approved": "true", "thread_id": "test-ransomware"})
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_scenario_insider_with_scope(client, mock_agents):
    """Szenario: Insider Threat mit Scope-Dokument."""
    res = await client.post("/ns-mas/run", json=SCENARIO_INSIDER, params={"thread_id": "test-insider"})
    assert res.status_code == 200
    assert res.json()["status"] == "awaiting_approval"

    res2 = await client.post("/ns-mas/resume", params={"approved": "true", "thread_id": "test-insider"})
    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] == "completed"
    # Scenario Planner sollte mit scope_document aufgerufen worden sein
    mock_agents["planner"].assert_called_once()


@pytest.mark.asyncio
async def test_scenario_minimal_input(client, mock_agents):
    """Szenario: Minimaler Input – nur Pflichtfelder."""
    res = await client.post("/ns-mas/run", json=SCENARIO_MINIMAL, params={"thread_id": "test-minimal"})
    assert res.status_code == 200
    assert res.json()["status"] == "awaiting_approval"

    res2 = await client.post("/ns-mas/resume", params={"approved": "true", "thread_id": "test-minimal"})
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_auditor_retry_loop(client, mock_agents):
    """Szenario: KG Auditor schlägt 2x fehl, dann Pass – prüft Retry-Logik."""
    call_count = [0]

    async def auditor_side_effect(ttp, **kwargs):
        call_count[0] += 1
        return _make_validation_report(passed=call_count[0] >= 3)

    mock_agents["auditor"].side_effect = auditor_side_effect

    res = await client.post("/ns-mas/run", json=SCENARIO_APT29, params={"thread_id": "test-retry"})
    assert res.status_code == 200
    assert res.json()["status"] == "awaiting_approval"

    res2 = await client.post("/ns-mas/resume", params={"approved": "true", "thread_id": "test-retry"})
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"
    assert call_count[0] >= 3, "Auditor sollte mind. 3x aufgerufen worden sein (2x FAIL, 1x PASS)"


@pytest.mark.asyncio
async def test_resume_rejected(client, mock_agents):
    """Szenario: Human Review abgelehnt – Pipeline endet ohne Report Synthesizer."""
    res = await client.post("/ns-mas/run", json=SCENARIO_APT29, params={"thread_id": "test-reject"})
    assert res.status_code == 200
    assert res.json()["status"] == "awaiting_approval"

    res2 = await client.post("/ns-mas/resume", params={"approved": "false", "thread_id": "test-reject"})
    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] == "completed"
    # Bei Ablehnung: report_synthesizer wird nicht aufgerufen (routing zu END)
    mock_agents["report"].assert_not_called()
