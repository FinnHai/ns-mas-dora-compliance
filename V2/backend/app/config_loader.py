"""Lädt config/settings.yaml falls vorhanden."""
from pathlib import Path

_config_cache: dict | None = None


def load_yaml_config() -> dict:
    """Lädt config/settings.yaml. Gibt leeres Dict zurück wenn nicht vorhanden."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_paths = [
        Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml",
        Path.cwd() / "config" / "settings.yaml",
    ]
    for p in config_paths:
        if p.exists():
            try:
                import yaml
                with open(p, encoding="utf-8") as f:
                    _config_cache = yaml.safe_load(f) or {}
                return _config_cache
            except Exception:
                pass
    _config_cache = {}
    return _config_cache


def get_prompt(name: str) -> str:
    """Lädt Prompt-Template aus config/prompts/{name}.txt."""
    for base in [
        Path(__file__).resolve().parent.parent.parent / "config" / "prompts",
        Path.cwd() / "config" / "prompts",
    ]:
        p = base / f"{name}.txt"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""
