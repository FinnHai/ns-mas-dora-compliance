"""Graph-Nodes für MSEL-Workflows (lazy imports)."""


def __getattr__(name: str):
    """Lazy import (generator lädt LangChain)."""
    if name == "generate_step":
        from app.graph.nodes.generator import generate_step
        return generate_step
    if name == "validate_step":
        from app.graph.nodes.validator import validate_step
        return validate_step
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["generate_step", "validate_step"]
