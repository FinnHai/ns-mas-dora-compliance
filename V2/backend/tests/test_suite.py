"""
Umfassende pytest Test-Suite für den DORA-Agenten.

Kategorien:
1. Validator Logic (Unit Tests)
2. Neo4j Integration (Integration Tests)
3. MSEL-Struktur (Model Tests)
4. System-Sanity
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from pydantic import ValidationError


# =============================================================================
# 1. Validator Logic (Unit Tests)
# =============================================================================


class TestValidatorLogic:
    """Unit Tests für die Validator-Logik."""

    def test_is_destructive_action_wipe_disk(self):
        """'I will wipe the disk' muss True sein."""
        from app.graph.nodes.validator import _is_destructive_action

        assert _is_destructive_action("I will wipe the disk") is True

    def test_is_destructive_action_analyze_disk(self):
        """'I will analyze the disk' muss False sein."""
        from app.graph.nodes.validator import _is_destructive_action

        assert _is_destructive_action("I will analyze the disk") is False

    def test_validate_step_returns_error_when_neo4j_returns_false(self):
        """Validator gibt validation_error, wenn Neo4j validate_path False liefert."""
        from app.graph.nodes.validator import validate_step

        fake_state = {
            "msel_items": [
                {"technique_id": "T1592", "action_description": "Scan network"},
                {
                    "technique_id": "T1566",
                    "action_description": "Analyze disk",
                    "target": "server",
                    "success_criteria": "access",
                },
            ],
            "target_cif": None,
        }

        mock_neo4j = MagicMock()
        mock_neo4j.validate_path.return_value = False
        mock_neo4j.get_technique_details.return_value = {}

        with patch("app.graph.nodes.validator.Neo4jService", return_value=mock_neo4j):
            result = validate_step(fake_state)

        assert result.get("validation_error") is not None
        assert "impossible path" in (result.get("validation_error") or "").lower()
        assert len(result.get("msel_items", [])) == 1


# =============================================================================
# 2. Neo4j Integration (Integration Tests)
# =============================================================================


@pytest.mark.integration
class TestNeo4jIntegration:
    """Integration Tests mit echter Neo4j-Datenbank."""

    @pytest.fixture(autouse=True)
    def skip_if_neo4j_unavailable(self):
        """Überspringt Tests, wenn Neo4j nicht erreichbar ist."""
        from app.services.neo4j_connector import Neo4jService

        neo4j = Neo4jService()
        if not neo4j.verify_connectivity():
            pytest.skip("Neo4j nicht erreichbar – Integration-Tests übersprungen")

    def test_validate_path_phishing_to_valid_accounts(self):
        """Phishing (T1566) -> Valid Accounts (T1078) muss True sein."""
        from app.services.neo4j_connector import Neo4jService

        neo4j = Neo4jService()
        assert neo4j.validate_path("T1566", "T1078") is True

    def test_validate_path_exfiltration_to_phishing_false(self):
        """Exfiltration (T1048) -> Phishing (T1566) muss False sein (rückwärts in Kill-Chain)."""
        from app.services.neo4j_connector import Neo4jService

        neo4j = Neo4jService()
        assert neo4j.validate_path("T1048", "T1566") is False

    def test_validate_path_loop_fix(self):
        """validate_path('T1071', 'T1071') muss True sein (Loop-Fix ohne DB-Fehler)."""
        from app.services.neo4j_connector import Neo4jService

        neo4j = Neo4jService()
        assert neo4j.validate_path("T1071", "T1071") is True


# =============================================================================
# 3. MSEL-Struktur (Model Tests)
# =============================================================================


class TestMSELStructure:
    """Model Tests für MSELItem."""

    @pytest.fixture
    def valid_msel_kwargs(self):
        """Minimale gültige KWargs für MSELItem (ohne phase/technique_id)."""
        return {
            "id": uuid4(),
            "step_index": 1,
            "scenario_id": "scenario-1",
            "time_planned": "09:00",
            "source": "attacker",
            "target": "server",
            "action_description": "Test action",
            "tactic": "initial-access",
            "tools_used": [],
            "security_goal": "CONFIDENTIALITY",
            "success_criteria": "access",
            "result": "PLANNED",
        }

    def test_msel_item_missing_phase_raises(self, valid_msel_kwargs):
        """MSELItem mit fehlender Phase muss ValidationError werfen."""
        from app.models.msel import MSELItem

        valid_msel_kwargs["technique_id"] = "T1566"
        # phase bewusst nicht gesetzt – required field fehlt

        with pytest.raises(ValidationError):
            MSELItem(**valid_msel_kwargs)

    def test_msel_item_invalid_technique_id_xyz(self, valid_msel_kwargs):
        """technique_id 'XYZ' muss ValidationError werfen (muss mit T starten)."""
        from app.models.msel import MSELItem
        from app.models.enums import Phase

        valid_msel_kwargs["phase"] = Phase.IN
        valid_msel_kwargs["technique_id"] = "XYZ"

        with pytest.raises(ValidationError) as exc_info:
            MSELItem(**valid_msel_kwargs)

        assert "technique_id" in str(exc_info.value).lower() or "T" in str(exc_info.value)

    def test_msel_item_technique_id_txyz_accepted(self, valid_msel_kwargs):
        """technique_id 'TXYZ' wird akzeptiert (Format stimmt)."""
        from app.models.msel import MSELItem
        from app.models.enums import Phase

        valid_msel_kwargs["phase"] = Phase.IN
        valid_msel_kwargs["technique_id"] = "TXYZ"

        item = MSELItem(**valid_msel_kwargs)
        assert item.technique_id == "TXYZ"


# =============================================================================
# 4. System-Sanity
# =============================================================================


class TestSystemSanity:
    """System-Sanity-Checks."""

    @pytest.mark.slow
    def test_main_graph_compiles(self):
        """MainGraph muss ohne Fehler kompilieren (langsam wegen LangGraph)."""
        from app.graph.main import app

        assert app is not None
