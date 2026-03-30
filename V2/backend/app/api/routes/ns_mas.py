"""NS-MAS Pipeline API-Routen.

LangGraph und Pipeline werden erst beim ersten Request geladen (Lazy-Load),
damit der Server schnell startet. Die erste /ns-mas/run-Anfrage dauert dann 30–60 Sek länger.
"""
import logging

from fastapi import APIRouter, HTTPException

from app.models.ns_mas_schemas import UserInput

logger = logging.getLogger(__name__)

router = APIRouter()

_ns_mas_app = None


def _get_app():
    """Lazy-Load: LangGraph + Pipeline erst beim ersten Request."""
    global _ns_mas_app
    if _ns_mas_app is None:
        logger.info("NS-MAS: Lade LangGraph + Pipeline (erster Request, ca. 30–60 Sek)...")
        from app.graph.ns_mas_pipeline import build_ns_mas_graph
        _ns_mas_app = build_ns_mas_graph()
        logger.info("NS-MAS: Pipeline geladen")
    return _ns_mas_app


def _state_to_dict(state) -> dict:
    """Konvertiert State in JSON-serialisierbares Dict."""
    if state is None:
        return {}
    if hasattr(state, "model_dump"):
        return state.model_dump()
    if isinstance(state, dict):
        out = {}
        for k, v in state.items():
            if hasattr(v, "model_dump"):
                out[k] = v.model_dump()
            elif isinstance(v, list):
                out[k] = [_state_to_dict(x) if hasattr(x, "model_dump") else x for x in v]
            elif isinstance(v, dict):
                out[k] = _state_to_dict(v)
            else:
                out[k] = v
        return out
    return dict(state) if hasattr(state, "items") else {}


@router.post("/run")
async def run_ns_mas_pipeline(
    request: UserInput,
    thread_id: str = "default",
    mode: str = "nsmas",
):
    """
    Startet die NS-MAS Pipeline: Planner → Generator → Auditor → Human Review → Synthesizer.
    mode=nsmas: Normale Korrekturschleife. mode=baseline: Auditor misst, aber keine Rückkopplung.
    Kann bei Human Review pausieren; dann /resume aufrufen.
    """
    app = _get_app()
    config = {"configurable": {"thread_id": thread_id}}
    baseline_mode = mode == "baseline"
    initial_state = {
        "user_input": request.model_dump() if hasattr(request, "model_dump") else request,
        "baseline_mode": baseline_mode,
    }
    req_dict = request.model_dump() if hasattr(request, "model_dump") else request
    logger.info(
        "NS-MAS Pipeline gestartet (thread_id=%s, mode=%s) – Org=%s, Threat=%s",
        thread_id,
        mode,
        req_dict.get("target_organization", "?"),
        req_dict.get("threat_profile", "?"),
    )
    try:
        result = await app.ainvoke(
            initial_state,
            config=config,
        )
        if hasattr(result, "interrupts") and result.interrupts:
            logger.info("NS-MAS: Human Review erforderlich – warte auf Freigabe")
            return {
                "status": "awaiting_approval",
                "message": "Human Review erforderlich",
                "interrupt": result.interrupts[0].value if result.interrupts else None,
                "state": _state_to_dict(getattr(result, "values", result)),
            }
        if isinstance(result, dict) and result.get("__interrupt__"):
            return {
                "status": "awaiting_approval",
                "message": "Human Review erforderlich",
                "interrupt": result["__interrupt__"][0].value if result["__interrupt__"] else None,
                "state": _state_to_dict(result),
            }
        logger.info("NS-MAS Pipeline abgeschlossen")
        return {"status": "completed", "result": _state_to_dict(result)}
    except Exception as e:
        logger.exception("NS-MAS Pipeline Fehler: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume_ns_mas_pipeline(
    approved: bool = True,
    thread_id: str = "default",
):
    """Setzt die Pipeline nach Human Review fort."""
    from langgraph.types import Command
    app = _get_app()
    config = {"configurable": {"thread_id": thread_id}}
    logger.info("NS-MAS: Resume (approved=%s, thread_id=%s)", approved, thread_id)
    try:
        result = await app.ainvoke(Command(resume=approved), config=config)
        return {"status": "completed", "result": _state_to_dict(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
