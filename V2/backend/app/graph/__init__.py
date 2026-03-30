"""Graph-Modul für MSEL-Validierung und -Generierung (lazy imports)."""


def __getattr__(name: str):
    """Lazy import um LangGraph erst bei Bedarf zu laden."""
    if name == "app":
        from app.graph.main import app
        return app
    if name == "run_scenario":
        from app.graph.main import run_scenario
        return run_scenario
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "run_scenario"]
