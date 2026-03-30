"""RAG-Komponenten für TTP Generator (lazy imports wegen Neo4j-Import-Hang auf macOS)."""


def __getattr__(name: str):
    """Lazy import um Neo4j/Retriever erst bei Bedarf zu laden."""
    if name == "NVDClient":
        from app.rag.nvd_client import NVDClient
        return NVDClient
    if name == "TechniqueRetriever":
        from app.rag.retriever import TechniqueRetriever
        return TechniqueRetriever
    if name == "rerank":
        from app.rag.reranker import rerank
        return rerank
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["NVDClient", "TechniqueRetriever", "rerank"]
