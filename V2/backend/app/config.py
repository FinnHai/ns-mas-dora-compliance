"""Pydantic Settings für Konfiguration."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env in Projektroot oder backend/
_env = next(
    (p for p in [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ] if p.exists()),
    Path.cwd() / ".env",
)


class Settings(BaseSettings):
    """Anwendungskonfiguration aus Umgebungsvariablen."""

    model_config = SettingsConfigDict(
        env_file=str(_env),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "dora-local-password"

    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_provider: str = "openai"  # "openai" oder "anthropic"
    anthropic_api_key: str = ""

    # Optional: Azure OpenAI
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None

    # Agent
    max_audit_iterations: int = 3

    # NS-MAS Pipeline (DR4 Reproduzierbarkeit)
    llm_temperature: float = 0.0
    llm_seed: int | None = 42

    # RAG (optional)
    rag_retriever_top_k: int = 40
    rag_reranker_top_k: int = 3
    nvd_api_key: str = ""


settings = Settings()
