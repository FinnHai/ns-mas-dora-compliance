#!/usr/bin/env python3
"""
Validierungsplan Punkt 8: Smoke Test – vollständiger S2-Durchlauf (Lazarus Group).

Führt S2 komplett durch, speichert den State in full_run_s2_debug.json
für manuelle Verifikation gegen eval_comparison.json.

Usage: python -m scripts.run_smoke_test_s2
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = os.environ.get("API_URL", "http://localhost:8000")
THREAD_ID = "smoke-s2"

S2_PAYLOAD = {
    "target_organization": "Deutsche Bundesbank",
    "threat_profile": "Lazarus Group",
    "scope_document": "Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
}


def _serialize(obj):
    """Serialisiert Pydantic/Objekte für JSON."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


async def run_smoke_test():
    print("=" * 60)
    print("NS-MAS Smoke Test S2 (Lazarus Group)")
    print(f"API: {API_URL}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            sys.exit(1)

        print("\n1. POST /ns-mas/run …")
        res = await client.post(
            f"{API_URL}/ns-mas/run",
            json=S2_PAYLOAD,
            params={"thread_id": THREAD_ID},
        )
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")
        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            print("2. Human Review → POST /ns-mas/resume …")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": THREAD_ID},
            )
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)

        if not state:
            print("Kein State erhalten.")
            sys.exit(1)

        full_output = {
            "input": state.get("user_input"),
            "attack_sketch": state.get("attack_sketch"),
            "ttp_scenario": state.get("ttp_scenario"),
            "validation_report": state.get("validation_report"),
            "auditor_iterations": state.get("auditor_iterations"),
            "msel_output": state.get("report"),
            "correction_history": state.get("correction_hints", []),
        }

        output_path = Path(__file__).resolve().parent.parent / "evaluation" / "smoke" / "full_run_s2_debug.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(_serialize(full_output), f, indent=2, ensure_ascii=False, default=str)

        print(f"\n✓ Vollständiger Output gespeichert: {output_path}")
        print("  Verifiziere gegen evaluation/comparison/eval_comparison.json (S2).")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
