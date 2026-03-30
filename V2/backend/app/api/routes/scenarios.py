"""Szenario-Routen."""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.schemas.scenarios import ScenarioGenerateRequest, ScenarioResponse, ScenarioStatus

router = APIRouter()

# In-Memory Store für Prototyp (später durch DB ersetzen)
_scenarios: dict[str, dict] = {}


def _seed_example_scenario() -> None:
    """Fügt ein Beispiel-Szenario beim Start hinzu."""
    example = {
        "id": "example-ransomware-001",
        "status": "completed",
        "events": [
            {"order": 1, "description": "[IN] Phishing-E-Mail mit schädlichem Anhang an Mitarbeiter", "tactic_id": "initial-access", "technique_id": "T1566", "timestamp_offset_hours": 1.0},
            {"order": 2, "description": "[IN] Makro führt Ransomware-Payload aus", "tactic_id": "execution", "technique_id": "T1059", "timestamp_offset_hours": 2.0},
            {"order": 3, "description": "[THROUGH] Persistenz durch Scheduled Task", "tactic_id": "persistence", "technique_id": "T1053", "timestamp_offset_hours": 4.0},
            {"order": 4, "description": "[THROUGH] Credential Dumping (LSASS)", "tactic_id": "credential-access", "technique_id": "T1003", "timestamp_offset_hours": 8.0},
            {"order": 5, "description": "[THROUGH] Laterale Bewegung zum Dateiserver", "tactic_id": "lateral-movement", "technique_id": "T1021", "timestamp_offset_hours": 12.0},
            {"order": 6, "description": "[OUT] Datenverschlüsselung und Ransom-Note", "tactic_id": "impact", "technique_id": "T1486", "timestamp_offset_hours": 16.0},
        ],
        "threat_context": "Ransomware-Angriff über Phishing: Kriminelle Gruppe nutzt E-Mail-Kampagne, um Ransomware in ein Finanzinstitut einzuschleusen. Ziele: ERP-System, Dateiserver, E-Mail.",
        "audit_feedback": ["Flag achieved - Szenario erfolgreich abgeschlossen."],
        "error_message": None,
        "validation": {
            "overall_valid": True,
            "action_alignment_score": 1.0,
            "results": [
                {"order": i, "is_valid": True, "message": "OK", "suggested_tactic_id": None, "suggested_technique_id": None}
                for i in range(1, 7)
            ],
            "sequence_valid": True,
            "sequence_message": "",
            "tactic_coverage": 1.0,
            "technique_validity": 1.0,
            "technique_mapping": 1.0,
        },
        "execution_trace": [
            {"step": "generator", "iteration": 1, "timestamp": datetime.utcnow().isoformat() + "Z", "detail": "[IN] T1566: Phishing-E-Mail...", "payload": {"technique_id": "T1566", "phase": "IN"}},
            {"step": "validator", "iteration": 1, "timestamp": datetime.utcnow().isoformat() + "Z", "detail": "Validiert", "payload": {"approved": True}},
        ],
    }
    _scenarios[example["id"]] = example


# Beispiel-Szenario beim Modul-Import laden
_seed_example_scenario()


@router.post("/generate", response_model=ScenarioResponse)
async def generate_scenario(
    request: ScenarioGenerateRequest,
    baseline: bool = Query(
        default=False,
        description="Wenn True: Baseline-Modus ohne Graph-Validierung (reines LLM)",
    ),
    include_validation: bool = Query(
        default=True,
        description="Wenn True: Quantitative Evaluation (Action Alignment Score) in Response",
    ),
):
    """Startet die Szenario-Generierung mit Kontext.

    - Standard: Neuro-symbolisch (LLM + Knowledge Graph Validierung)
    - baseline=true: Nur LLM ohne Graph-Validierung (fuer Vergleichsevaluation)
    """
    from app.services.scenario_service import scenario_service

    result = await scenario_service.generate(
        request, use_graph_validation=not baseline, include_validation=include_validation
    )
    _scenarios[result.id] = result.model_dump()
    return result


@router.post("/generate/stream")
async def generate_scenario_stream(
    request: ScenarioGenerateRequest,
    baseline: bool = Query(
        default=False,
        description="Wenn True: Baseline-Modus ohne Graph-Validierung",
    ),
    include_validation: bool = Query(
        default=True,
        description="Wenn True: Quantitative Evaluation in Response",
    ),
):
    """Streamt die Szenario-Generierung mit Live-Logs (Server-Sent Events)."""
    from app.services.scenario_service import scenario_service

    async def event_generator():
        try:
            async for event in scenario_service.generate_stream(
                request,
                use_graph_validation=not baseline,
                include_validation=include_validation,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "complete" and "result" in event:
                    _scenarios[event["result"]["id"]] = event["result"]
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str):
    """Ruft Status und Ergebnis eines Szenarios ab."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail="Szenario nicht gefunden")
    return _scenarios[scenario_id]


@router.get("/")
async def list_scenarios():
    """Listet alle Szenarien (Übersicht). Neueste zuerst."""
    scenarios = list(_scenarios.values())
    # Neueste zuerst (Beispiel hat feste ID, neu generierte kommen ans Ende)
    scenarios.reverse()
    return {"scenarios": scenarios}
