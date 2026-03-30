#!/usr/bin/env python3
"""
S1-Bug Debug: Direkte Agent-Aufrufe (ohne HTTP-Backend).

Führt NS-MAS-Pipeline für S1 (Atruvia/APT29) aus und gibt correction_hints aus.
Funktioniert ohne Backend – benötigt nur Neo4j und LLM-API-Keys.

Usage:
  cd V2/backend && python -m scripts.debug_s1_direct
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.eval_comparison import run_nsmas, SCENARIOS


async def main():
    print("S1-Bug Debug (direkte Agent-Aufrufe, kein HTTP)")
    print("=" * 60)
    print("Payload: Atruvia AG / APT29")
    print()
    print("[1/1] Starte run_nsmas (Scenario Planner → TTP Generator → KG Auditor, max 3 Iter.)…")
    print("      Erster LLM-Aufruf (Scenario Planner) kann 20–60 Sek dauern – bitte warten.")
    state = await run_nsmas(SCENARIOS[0]["payload"])
    if not state:
        print("Run fehlgeschlagen")
        return 1
    report = state.get("validation_report")
    if not report:
        print("Kein validation_report")
        return 1
    hints = (
        report.correction_hints
        if hasattr(report, "correction_hints")
        else report.get("correction_hints", [])
    )
    passed = report.passed if hasattr(report, "passed") else report.get("passed", False)
    iters = (
        report.auditor_iterations
        if hasattr(report, "auditor_iterations")
        else report.get("auditor_iterations", "?")
    )
    print("ERGEBNIS")
    print("=" * 60)
    print(f"report_passed: {passed}")
    print(f"auditor_iterations: {iters}")
    print(f"correction_hints: {len(hints)}")
    print()
    if hints:
        print("CORRECTION HINTS (Ursache für report_passed=false):")
        print("-" * 60)
        for i, h in enumerate(hints):
            m = h.message if hasattr(h, "message") else h.get("message", "?")
            sid = h.step_id if hasattr(h, "step_id") else h.get("step_id", "?")
            tid = h.technique_id if hasattr(h, "technique_id") else h.get("technique_id", "?")
            print(f"  [{i+1}] step_id={sid} technique_id={tid}")
            print(f"      message: {m}")
            print()
    else:
        print("Keine correction_hints – report_passed sollte True sein.")
    out = (
        Path(__file__).resolve().parent.parent
        / "evaluation"
        / "entwicklung_archiv"
        / "interview"
        / "debug_s1_validation_report.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    d = report.model_dump() if hasattr(report, "model_dump") else dict(report)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False, default=str)
    print(f"ValidationReport gespeichert: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
