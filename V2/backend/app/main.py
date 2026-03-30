"""FastAPI-Einstieg für die DORA-Szenario-Plattform."""
import json
import logging
import sys
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse

def _log(msg: str) -> None:
    print(f"[Startup] {msg}", flush=True)

_log("Python gestartet")
_log("Lade FastAPI...")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
_log("FastAPI geladen")

_log("Lade API-Routen...")
from app.api.routes import scenarios, validation, graph, agent_config, evaluation, ns_mas
_log("  scenarios, validation, graph, agent_config, evaluation, ns_mas OK")
_log("  (NS-MAS Pipeline wird beim ersten /ns-mas/run-Request geladen – spart Startzeit)")

# Logging für Live-Logs während der Generierung (Generator, Validator)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="DORA Szenario-Plattform",
    description="Neuro-symbolisches Multi-Agenten-System zur Unterstützung der Szenario-Entwicklung im Kontext von DORA",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router, prefix="/scenarios", tags=["scenarios"])
app.include_router(validation.router, prefix="/validation", tags=["validation"])
app.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(agent_config.router, prefix="/agent-config", tags=["agent-config"])
app.include_router(ns_mas.router, prefix="/ns-mas", tags=["ns-mas"])
_log("Router registriert")


@app.on_event("startup")
async def startup_log():
    _log("Uvicorn-Server bereit – warte auf Anfragen")
    _log("Health-Check: http://localhost:8000/health")
    _log("NS-MAS API: http://localhost:8000/ns-mas/run")
    _log("Smoke-Results: http://localhost:8000/smoke-results")
    _log("Eval-N10: http://localhost:8000/eval-n10")
    _log("Generierte: http://localhost:8000/evaluation/generated")


@app.get("/health")
def health_check():
    """Health-Check für Liveness."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Leitet zur Frontend-Oberfläche weiter."""
    return RedirectResponse(url="http://localhost:5173/", status_code=302)


# Smoke-Test-Ergebnisse Dashboard
_BACKEND_DIR = Path(__file__).resolve().parent.parent


@app.get("/smoke-results")
def smoke_results_dashboard():
    """HTML-Dashboard für Smoke-Test-Ergebnisse."""
    path = _BACKEND_DIR / "evaluation" / "smoke" / "smoke_results_dashboard.html"
    if not path.exists():
        return JSONResponse({"error": "Dashboard nicht gefunden"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/smoke-results/data")
def smoke_results_data():
    """Lädt alle full_run_*_debug.json dynamisch."""
    results = []
    smoke_dir = _BACKEND_DIR / "evaluation" / "smoke"
    if not smoke_dir.exists():
        return results
    for p in sorted(smoke_dir.glob("full_run_*_debug.json")):
        try:
            with open(p, encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results


@app.get("/eval-n10")
def eval_n10_dashboard():
    """HTML-Dashboard für Eval N10 Ergebnisse."""
    path = _BACKEND_DIR / "evaluation" / "n10" / "eval_n10_dashboard.html"
    if not path.exists():
        return JSONResponse({"error": "Dashboard nicht gefunden"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/eval-n10/data")
def eval_n10_data():
    """Lädt eval_n10_results.json dynamisch."""
    path = _BACKEND_DIR / "evaluation" / "n10" / "eval_n10_results.json"
    if not path.exists():
        return JSONResponse({"metadata": {}, "runs": []})
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return JSONResponse({"metadata": {}, "runs": []})


# ---- Generierte Szenarien (Archiv: qualitative Eval./Interview) ----
_GENERATED_DIR = (
    _BACKEND_DIR / "evaluation" / "entwicklung_archiv" / "interview"
)


def _discover_generated_scenarios():
    scenarios = []
    if not _GENERATED_DIR.exists():
        return scenarios
    for p in sorted(_GENERATED_DIR.glob("*_metadata.json")):
        base = p.stem.replace("_metadata", "")
        if "debug" in base:
            continue
        meta = {}
        try:
            with open(p, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass
        label = base.replace("interview_", "").replace("_", " ").upper()
        if "baseline" in base:
            label = f"{label} (Baseline)"
        ttp_path = _GENERATED_DIR / f"{base}_ttp.json"
        narrative_path = _GENERATED_DIR / f"{base}_narrative.txt"
        validation_path = _GENERATED_DIR / f"{base}_validation.json"
        scenarios.append({
            "id": base,
            "label": label,
            "mode": meta.get("mode", "nsmas"),
            "timestamp": meta.get("timestamp", ""),
            "elapsed_seconds": meta.get("elapsed_seconds"),
            "validation_passed": meta.get("validation_passed"),
            "auditor_iterations": meta.get("auditor_iterations"),
            "has_ttp": ttp_path.exists(),
            "has_narrative": narrative_path.exists(),
            "has_validation": validation_path.exists(),
        })
    return scenarios


@app.get("/evaluation/generated")
def list_generated_scenarios():
    """Listet generierte Szenarien aus evaluation/entwicklung_archiv/interview."""
    return {"scenarios": _discover_generated_scenarios()}


@app.get("/evaluation/generated/{scenario_id}")
def get_generated_scenario(scenario_id: str):
    """Lädt ein generiertes Szenario (TTP, Narrative, Validation)."""
    from fastapi import HTTPException

    base = scenario_id.replace("_metadata", "")
    meta_path = _GENERATED_DIR / f"{base}_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Szenario nicht gefunden")
    result = {"id": base, "metadata": {}, "ttp": None, "narrative": "", "validation": None, "sketch": None}
    for key, ext, loader in [
        ("metadata", "_metadata.json", lambda f: json.load(f)),
        ("ttp", "_ttp.json", lambda f: json.load(f)),
        ("validation", "_validation.json", lambda f: json.load(f)),
        ("sketch", "_sketch.json", lambda f: json.load(f)),
    ]:
        path = _GENERATED_DIR / f"{base}{ext}"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    result[key] = loader(f)
            except Exception:
                pass
    narrative_path = _GENERATED_DIR / f"{base}_narrative.txt"
    if narrative_path.exists():
        try:
            with open(narrative_path, encoding="utf-8") as f:
                result["narrative"] = f.read()
        except Exception:
            pass
    return result
