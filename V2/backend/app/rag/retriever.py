"""BM25 Retriever für TTP Generator."""
import logging
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.neo4j_connector import Neo4jService

logger = logging.getLogger(__name__)


class TechniqueRetriever:
    """BM25-basierter Retriever für MITRE ATT&CK Techniken."""

    def __init__(self, top_k: int = 40):
        self.top_k = top_k
        self._corpus: list[str] = []
        self._documents: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None

    def _build_corpus(self) -> None:
        """Lädt Techniken aus Neo4j und baut BM25-Index."""
        neo4j = Neo4jService()
        techniques = neo4j.get_all_techniques()
        self._documents = techniques
        self._corpus = []
        for t in techniques:
            text = f"{t.get('id', '')} {t.get('name', '')} {t.get('description', '')} " + " ".join(t.get("tactic_ids", []))
            self._corpus.append(text.lower())

        if self._corpus:
            tokenized = [doc.split() for doc in self._corpus]
            self._bm25 = BM25Okapi(tokenized)
            logger.info("RAG: Corpus aufgebaut, %d Techniken", len(self._documents))
        else:
            self._bm25 = None

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        """
        Gibt Top-K Techniken zur Query zurück (BM25).
        Query z.B.: "Techniques for initial access used by APT29"
        """
        if not self._corpus:
            self._build_corpus()

        if not self._bm25 or not self._documents:
            return []

        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: self.top_k]
        results = [self._documents[i] for i in top_indices if scores[i] > 0]
        logger.info("RAG: Query '%s' → %d Treffer", (query[:60] + "…") if len(query) > 60 else query, len(results))
        return results
