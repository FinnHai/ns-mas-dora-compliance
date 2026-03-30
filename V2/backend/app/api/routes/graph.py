"""Graph-Routen für Neo4j."""
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.graph import TacticsResponse, TechniqueResponse

router = APIRouter()


@router.get("/tactics", response_model=TacticsResponse)
async def get_tactics():
    """Liste aller verfügbaren MITRE ATT&CK Taktiken."""
    from app.graph_db.client import get_graph_client

    client = get_graph_client()
    tactics = await client.get_tactics()
    return TacticsResponse(tactics=tactics)


@router.get("/techniques", response_model=TechniqueResponse)
async def get_techniques():
    """Liste aller verfügbaren MITRE ATT&CK Techniken."""
    from app.graph_db.client import get_graph_client

    client = get_graph_client()
    techniques = await client.get_techniques()
    return TechniqueResponse(techniques=techniques)


class ValidatePathRequest(BaseModel):
    tactic_ids: list[str]


@router.post("/validate-path")
async def validate_path(request: ValidatePathRequest):
    """Validiert eine Taktik-Sequenz gegen den Reasoning Graph."""
    from app.graph_db.client import get_graph_client

    client = get_graph_client()
    result = await client.validate_tactic_sequence(request.tactic_ids)
    return result
