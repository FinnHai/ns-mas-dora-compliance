#!/usr/bin/env python3
"""
Evaluation N10: 60 Runs für Kap. 5 (Mann-Whitney-U, Jaccard, Auditor-Effektivität).

Pro Szenario: 10 NS-MAS + 10 Baseline = 20 Runs. S1–S3 = 60 Runs, S4 = 20 Runs (Skalierbarkeitstest).
Baseline: Auditor misst, aber keine Korrekturschleife (mode=baseline).

Output: eval_n10_results.json mit run_result pro Run.

Usage:
  python -m scripts.run_eval_n10              # Alle Szenarien (S1–S4 = 80 Runs)
  python -m scripts.run_eval_n10 --scenario s4 # Nur S4 (20 Runs)
  python -m scripts.run_eval_n10 --scenario s4 --append  # S4 an bestehende Ergebnisse anhängen
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
REPEATS = 10
MODES = ["nsmas", "baseline"]
PAUSE_BETWEEN_RUNS = 5
SLEEP_BEFORE_RESUME = 1

SCENARIOS = [
    {
        "id": "s1",
        "payload": {
            "target_organization": "Atruvia AG",
            "threat_profile": "APT29",
            "scope_document": "Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory.",
        },
    },
    {
        "id": "s2",
        "payload": {
            "target_organization": "Deutsche Bundesbank",
            "threat_profile": "Lazarus Group",
            "scope_document": "Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
        },
    },
    {
        "id": "s3",
        "payload": {
            "target_organization": "Sparkasse Münsterland Ost",
            "threat_profile": "FIN13",
            "scope_document": "Ransomware-Angriff auf Kernbanksystem. Kritische Funktionen: Kontoführung, Kartenverarbeitung, Backup-Infrastruktur.",
        },
    },
    {
        "id": "s4",
        "payload": {
            "target_organization": "DZ BANK AG",
            "threat_profile": "APT41",
            "scope_document": "Mehrstufiger Angriff auf das zentrale Wertpapierabwicklungssystem über kompromittierte Entwickler-Zugänge. Kritische Funktionen: Wertpapierabwicklung (T2S-Anbindung), Treasury-Management, Entwicklungs-Pipeline (CI/CD), Active Directory, SWIFT-Interface. Das Szenario soll den vollständigen Angriffslebenszyklus abbilden und mindestens 12 Angriffsschritte umfassen, einschließlich Reconnaissance, Resource Development, mehrstufiger lateraler Bewegung, Privilege Escalation, Defense Evasion und gezielter Exfiltration über mehrere Kanäle.",
        },
    },
]


def _parse_args():
    parser = argparse.ArgumentParser(
        description="NS-MAS Evaluation N10 – Szenario-Runs für Kap. 5"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["s1", "s2", "s3", "s4"],
        default=None,
        help="Nur dieses Szenario ausführen (z.B. s4 für Skalierbarkeitstest)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Bestehende eval_n10_results.json laden, neue Runs anhängen, speichern",
    )
    return parser.parse_args()


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj if isinstance(obj, dict) else {}


def _extract_run_result(
    run_id: str,
    scenario_id: str,
    mode: str,
    repeat: int,
    state: dict,
    duration_seconds: float,
) -> dict:
    """Extrahiert run_result aus Pipeline-State."""
    ttp = state.get("ttp_scenario") or {}
    report = state.get("validation_report") or {}
    report = _to_dict(report) if report else {}

    technique_ids = []
    for phase in ttp.get("phases", []):
        for step in phase.get("steps", []):
            technique_ids.append(step.get("technique_id", ""))

    steps = report.get("steps", [])
    steps = [s if isinstance(s, dict) else _to_dict(s) for s in steps]
    n = len(steps) if steps else 0

    def _rate(key: str) -> float:
        if n == 0:
            return 0.0
        return sum(1 for s in steps if s.get(key)) / n

    hints = report.get("correction_hints", [])
    hints = [h if isinstance(h, dict) else _to_dict(h) for h in hints]

    return {
        "run_id": run_id,
        "scenario": scenario_id,
        "mode": mode,
        "repeat": repeat,
        "technique_ids": technique_ids,
        "num_steps": len(technique_ids),
        "tactic_match_rate": round(_rate("tactic_match"), 4),
        "id_exists_rate": round(_rate("id_exists"), 4),
        "phase_conform_rate": round(_rate("phase_conform"), 4),
        "path_reachable_rate": round(_rate("path_reachable"), 4),
        "auditor_iterations": state.get("auditor_iterations", 0),
        "correction_hints_count": len(hints),
        "report_passed": report.get("passed", False),
        "duration_seconds": round(duration_seconds, 1),
        "timestamp": datetime.now().isoformat(),
    }


async def run_single(
    client: httpx.AsyncClient,
    scenario_id: str,
    payload: dict,
    mode: str,
    repeat: int,
) -> dict | None:
    """Führt einen Run aus und gibt run_result zurück."""
    run_id_base = f"{mode}_{scenario_id}_r{repeat:02d}"
    thread_id = f"{run_id_base}_{uuid4().hex[:8]}"

    print(f"  Running {run_id_base}...", end=" ", flush=True)
    start = time.time()

    try:
        res = await client.post(
            f"{API_URL}/ns-mas/run",
            json=payload,
            params={"thread_id": thread_id, "mode": mode},
        )
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")
        state = data.get("state", data.get("result", {}))

        if status == "awaiting_approval":
            time.sleep(SLEEP_BEFORE_RESUME)
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)

        duration = time.time() - start

        if not state:
            print(f"FAIL (kein State)")
            return None

        run_result = _extract_run_result(
            run_id=run_id_base,
            scenario_id=scenario_id,
            mode=mode,
            repeat=repeat,
            state=state,
            duration_seconds=duration,
        )
        print(f"Done in {duration:.1f}s | passed={run_result['report_passed']}")
        return run_result

    except httpx.HTTPStatusError as e:
        print(f"FAIL HTTP {e.response.status_code}")
        return None
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        return None


async def main():
    args = _parse_args()

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"Unbekanntes Szenario: {args.scenario}")
            sys.exit(1)

    total = len(scenarios) * len(MODES) * REPEATS
    print("=" * 60)
    print(f"NS-MAS Evaluation N10 – {total} Runs")
    if args.scenario:
        print(f"Szenario: {args.scenario} only")
    if args.append:
        print("Modus: --append (bestehende Ergebnisse anhängen)")
    print(f"Backend: {API_URL}")
    print(f"Pause zwischen Runs: {PAUSE_BETWEEN_RUNS}s")
    print("=" * 60)

    output_path = Path(__file__).resolve().parent.parent / "evaluation" / "n10" / "eval_n10_results.json"
    existing_runs = []
    if args.append and output_path.exists():
        try:
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
            existing_runs = data.get("runs", [])
            print(f"Geladen: {len(existing_runs)} bestehende Runs")
        except Exception as e:
            print(f"Warnung: Konnte {output_path} nicht laden: {e}")

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            print("Starte: cd V2/backend && ./run.sh")
            sys.exit(1)

        results = list(existing_runs) if args.append else []
        current = 0

        for scenario in scenarios:
            sid = scenario["id"]
            payload = scenario["payload"]
            for mode in MODES:
                for repeat in range(1, REPEATS + 1):
                    current += 1
                    print(f"\n[{current}/{total}] {sid} {mode} r{repeat:02d}")
                    run_result = await run_single(
                        client, sid, payload, mode, repeat
                    )
                    if run_result:
                        results.append(run_result)
                    if current < total:
                        time.sleep(PAUSE_BETWEEN_RUNS)

        out = {
            "metadata": {
                "total_runs": len(results),
                "expected_runs": total,
                "repeats": REPEATS,
                "append": args.append,
                "timestamp": datetime.now().isoformat(),
            },
            "runs": results,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Ohne --append: Vorhandene Datei sichern, bevor überschrieben wird
        if not args.append and output_path.exists():
            backup_path = output_path.parent / (
                f"eval_n10_results_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            )
            shutil.copy2(output_path, backup_path)
            print(f"Backup: {backup_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        new_count = len(results) - len(existing_runs) if args.append else len(results)
        print(f"\n{'='*60}")
        print(f"Fertig: {new_count} neue Runs, gesamt {len(results)} gespeichert")
        print(f"Output: {output_path}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
