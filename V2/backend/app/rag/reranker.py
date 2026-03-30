"""Re-Ranker für RAG: Top-40 → Top-3 (Cross-Encoder)."""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_cross_encoder = None


def _get_cross_encoder():
    """Lazy load Cross-Encoder für Re-Ranking."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except ImportError:
            logger.debug("Cross-Encoder nicht verfügbar, nutze Reihenfolge.")
    return _cross_encoder


def _doc_to_text(doc: dict[str, Any]) -> str:
    """Konvertiert Technik-Dokument zu Text für Cross-Encoder."""
    return (
        f"{doc.get('id', '')} {doc.get('name', '')} {doc.get('description', '')} "
        + " ".join(doc.get("tactic_ids", []))
    )


def rerank(
    documents: list[dict[str, Any]],
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Filtert Top-K aus den Retriever-Ergebnissen.
    Nutzt Cross-Encoder (ms-marco-MiniLM-L-6-v2) für semantische Relevanz.
    Fallback: Übernahme der Retriever-Reihenfolge.
    """
    k = top_k or settings.rag_reranker_top_k
    if not documents:
        return []

    ce = _get_cross_encoder()
    if ce is None:
        return documents[:k]

    try:
        pairs = [(query, _doc_to_text(d)) for d in documents]
        scores = ce.predict(pairs)
        indexed = list(zip(scores, documents, range(len(documents))))
        indexed.sort(key=lambda x: (x[0], -x[2]), reverse=True)
        return [d for _, d, _ in indexed[:k]]
    except Exception as e:
        logger.warning("Cross-Encoder Re-Ranking fehlgeschlagen: %s", e)
        return documents[:k]
