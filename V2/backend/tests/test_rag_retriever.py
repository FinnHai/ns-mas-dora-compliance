"""Unit Tests für RAG Retriever (benötigt MOCK_NEO4J=1)."""
import pytest
from unittest.mock import patch, MagicMock

from app.rag.retriever import TechniqueRetriever


class TestTechniqueRetriever:
    def test_retriever_empty_corpus(self):
        """Leerer KG → leere Liste."""
        with patch("app.rag.retriever.Neo4jService") as MockNeo4j:
            mock_instance = MagicMock()
            mock_instance.get_all_techniques.return_value = []
            MockNeo4j.return_value = mock_instance

            retriever = TechniqueRetriever(top_k=40)
            result = retriever.retrieve("initial access phishing")

            assert result == []

    def test_retriever_with_mock_techniques(self):
        """Neo4jService.get_all_techniques gemockt, BM25-Retrieval."""
        mock_techniques = [
            {"id": "T1566", "name": "Phishing", "description": "Spear phishing", "tactic_ids": ["initial-access"]},
            {"id": "T1190", "name": "Exploit Public-Facing Application", "description": "Web exploit", "tactic_ids": ["initial-access"]},
            {"id": "T1059", "name": "Command and Scripting Interpreter", "description": "PowerShell", "tactic_ids": ["execution"]},
        ]
        with patch("app.rag.retriever.Neo4jService") as MockNeo4j:
            mock_instance = MagicMock()
            mock_instance.get_all_techniques.return_value = mock_techniques
            MockNeo4j.return_value = mock_instance

            retriever = TechniqueRetriever(top_k=40)
            result = retriever.retrieve("phishing initial access")

            assert len(result) > 0
            assert any(d["id"] == "T1566" for d in result)
