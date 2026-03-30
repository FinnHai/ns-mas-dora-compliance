#!/usr/bin/env python3
"""
Evaluation N10 – VERBOSE VERSION mit maximalem Logging & Datensicherung.

- Szenarien s1,s2,s3 wählbar (z.B. --scenarios s1 s2 s3 für 60 Runs ohne S4)
- Vollständiger State pro Run → log_dir/run_{run_id}.json
- Inkrementelles Speichern nach JEDEM Run → checkpoint + Hauptoutput
- JSONL-Checkpoint für Recovery
- Mehrfach-Backups am Ende
- Detailliertes Log in log_dir/eval_n10_verbose.log

Usage:
  python -m scripts.run_eval_n10_verbose --scenarios s1 s2 s3   # 60 Runs S1–S3
  python -m scripts.run_eval_n10_verbose                        # Alle 80 Runs
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
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
            "scope_document": "Mehrstufiger Angriff auf das zentrale Wertpapierabwicklungssystem über kompromittierte Entwickler-Zugänge. Kritische Funktionen: Wertpapierabwicklung (T2S-Anbindung), Treasury-Management, Entwicklungs-Pipeline (CI/CD), Active Directory, SWIFT-Interface. Das Szenario soll den vollständigen Angriffslebenszyklus abbilden und mindestens 12 Angriffsschritte umfassen.",
        },
    },
]


def _to_dict(obj):
    """Rekursiv in dict konvertieren (Pydantic, Listen, etc.)."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(x) for x in obj]
    return obj


def _parse_args():
    parser = argparse.ArgumentParser(
        description="NS-MAS Evaluation N10 – VERBOSE mit Full-Logging"
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["s1", "s2", "s3", "s4"],
        default=None,
        help="Nur diese Szenarien (z.B. s1 s2 s3 für 60 Runs ohne S4)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="An bestehende eval_n10_results.json anhängen",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Log-Verzeichnis (default: evaluation/n10/logs/eval_n10_YYYYMMDD_HHMM)",
    )
    return parser.parse_args()


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
    log_dir: Path | None,
    logger: logging.Logger,
) -> tuple[dict | None, dict | None]:
    """
    Führt einen Run aus.
    Returns: (run_result, full_state) – full_state für Full-Dump, kann None sein bei Fehler.
    """
    run_id_base = f"{mode}_{scenario_id}_r{repeat:02d}"
    thread_id = f"{run_id_base}_{uuid4().hex[:8]}"

    logger.info("  Running %s (thread_id=%s)...", run_id_base, thread_id[:20] + "...")
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

        logger.info("    Response: status=%s, state_keys=%s", status, list((state or {}).keys()))

        if status == "awaiting_approval":
            logger.info("    Human Review erforderlich → resume...")
            time.sleep(SLEEP_BEFORE_RESUME)
            res2 = await client.post(
                f"{API_URL}/ns-mas/resume",
                params={"approved": "true", "thread_id": thread_id},
            )
            res2.raise_for_status()
            data2 = res2.json()
            state = data2.get("result", state)
            logger.info("    Resume: state_keys=%s", list((state or {}).keys()))

        duration = time.time() - start

        if not state:
            logger.warning("    FAIL: kein State")
            return None, None

        run_result = _extract_run_result(
            run_id=run_id_base,
            scenario_id=scenario_id,
            mode=mode,
            repeat=repeat,
            state=state,
            duration_seconds=duration,
        )
        logger.info(
            "    Done %.1fs | passed=%s | techniques=%d | tactic_match=%.2f | auditor_iter=%d",
            duration,
            run_result["report_passed"],
            run_result["num_steps"],
            run_result["tactic_match_rate"],
            run_result["auditor_iterations"],
        )
        return run_result, _to_dict(state)

    except httpx.HTTPStatusError as e:
        logger.error("    FAIL HTTP %s: %s", e.response.status_code, e)
        return None, None
    except Exception as e:
        logger.exception("    FAIL %s: %s", type(e).__name__, e)
        return None, None


def _save_checkpoint_and_output(
    results: list[dict],
    total_expected: int,
    output_path: Path,
    checkpoint_path: Path | None,
    jsonl_path: Path | None,
    run_result: dict,
    append: bool,
):
    """Speichert nach jedem Run: Hauptoutput, Checkpoint, JSONL."""
    out = {
        "metadata": {
            "total_runs": len(results),
            "expected_runs": total_expected,
            "repeats": REPEATS,
            "append": append,
            "timestamp": datetime.now().isoformat(),
        },
        "runs": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    if checkpoint_path:
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
        except OSError as e:
            pass  # Checkpoint optional, Hauptoutput ist bereits gespeichert

    if jsonl_path:
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_result, ensure_ascii=False) + "\n")


def _init_jsonl_if_needed(jsonl_path: Path, append: bool):
    """Bei neuem Lauf: JSONL leeren. Bei append: bestehende Datei behalten."""
    if not append and jsonl_path.exists():
        jsonl_path.write_text("")


async def main():
    args = _parse_args()

    scenarios = SCENARIOS
    if args.scenarios:
        scenarios = [s for s in SCENARIOS if s["id"] in args.scenarios]
        if not scenarios:
            print("Unbekannte Szenarien:", args.scenarios)
            sys.exit(1)

    total = len(scenarios) * len(MODES) * REPEATS
    eval_base = Path(__file__).resolve().parent.parent / "evaluation" / "n10"
    log_dir = Path(args.log_dir) if args.log_dir else eval_base / "logs" / f"eval_n10_{datetime.now().strftime('%Y%m%d_%H%M')}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Logging: Console + File
    log_file = log_dir / "eval_n10_verbose.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[file_handler, console_handler],
    )
    logger = logging.getLogger("eval_n10_verbose")
    logger.setLevel(logging.DEBUG)

    output_path = eval_base / "eval_n10_results.json"
    checkpoint_path = log_dir / "eval_n10_checkpoint.json"
    jsonl_path = log_dir / "eval_n10_results.jsonl"

    # Manifest für diesen Lauf
    manifest = {
        "started_at": datetime.now().isoformat(),
        "scenarios": [s["id"] for s in scenarios],
        "total_expected": total,
        "output_path": str(output_path),
        "log_dir": str(log_dir),
    }
    with open(log_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    _init_jsonl_if_needed(jsonl_path, args.append)

    existing_runs = []
    if args.append and output_path.exists():
        try:
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
            existing_runs = data.get("runs", [])
            logger.info("Geladen: %d bestehende Runs", len(existing_runs))
        except Exception as e:
            logger.warning("Konnte %s nicht laden: %s", output_path, e)

    print("=" * 70)
    print("NS-MAS Evaluation N10 – VERBOSE MODE")
    print("=" * 70)
    print(f"  Szenarien: {[s['id'] for s in scenarios]}")
    print(f"  Runs gesamt: {total}")
    print(f"  Log-Verzeichnis: {log_dir}")
    print(f"  Log-Datei: {log_file}")
    print(f"  Output: {output_path}")
    print(f"  JSONL-Checkpoint: {jsonl_path}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            r.raise_for_status()
        except Exception as e:
            print(f"Backend nicht erreichbar: {e}")
            print("Starte: cd V2/backend && ./run.sh")
            sys.exit(1)

        results = list(existing_runs) if args.append else []
        existing_ids = {r["run_id"] for r in results}
        current = 0

        for scenario in scenarios:
            sid = scenario["id"]
            payload = scenario["payload"]
            for mode in MODES:
                for repeat in range(1, REPEATS + 1):
                    current += 1
                    run_id = f"{mode}_{sid}_r{repeat:02d}"
                    if args.append and run_id in existing_ids:
                        print(f"\n[{current}/{total}] {sid} {mode} r{repeat:02d} (bereits vorhanden, übersprungen)")
                        continue
                    print(f"\n[{current}/{total}] {sid} {mode} r{repeat:02d}")
                    run_result, full_state = await run_single(
                        client, sid, payload, mode, repeat, log_dir, logger
                    )
                    if run_result:
                        results.append(run_result)
                        # Full-State pro Run speichern
                        full_path = log_dir / f"run_{run_result['run_id']}.json"
                        if full_state:
                            full_dump = {
                                "run_id": run_result["run_id"],
                                "run_result": run_result,
                                "timestamp": datetime.now().isoformat(),
                                "state": full_state,
                            }
                            with open(full_path, "w", encoding="utf-8") as f:
                                json.dump(full_dump, f, indent=2, ensure_ascii=False)
                            logger.debug("Full-State gespeichert: %s", full_path)

                        # Inkrementell speichern
                        _save_checkpoint_and_output(
                            results=results,
                            total_expected=total,
                            output_path=output_path,
                            checkpoint_path=checkpoint_path,
                            jsonl_path=jsonl_path,
                            run_result=run_result,
                            append=args.append,
                        )
                        logger.info("Checkpoint gespeichert (%d/%d)", len(results), total)

                    if current < total:
                        time.sleep(PAUSE_BETWEEN_RUNS)

        # Finale Mehrfach-Backups
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
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        backups = [
            eval_base / f"eval_n10_results_{ts}.json",
            log_dir / "eval_n10_results_final.json",
        ]
        for bp in backups:
            bp.parent.mkdir(parents=True, exist_ok=True)
            with open(bp, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
            logger.info("Backup: %s", bp)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        new_count = len(results) - len(existing_runs) if args.append else len(results)
        print(f"\n{'='*70}")
        print(f"Fertig: {new_count} neue Runs, gesamt {len(results)}")
        print(f"Output: {output_path}")
        print(f"Logs + Full-States: {log_dir}")
        print(f"Backups: {backups}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
