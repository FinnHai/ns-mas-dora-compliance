#!/usr/bin/env python3
"""
Debug S1-Bug: Korrekturhinweise aus nsmas_s1-Run ausgeben.

Führt einen frischen NS-MAS-Run mit dem S1-Payload (Atruvia/APT29) durch,
hängt automatisch Resume an und gibt alle correction_hints aus.
Speichert den vollständigen validation_report für Analyse.

Usage:
  cd V2/backend && python -m scripts.debug_s1_hints

Backend muss laufen: ./run.sh
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "interview"

S1_PAYLOAD = {
    "target_organization": "Atruvia AG",
    "threat_profile": "APT29",
    "scope_document": (
        "Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. "
        "Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory."
    ),
}


def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


async def main():
    thread_id = "debug-s1-hints"
    print(f"Debug S1 Hints – API: {API_URL}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            print("Hinweis: cd V2/backend && ./run.sh")
            sys.exit(1)

        print("POST /ns-mas/run (S1: Atruvia/APT29)…")
        res = await client.post(
            f"{API_URL}/ns-mas/run",
            json=S1_PAYLOAD,
            params={"thread_id": thread_id, "mode": "nsmas"},
        )
        if res.status_code >= 400:
            print(f"HTTP {res.status_code}: {res.text}")
            sys.exit(1)

        data = res.json()
        status = data.get("status", "")
        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            print("Human Review → Resume…")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            if res2.status_code >= 400:
                print(f"Resume HTTP {res2.status_code}: {res2.text}")
                sys.exit(1)
            data2 = res2.json()
            state = data2.get("result", state)

        if not state:
            print("Kein State erhalten")
            sys.exit(1)

        validation = state.get("validation_report")
        if not validation:
            print("Kein validation_report im State")
            print("State-Keys:", list(state.keys()) if state else "N/A")
            sys.exit(1)

        val_dict = validation if isinstance(validation, dict) else _serialize(validation)
        hints = val_dict.get("correction_hints", [])
        passed = val_dict.get("passed", None)
        auditor_iterations = val_dict.get("auditor_iterations", "?")

        print("\n" + "=" * 60)
        print("ERGEBNIS")
        print("=" * 60)
        print(f"report_passed: {passed}")
        print(f"auditor_iterations: {auditor_iterations}")
        print(f"correction_hints: {len(hints)}")
        print()

        if hints:
            print("CORRECTION HINTS (Ursache für report_passed=false):")
            print("-" * 60)
            for i, h in enumerate(hints):
                hd = h if isinstance(h, dict) else {"step_id": getattr(h, "step_id", "?"), "technique_id": getattr(h, "technique_id", "?"), "message": getattr(h, "message", "?")}
                print(f"  [{i+1}] step_id={hd.get('step_id')} technique_id={hd.get('technique_id')}")
                print(f"      message: {hd.get('message', 'N/A')}")
                print()
        else:
            print("Keine correction_hints – report_passed sollte True sein.")
            print("Falls passed=False: Prüfe ob eine andere Fehlerquelle vorliegt.")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / "debug_s1_validation_report.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(val_dict, f, indent=2, ensure_ascii=False, default=str)
        print(f"Vollständiger ValidationReport gespeichert: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
