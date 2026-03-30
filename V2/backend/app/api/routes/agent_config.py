"""Agent-Konfigurations-Routen."""
from fastapi import APIRouter
from app.schemas.agent_config import AgentConfig

router = APIRouter()


@router.get("", response_model=AgentConfig)
async def get_agent_config():
    """Gibt die Standard-Agent-Konfiguration zurück."""
    return AgentConfig()
