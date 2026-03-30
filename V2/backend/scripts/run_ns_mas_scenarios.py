#!/usr/bin/env python3
"""
NS-MAS Pipeline Szenarien direkt ausführen (ohne Frontend).

Verwendet das laufende Backend auf localhost:8002.
Beispiel: Backend starten, dann:
  python -m scripts.run_ns_mas_scenarios

Nur ein Szenario (schneller):
  python -m scripts.run_ns_mas_scenarios --single 0

Anderer Port:
  API_URL=http://localhost:8000 python -m scripts.run_ns_mas_scenarios
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8002")
THREAD_PREFIX = "script-"


SCENARIOS = [
    {
        "name": "APT29 vs. Finanzinstitut",
        "payload": {
            "target_organization": "Finanzinstitut AG",
            "threat_profile": "APT29",
            "scope_document": "Kritische Infrastruktur Bankensektor",
        },
    },
    {
        "name": "Ransomware vs. Krankenhaus",
        "payload": {
            "target_organization": "Krankenhausverbund Nord",
            "threat_profile": "Ransomware-as-a-Service",
            "scope_document": None,
        },
    },
    {
        "name": "Insider Threat",
        "payload": {
            "target_organization": "Tech-Startup GmbH",
            "threat_profile": "Insider Threat",
            "scope_document": "Cloud-Infrastruktur AWS",
        },
    },
    {
        "name": "Minimal (nur Pflichtfelder)",
        "payload": {
            "target_organization": "Test-Org",
            "threat_profile": "Generic Adversary",
        },
    },
]


async def run_scenario(client: httpx.AsyncClient, name: str, payload: dict, thread_id: str) -> bool:
    """Führt ein Szenario aus: /run → ggf. /resume."""
    print(f"\n--- {name} (thread={thread_id}) ---")
    try:
        res = await client.post(f"{API_URL}/ns-mas/run", json=payload, params={"thread_id": thread_id})
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")

        if status == "completed":
            result = data.get("result", {})
            report = result.get("report", {})
            print(f"  Status: completed (ohne Human Review)")
            if report:
                msel = report.get("msel", {})
                print(f"  Scenario-ID: {msel.get('scenario_id', 'N/A')}")
                print(f"  Events: {len(msel.get('events', []))}")
            return True

        if status == "awaiting_approval":
            print("  Status: awaiting_approval → Resume…")
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            res2.raise_for_status()
            data2 = res2.json()
            if data2.get("status") == "completed":
                result = data2.get("result", {})
                report = result.get("report", {})
                print(f"  Status: completed (nach Resume)")
                if report:
                    msel = report.get("msel", {})
                    print(f"  Scenario-ID: {msel.get('scenario_id', 'N/A')}")
                    print(f"  Events: {len(msel.get('events', []))}")
                return True
            print(f"  Unerwartet: {data2}")
            return False

        print(f"  Unerwarteter Status: {status}")
        return False

    except httpx.HTTPStatusError as e:
        print(f"  HTTP Fehler: {e.response.status_code} - {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"  Fehler: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="NS-MAS Pipeline Szenarien ausführen")
    parser.add_argument("--single", type=int, metavar="N", help="Nur Szenario N ausführen (0–3)")
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.single is not None:
        if 0 <= args.single < len(SCENARIOS):
            scenarios = [SCENARIOS[args.single]]
        else:
            print(f"Ungültiger Index: {args.single} (0–{len(SCENARIOS)-1})")
            sys.exit(1)

    print(f"NS-MAS Pipeline Szenarien – Backend: {API_URL}")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Health-Check
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            print("Starte zuerst: cd V2/backend && PORT=8002 ./run.sh")
            sys.exit(1)

        ok = 0
        for i, s in enumerate(scenarios):
            thread_id = f"{THREAD_PREFIX}{i}"
            if await run_scenario(client, s["name"], s["payload"], thread_id):
                ok += 1

    print("\n" + "=" * 50)
    print(f"Ergebnis: {ok}/{len(scenarios)} Szenarien erfolgreich")
    sys.exit(0 if ok == len(SCENARIOS) else 1)


if __name__ == "__main__":
    asyncio.run(main())
