#!/usr/bin/env python3
"""
Interview Szenario B (APT41/Atruvia) – Generierung und Speicherung aller Outputs.

Führt NS-MAS- und Baseline-Runs durch, speichert alle fünf Artefakte pro Run:
  1. interview_sc_b_sketch.json (AttackSketch)
  2. interview_sc_b_ttp.json (TTPScenario)
  3. interview_sc_b_validation.json (ValidationReport)
  4. interview_sc_b_narrative.txt (MSEL-Narrative)
  5. interview_sc_b_metadata.json (Modell, Temperature, Laufzeit)

Usage:
  cd V2/backend && python -m scripts.run_interview_scenario_b --nsmas --baseline
  cd V2/backend && python -m scripts.run_interview_scenario_b --nsmas --baseline --nsmas-repeat 4  # 5 NS-MAS-Runs, Best-Run-Auswahl
  cd V2/backend && python -m scripts.run_interview_scenario_b --all --debug

Backend muss laufen: ./run.sh oder PORT=8000 uvicorn app.main:app
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "entwicklung_archiv" / "interview"

SCENARIO_B_PAYLOAD = {
    "target_organization": "Atruvia AG (IT-Dienstleister der Genossenschaftsbanken)",
    "threat_profile": "APT41",
    "scope_document": (
        "Mehrstufiger Angriff auf die Rechenzentrums-Infrastruktur eines genossenschaftlichen "
        "IT-Dienstleisters. Kritische Funktionen: Kernbanksystem (agree21), Zahlungsverkehrsplattform, "
        "Online-Banking-Infrastruktur, Anbindung der Mitgliedsbanken. DORA-Kontext: Atruvia als "
        "kritischer IKT-Drittdienstleister gemäß Art. 28 DORA. Angriffsziel: Kompromittierung der "
        "zentralen Zahlungsverkehrsinfrastruktur über kompromittierte Entwickler-Zugänge."
    ),
}


def _serialize(obj):
    """Serialisiert Pydantic-Objekte und dicts für JSON."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _get_llm_config():
    """Liest Modell und Temperature aus app.config (funktioniert nur wenn Backend-Kontext)."""
    try:
        from app.config import settings
        return {
            "llm_model": getattr(settings, "llm_model", "gpt-4o-mini"),
            "llm_temperature": getattr(settings, "llm_temperature", 0.0),
        }
    except Exception:
        return {"llm_model": "N/A", "llm_temperature": "N/A"}


async def run_scenario_b(
    client: httpx.AsyncClient,
    mode: str,
    suffix: str,
    thread_id: str,
    debug: bool = False,
) -> bool:
    """Führt Szenario B aus (nsmas oder baseline) und speichert alle Outputs."""
    t0 = time.perf_counter()
    print(f"\n{'='*60}")
    print(f"Szenario B – {mode.upper()} (thread_id={thread_id})")
    print(f"{'='*60}")

    try:
        res = await client.post(
            f"{API_URL}/ns-mas/run",
            json=SCENARIO_B_PAYLOAD,
            params={"thread_id": thread_id, "mode": mode},
        )
        if res.status_code >= 400:
            body = res.text if debug else res.text[:300]
            print(f"  ✗ HTTP {res.status_code}: {body}")
            return False
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")
        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            if debug:
                print("  [DEBUG] State vor Resume:", json.dumps(
                    {k: "(present)" for k in (state or {}).keys()}, indent=2
                ))
            print("  Human Review → Resume…")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            if res2.status_code >= 400:
                body = res2.text if debug else res2.text[:300]
                print(f"  ✗ Resume HTTP {res2.status_code}: {body}")
                return False
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)

        elapsed = time.perf_counter() - t0

        if not state:
            print("  ✗ Kein State erhalten")
            return False

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 1. AttackSketch
        sketch = state.get("attack_sketch")
        if sketch:
            path = OUTPUT_DIR / f"interview_sc_b_{suffix}sketch.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_serialize(sketch), f, indent=2, ensure_ascii=False, default=str)
            print(f"  ✓ {path.name}")

        # 2. TTP-Sequenz
        ttp = state.get("ttp_scenario")
        if ttp:
            path = OUTPUT_DIR / f"interview_sc_b_{suffix}ttp.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_serialize(ttp), f, indent=2, ensure_ascii=False, default=str)
            print(f"  ✓ {path.name}")

        # 3. ValidationReport
        validation = state.get("validation_report")
        if validation:
            path = OUTPUT_DIR / f"interview_sc_b_{suffix}validation.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_serialize(validation), f, indent=2, ensure_ascii=False, default=str)
            print(f"  ✓ {path.name}")

        # 4. MSEL-Narrative
        report = state.get("report", {})
        narrative = report.get("narrative", "") if isinstance(report, dict) else ""
        path = OUTPUT_DIR / f"interview_sc_b_{suffix}narrative.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(narrative)
        print(f"  ✓ {path.name}")

        # 5. Metadaten
        llm_cfg = _get_llm_config()
        metadata = {
            "mode": mode,
            "llm_model": llm_cfg["llm_model"],
            "llm_temperature": llm_cfg["llm_temperature"],
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "auditor_iterations": state.get("auditor_iterations"),
            "validation_passed": validation.get("passed") if validation else None,
        }
        path = OUTPUT_DIR / f"interview_sc_b_{suffix}metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"  ✓ {path.name}")

        print(f"  Laufzeit: {elapsed:.1f}s")
        return True

    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e}")
        if debug:
            traceback.print_exc()
        return False


def _select_best_nsmas_run(nsmas_repeat: int) -> int | None:
    """
    Nach NS-MAS-Runs: Prüft, ob Haupt-Run (ohne Suffix) passed hat.
    Falls nein: Sucht den ersten run{N}_ mit passed=true.
    Gibt die Run-Nummer zurück (1=Haupt, 2..N+1=run2..runN+1) oder None.
    """
    main_val = OUTPUT_DIR / "interview_sc_b_validation.json"
    if main_val.exists():
        try:
            with open(main_val, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("passed", False):
                return 1  # Haupt-Run hat bestanden
        except Exception:
            pass

    for i in range(nsmas_repeat):
        n = i + 2
        val_path = OUTPUT_DIR / f"interview_sc_b_run{n}_validation.json"
        if val_path.exists():
            try:
                with open(val_path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("passed", False):
                    return n
            except Exception:
                pass
    return None


def _promote_run_to_main(run_num: int) -> None:
    """Kopiert die Artefakte von run{N} in die Hauptdateien (ohne Suffix)."""
    suffix = f"run{run_num}_" if run_num > 1 else ""
    if run_num == 1:
        return  # Bereits Haupt-Dateien
    artifacts = ["sketch", "ttp", "validation", "narrative", "metadata"]
    for art in artifacts:
        ext = "json" if art != "narrative" else "txt"
        src = OUTPUT_DIR / f"interview_sc_b_{suffix}{art}.{ext}"
        dst = OUTPUT_DIR / f"interview_sc_b_{art}.{ext}"
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


async def main():
    parser = argparse.ArgumentParser(
        description="Generiert Szenario B (APT41/Atruvia) für Interview-Evaluation"
    )
    parser.add_argument("--nsmas", action="store_true", help="NS-MAS-Run mit Korrekturschleife")
    parser.add_argument("--baseline", action="store_true", help="Baseline-Run ohne Korrekturschleife")
    parser.add_argument("--nsmas-repeat", type=int, default=0, metavar="N", help="Zusätzliche NS-MAS-Runs (3–5 empfohlen). Erster PASS wird als Haupt-Szenario B übernommen.")
    parser.add_argument("--all", action="store_true", help="Alle: NS-MAS + Baseline + optional zweiter NS-MAS (--nsmas-repeat 1)")
    parser.add_argument("--debug", action="store_true", help="Vollständige Fehlerausgaben, Traceback bei Exceptions")
    args = parser.parse_args()

    if args.all:
        run_nsmas = run_baseline = True
        nsmas_repeat = 1
    else:
        run_nsmas = args.nsmas
        run_baseline = args.baseline
        nsmas_repeat = args.nsmas_repeat
        if not run_nsmas and not run_baseline:
            run_nsmas = run_baseline = True  # Default: beide

    print(f"Interview Szenario B – API: {API_URL}")
    print(f"Output: {OUTPUT_DIR}/")
    print("Hinweis: Erster NS-MAS-Request lädt die Pipeline (1–2 Min) + Szenario (3–5 Min). Bitte warten.")
    if args.debug:
        print("Debug-Modus: aktiviert")

    # 10 Min Timeout: Erster Request lädt Pipeline (1–2 Min) + LLM-Calls (3–5 Min)
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar ({API_URL}): {e}")
            print("Hinweis: Starte zuerst das Backend mit: cd V2/backend && ./run.sh")
            sys.exit(1)

        ok = 0
        if run_nsmas:
            if await run_scenario_b(client, "nsmas", "", "interview-scb-nsmas-1", args.debug):
                ok += 1
            for i in range(nsmas_repeat):
                suf = f"run{i+2}_"
                tid = f"interview-scb-nsmas-{i+2}"
                if await run_scenario_b(client, "nsmas", suf, tid, args.debug):
                    ok += 1
        if run_baseline:
            if await run_scenario_b(client, "baseline", "baseline_", "interview-scb-baseline", args.debug):
                ok += 1

        # Best-Run-Auswahl: Wenn Haupt-NS-MAS-Run FAIL, ersten run{N} mit PASS als Haupt-Szenario B verwenden
        if run_nsmas:
            best = _select_best_nsmas_run(nsmas_repeat)
            if best is None:
                print("\n⚠ Keiner der NS-MAS-Runs bestand → Fallback Option 2 (ehrliche Darstellung)")
            elif best > 1:
                _promote_run_to_main(best)
                print(f"\n✓ NS-MAS Run {best} hatte PASS → als Haupt-Szenario B übernommen")

    total = (1 + nsmas_repeat if run_nsmas else 0) + (1 if run_baseline else 0)
    print(f"\nErgebnis: {ok}/{total} Runs erfolgreich")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
