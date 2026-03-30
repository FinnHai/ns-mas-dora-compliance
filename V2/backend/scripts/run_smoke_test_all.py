#!/usr/bin/env python3
"""
Smoke Test S1, S2, S3 – vollständige Durchläufe für Expertenverifikation.

Führt alle drei Szenarien durch, speichert jeweils full_run_s1_debug.json,
full_run_s2_debug.json, full_run_s3_debug.json.

Usage: python -m scripts.run_smoke_test_all
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 127.0.0.1 statt localhost, um IPv6-Connection-refused zu vermeiden
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

SCENARIOS = [
    {
        "id": "s1",
        "name": "Szenario 1 — APT29 (Haupttest)",
        "payload": {
            "target_organization": "Atruvia AG",
            "threat_profile": "APT29",
            "scope_document": "Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory.",
        },
    },
    {
        "id": "s2",
        "name": "Szenario 2 — Lazarus Group (Generalisierung)",
        "payload": {
            "target_organization": "Deutsche Bundesbank",
            "threat_profile": "Lazarus Group",
            "scope_document": "Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
        },
    },
    {
        "id": "s3",
        "name": "Szenario 3 — FIN13 (Graceful Degradation)",
        "payload": {
            "target_organization": "Sparkasse Münsterland Ost",
            "threat_profile": "FIN13",
            "scope_document": "Ransomware-Angriff auf Kernbanksystem. Kritische Funktionen: Kontoführung, Kartenverarbeitung, Backup-Infrastruktur.",
        },
    },
]


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


async def run_scenario(client: httpx.AsyncClient, scenario: dict, output_dir: Path) -> bool:
    sid = scenario["id"]
    thread_id = f"smoke-{sid}"
    payload = scenario["payload"]
    t0 = time.perf_counter()
    print(f"\n{'='*60}")
    print(f"{scenario['name']}")
    print(f"{'='*60}")
    print(f"  Payload: Org={payload.get('target_organization', '?')}, Threat={payload.get('threat_profile', '?')}")

    try:
        print(f"  POST /ns-mas/run … Warte auf Antwort (Timeout 300s)…")
        res = await client.post(
            f"{API_URL}/ns-mas/run",
            json=payload,
            params={"thread_id": thread_id},
        )
        if res.status_code >= 400:
            elapsed_err = time.perf_counter() - t0
            print(f"  ✗ HTTP {res.status_code} (nach {elapsed_err:.1f}s):")
            print(f"  Response-Body: {res.text}")
            return False
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")
        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            print(f"  Human Review → POST /ns-mas/resume … Warte auf Antwort…")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            if res2.status_code >= 400:
                elapsed_total = time.perf_counter() - t0
                print(f"  ✗ Resume HTTP {res2.status_code} (nach {elapsed_total:.1f}s):")
                print(f"  Response-Body: {res2.text}")
                return False
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)
        elapsed = time.perf_counter() - t0

        if not state:
            print(f"  ✗ Kein State erhalten")
            return False

        full_output = {
            "scenario_id": sid,
            "scenario_name": scenario["name"],
            "input": state.get("user_input"),
            "attack_sketch": state.get("attack_sketch"),
            "ttp_scenario": state.get("ttp_scenario"),
            "validation_report": state.get("validation_report"),
            "auditor_iterations": state.get("auditor_iterations"),
            "msel_output": state.get("report"),
            "correction_history": state.get("correction_hints", []),
        }

        output_path = output_dir / f"full_run_{sid}_debug.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(_serialize(full_output), f, indent=2, ensure_ascii=False, default=str)

        print(f"  ✓ Gespeichert: {output_path} (Laufzeit: {elapsed:.1f}s)")
        return True

    except Exception as e:
        elapsed_final = time.perf_counter() - t0
        print(f"  ✗ Fehler nach {elapsed_final:.1f}s: {type(e).__name__}: {e}")
        return False


async def main():
    output_dir = Path(__file__).resolve().parent.parent / "evaluation" / "smoke"
    print("=" * 60)
    print("NS-MAS Smoke Test – S1, S2, S3")
    print(f"API: {API_URL}")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_dir}/full_run_*_debug.json")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            sys.exit(1)

        results = []
        for scenario in SCENARIOS:
            ok = await run_scenario(client, scenario, output_dir)
            results.append((scenario["id"], ok))

    print(f"\n{'='*60}")
    print("Zusammenfassung:")
    for sid, ok in results:
        print(f"  {sid}: {'✓' if ok else '✗'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
