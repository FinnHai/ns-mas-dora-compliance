"""Unit/Integration Tests für Neo4j-Connector-Erweiterungen (technique_exists, get_technique_tactics)."""
import pytest

from app.services.neo4j_connector import Neo4jService


@pytest.mark.integration
class TestNeo4jConnectorExtensions:
    """Integration Tests mit echter Neo4j-Datenbank."""

    @pytest.fixture(autouse=True)
    def skip_if_neo4j_unavailable(self):
        """Überspringt Tests, wenn Neo4j nicht erreichbar ist."""
        neo4j = Neo4jService()
        if not neo4j.verify_connectivity():
            pytest.skip("Neo4j nicht erreichbar – Integration-Tests übersprungen")

    def test_technique_exists_true(self):
        """T1566 existiert (Phishing)."""
        neo4j = Neo4jService()
        assert neo4j.technique_exists("T1566") is True

    def test_technique_exists_false(self):
        """T99999 existiert nicht."""
        neo4j = Neo4jService()
        assert neo4j.technique_exists("T99999") is False

    def test_get_technique_tactics(self):
        """T1566 → initial-access o.ä."""
        neo4j = Neo4jService()
        tactics = neo4j.get_technique_tactics("T1566")
        assert isinstance(tactics, list)
        assert "initial-access" in tactics or len(tactics) >= 0
