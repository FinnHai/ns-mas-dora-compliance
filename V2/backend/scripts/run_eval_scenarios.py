#!/usr/bin/env python3
"""
Evaluation: Drei Szenarien für Kap. 4.4 / Kap. 5.

Szenario 1: APT29 (bekannter Akteur, Finanzsektor)
Szenario 2: Lazarus Group (anderer Akteur)
Szenario 3: FIN13 (unbekannter Akteur, Graceful Degradation)

Output: Vollständiger JSON-State pro Szenario inkl.:
- technique_ids gewählt
- tactic_match pro Schritt
- suggested_technique_id in correction_hints
- auditor_iterations
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8002")
THREAD_PREFIX = "eval-"

SCENARIOS = [
    {
        "name": "Szenario 1 — Haupttest (APT29, Finanzsektor)",
        "payload": {
            "target_organization": "Atruvia AG",
            "threat_profile": "APT29",
            "scope_document": "Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory.",
        },
    },
    {
        "name": "Szenario 2 — Generalisierung (Lazarus Group)",
        "payload": {
            "target_organization": "Deutsche Bundesbank",
            "threat_profile": "Lazarus Group",
            "scope_document": "Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
        },
    },
    {
        "name": "Szenario 3 — Graceful Degradation (FIN13)",
        "payload": {
            "target_organization": "Sparkasse Münsterland Ost",
            "threat_profile": "FIN13",
            "scope_document": "Ransomware-Angriff auf Kernbanksystem. Kritische Funktionen: Kontoführung, Kartenverarbeitung, Backup-Infrastruktur.",
        },
    },
]


def _serialize(obj):
    """Serialisiert Pydantic/Objekte für JSON."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    return obj


def _extract_metrics(state: dict) -> dict:
    """Extrahiert Metriken für Kap. 5."""
    ttp = state.get("ttp_scenario") or {}
    report = state.get("validation_report") or {}
    report = report if isinstance(report, dict) else (report.model_dump() if hasattr(report, "model_dump") else {})

    technique_ids = []
    for phase in ttp.get("phases", []):
        for step in phase.get("steps", []):
            technique_ids.append(step.get("technique_id", ""))

    steps = report.get("steps", [])
    tactic_matches = [s.get("tactic_match") for s in steps if isinstance(s, dict)]
    if not tactic_matches and steps:
        tactic_matches = [getattr(s, "tactic_match", None) for s in steps]

    hints = report.get("correction_hints", [])
    suggested_ids = []
    for h in hints:
        sid = h.get("suggested_technique_id") if isinstance(h, dict) else getattr(h, "suggested_technique_id", None)
        if sid:
            suggested_ids.append(sid)

    return {
        "technique_ids": technique_ids,
        "tactic_match_per_step": tactic_matches,
        "tactic_match_all_true": all(tactic_matches) if tactic_matches else None,
        "correction_hints_count": len(hints),
        "suggested_technique_ids": suggested_ids,
        "auditor_iterations": state.get("auditor_iterations", 0),
        "report_passed": report.get("passed", False),
    }


async def run_scenario(client: httpx.AsyncClient, name: str, payload: dict, thread_id: str) -> dict | None:
    """Führt ein Szenario aus und gibt den vollständigen State zurück."""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"Input: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    try:
        res = await client.post(f"{API_URL}/ns-mas/run", json=payload, params={"thread_id": thread_id})
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")

        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            print("  → Human Review → Resume…")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)

        if not state:
            print("  Kein State erhalten")
            return None

        # Metriken für Kap. 5
        metrics = _extract_metrics(state)
        print("\n--- Metriken (Kap. 5) ---")
        print(f"  Technik-IDs: {metrics['technique_ids']}")
        print(f"  tactic_match pro Schritt: {metrics['tactic_match_per_step']}")
        print(f"  Alle tactic_match: {metrics['tactic_match_all_true']}")
        print(f"  Correction Hints: {metrics['correction_hints_count']}")
        print(f"  suggested_technique_ids: {metrics['suggested_technique_ids']}")
        print(f"  Auditor-Iterationen: {metrics['auditor_iterations']}")
        print(f"  Report passed: {metrics['report_passed']}")

        return {"state": _serialize(state), "metrics": metrics}

    except httpx.HTTPStatusError as e:
        print(f"  HTTP Fehler: {e.response.status_code} - {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"  Fehler: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    print("NS-MAS Evaluation – Drei Szenarien für Kap. 4.4 / Kap. 5")
    print(f"Backend: {API_URL}")

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            print("Starte zuerst: cd V2/backend && PORT=8002 ./run.sh")
            sys.exit(1)

        results = []
        for i, s in enumerate(SCENARIOS):
            thread_id = f"{THREAD_PREFIX}{i}"
            out = await run_scenario(client, s["name"], s["payload"], thread_id)
            if out:
                results.append({"name": s["name"], "payload": s["payload"], **out})

    # Vollständiger JSON-Output für alle Szenarien
    output_path = os.path.join(os.path.dirname(__file__), "..", "evaluation_results", "eval_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Vollständiger JSON-Output gespeichert: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
