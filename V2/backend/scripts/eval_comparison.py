#!/usr/bin/env python3
"""
Evaluation: 12 Runs (3 Baseline + 9 NS-MAS) für Kap. 5.

Baseline: LLM ohne KG-Grounding (actor_context="", kein Retry).
NS-MAS: Mit KG-Grounding, Retry-Schleife, je 3 Wiederholungen pro Szenario.

Output: eval_comparison.json mit Metriken und Summary.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys

# Backend-Root für Imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.kg_auditor import run_kg_auditor
from app.agents.report_synthesizer import run_report_synthesizer
from app.agents.scenario_planner import run_scenario_planner
from app.agents.ttp_generator import run_ttp_generator
from app.config import settings
from app.models.ns_mas_schemas import UserInput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLEEP_BETWEEN_RUNS = 5

SCENARIOS = [
    {
        "name": "Szenario 1 — APT29 Finanzsektor",
        "payload": {
            "target_organization": "Atruvia AG",
            "threat_profile": "APT29",
            "scope_document": "Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory.",
        },
    },
    {
        "name": "Szenario 2 — Lazarus Group",
        "payload": {
            "target_organization": "Deutsche Bundesbank",
            "threat_profile": "Lazarus Group",
            "scope_document": "Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
        },
    },
    {
        "name": "Szenario 3 — FIN13 Graceful Degradation",
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


def _to_dict(obj):
    """Konvertiert Pydantic zu dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj if isinstance(obj, dict) else {}


def _get_steps_from_report(report) -> list:
    """Extrahiert steps aus ValidationReport (dict oder Pydantic)."""
    if report is None:
        return []
    d = _to_dict(report)
    steps = d.get("steps", [])
    return [s if isinstance(s, dict) else _to_dict(s) for s in steps]


def _get_phases_from_ttp(ttp) -> list:
    """Extrahiert phases aus TTPScenario (dict oder Pydantic)."""
    if ttp is None:
        return []
    d = _to_dict(ttp)
    return d.get("phases", [])


def jaccard(set_a: set, set_b: set) -> float:
    """Jaccard-Similarität zwischen zwei Technik-ID-Sets."""
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


async def run_baseline(payload: dict) -> dict | None:
    """
    Baseline: Direkte Agent-Aufrufe ohne KG-Grounding.
    actor_context="", KG Auditor 1x (read-only), kein Retry.
    """
    try:
        user_input = UserInput(**payload)
        sketch = await run_scenario_planner(user_input)
        ttp = await run_ttp_generator(sketch, use_actor_context=False)
        report = await run_kg_auditor(ttp, auditor_iterations=0)
        report_dict = await run_report_synthesizer(ttp, user_input)

        return {
            "attack_sketch": sketch,
            "ttp_scenario": ttp,
            "validation_report": report,
            "report": report_dict,
            "auditor_iterations": 1,
        }
    except Exception as e:
        logger.exception("Baseline Run fehlgeschlagen: %s", e)
        return None


async def run_nsmas(payload: dict) -> dict | None:
    """
    NS-MAS: Retry-Schleife wie in der Pipeline.
    actor_context aus KG, KG Auditor mit Retry bis passed oder max_iter.
    """
    try:
        user_input = UserInput(**payload)
        sketch = await run_scenario_planner(user_input)

        max_iter = getattr(settings, "max_audit_iterations", 3)
        ttp = None
        report = None
        correction_hints = []
        iterations = 0

        while iterations < max_iter:
            ttp = await run_ttp_generator(sketch, correction_hints=correction_hints)
            report = await run_kg_auditor(ttp, auditor_iterations=iterations)
            iterations += 1

            if report.passed:
                break
            correction_hints = report.correction_hints

        if ttp is None or report is None:
            return None

        report_dict = await run_report_synthesizer(ttp, user_input)

        return {
            "attack_sketch": sketch,
            "ttp_scenario": ttp,
            "validation_report": report,
            "report": report_dict,
            "auditor_iterations": iterations,
        }
    except Exception as e:
        logger.exception("NS-MAS Run fehlgeschlagen: %s", e)
        return None


def format_result(
    run_id: str,
    scenario_name: str,
    mode: str,
    repeat: int,
    payload: dict,
    state: dict | None,
    error: str | None = None,
) -> dict:
    """Formatiert Run-Ergebnis für eval_comparison.json."""
    result = {
        "run_id": run_id,
        "scenario_name": scenario_name,
        "mode": mode,
        "repeat": repeat,
        "payload": payload,
    }

    if error:
        result["report_passed"] = None
        result["error"] = error
        return result

    if state is None:
        result["report_passed"] = None
        result["error"] = "Run returned None"
        return result

    ttp = state.get("ttp_scenario")
    report = state.get("validation_report")

    # technique_ids, technique_names
    technique_ids = []
    technique_names = []
    all_steps = []
    for phase in _get_phases_from_ttp(ttp):
        for step in phase.get("steps", []):
            s = step if isinstance(step, dict) else _to_dict(step)
            technique_ids.append(s.get("technique_id", ""))
            technique_names.append(s.get("technique_name", ""))
            all_steps.append(s)

    steps_val = _get_steps_from_report(report)
    tactic_match_per_step = [s.get("tactic_match", False) for s in steps_val]
    id_exists_per_step = [s.get("id_exists", False) for s in steps_val]
    phase_conform_per_step = [s.get("phase_conform", False) for s in steps_val]
    path_reachable_per_step = [s.get("path_reachable", False) for s in steps_val]

    n = len(tactic_match_per_step) or 1
    tactic_match_rate = sum(tactic_match_per_step) / n if tactic_match_per_step else 0.0
    id_exists_rate = sum(id_exists_per_step) / n if id_exists_per_step else 0.0
    phase_conform_rate = sum(phase_conform_per_step) / n if phase_conform_per_step else 0.0
    path_reachable_rate = sum(path_reachable_per_step) / n if path_reachable_per_step else 0.0

    report_passed = report.passed if hasattr(report, "passed") else _to_dict(report).get("passed", False)
    correction_hints = report.correction_hints if hasattr(report, "correction_hints") else _to_dict(report).get("correction_hints", [])
    auditor_iterations = state.get("auditor_iterations", 0)

    uses_subtechniques = any("." in (tid or "") for tid in technique_ids)
    has_cve_references = any(len((s.get("cve_references") or [])) > 0 for s in all_steps)

    result.update({
        "technique_ids": technique_ids,
        "technique_names": technique_names,
        "tactic_match_per_step": tactic_match_per_step,
        "tactic_match_rate": round(tactic_match_rate, 2),
        "id_exists_per_step": id_exists_per_step,
        "id_exists_rate": round(id_exists_rate, 2),
        "phase_conform_per_step": phase_conform_per_step,
        "phase_conform_rate": round(phase_conform_rate, 2),
        "path_reachable_per_step": path_reachable_per_step,
        "path_reachable_rate": round(path_reachable_rate, 2),
        "correction_hints_count": len(correction_hints),
        "auditor_iterations": auditor_iterations,
        "report_passed": report_passed,
        "num_steps": len(technique_ids),
        "uses_subtechniques": uses_subtechniques,
        "has_cve_references": has_cve_references,
    })

    return result


def compute_summary(results: list[dict]) -> dict:
    """Berechnet Summary für Baseline, NS-MAS, Reproduzierbarkeit, Improvement."""
    baseline_runs = [r for r in results if r.get("mode") == "baseline" and r.get("error") is None]
    nsmas_runs = [r for r in results if r.get("mode") == "nsmas" and r.get("error") is None]

    def avg_rate(runs, key):
        vals = [r[key] for r in runs if r.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def subtechnique_rate(runs):
        return round(sum(1 for r in runs if r.get("uses_subtechniques")) / len(runs), 2) if runs else 0.0

    def cve_rate(runs):
        return round(sum(1 for r in runs if r.get("has_cve_references")) / len(runs), 2) if runs else 0.0

    baseline_summary = {
        "avg_tactic_match_rate": avg_rate(baseline_runs, "tactic_match_rate"),
        "avg_id_exists_rate": avg_rate(baseline_runs, "id_exists_rate"),
        "avg_phase_conform_rate": avg_rate(baseline_runs, "phase_conform_rate"),
        "avg_path_reachable_rate": avg_rate(baseline_runs, "path_reachable_rate"),
        "scenarios_passed": sum(1 for r in baseline_runs if r.get("report_passed")),
        "scenarios_total": len(baseline_runs),
        "pass_rate": round(sum(1 for r in baseline_runs if r.get("report_passed")) / len(baseline_runs), 2) if baseline_runs else 0.0,
        "subtechnique_usage_rate": subtechnique_rate(baseline_runs),
        "cve_reference_rate": cve_rate(baseline_runs),
    }

    nsmas_summary = {
        "avg_tactic_match_rate": avg_rate(nsmas_runs, "tactic_match_rate"),
        "avg_id_exists_rate": avg_rate(nsmas_runs, "id_exists_rate"),
        "avg_phase_conform_rate": avg_rate(nsmas_runs, "phase_conform_rate"),
        "avg_path_reachable_rate": avg_rate(nsmas_runs, "path_reachable_rate"),
        "scenarios_passed": sum(1 for r in nsmas_runs if r.get("report_passed")),
        "scenarios_total": len(nsmas_runs),
        "pass_rate": round(sum(1 for r in nsmas_runs if r.get("report_passed")) / len(nsmas_runs), 2) if nsmas_runs else 0.0,
        "subtechnique_usage_rate": subtechnique_rate(nsmas_runs),
        "cve_reference_rate": cve_rate(nsmas_runs),
    }

    # Reproduzierbarkeit: nur NS-MAS, pro Szenario Runs 1,2,3 vergleichen
    reproducibility = {}
    for i, scenario in enumerate(SCENARIOS):
        s_name = f"scenario_{i + 1}"
        runs = [r for r in nsmas_runs if r.get("scenario_name") == scenario["name"]]
        runs = sorted(runs, key=lambda x: x.get("repeat", 0))

        if len(runs) >= 3:
            ids1 = set(runs[0].get("technique_ids", []))
            ids2 = set(runs[1].get("technique_ids", []))
            ids3 = set(runs[2].get("technique_ids", []))

            overlap_12 = jaccard(ids1, ids2)
            overlap_13 = jaccard(ids1, ids3)
            overlap_23 = jaccard(ids2, ids3)
            avg_overlap = round((overlap_12 + overlap_13 + overlap_23) / 3, 2)

            tactic_rates = [r.get("tactic_match_rate", 0) for r in runs]
            variance = round(max(tactic_rates) - min(tactic_rates), 2) if tactic_rates else 0.0

            reproducibility[s_name] = {
                "technique_overlap_r1_r2": round(overlap_12, 2),
                "technique_overlap_r1_r3": round(overlap_13, 2),
                "technique_overlap_r2_r3": round(overlap_23, 2),
                "avg_technique_overlap": avg_overlap,
                "all_passed": all(r.get("report_passed") for r in runs),
                "tactic_match_variance": variance,
            }
        else:
            reproducibility[s_name] = {
                "technique_overlap_r1_r2": None,
                "technique_overlap_r1_r3": None,
                "technique_overlap_r2_r3": None,
                "avg_technique_overlap": None,
                "all_passed": False,
                "tactic_match_variance": None,
            }

    # Improvement: Deltas
    tm_b = baseline_summary["avg_tactic_match_rate"]
    tm_n = nsmas_summary["avg_tactic_match_rate"]
    pr_b = baseline_summary["pass_rate"]
    pr_n = nsmas_summary["pass_rate"]
    sub_b = baseline_summary["subtechnique_usage_rate"]
    sub_n = nsmas_summary["subtechnique_usage_rate"]

    def pct_delta(b, n):
        if b == 0:
            return f"+{int(n * 100)}%" if n > 0 else "0%"
        d = (n - b) / b * 100
        return f"+{int(d)}%" if d >= 0 else f"{int(d)}%"

    improvement = {
        "tactic_match_delta": pct_delta(tm_b, tm_n),
        "pass_rate_delta": pct_delta(pr_b, pr_n),
        "subtechnique_delta": pct_delta(sub_b, sub_n),
    }

    return {
        "baseline": baseline_summary,
        "nsmas": nsmas_summary,
        "reproducibility": reproducibility,
        "improvement": improvement,
    }


async def main():
    print("NS-MAS Evaluation – 12 Runs (3 Baseline + 9 NS-MAS)")
    results = []

    # 1. Baseline-Runs (3x)
    for i, scenario in enumerate(SCENARIOS):
        print(f"\nBaseline Run: {scenario['name']}")
        try:
            state = await run_baseline(scenario["payload"])
            err = None
            if state is None:
                err = "Run returned None"
        except Exception as e:
            state = None
            err = str(e)
            logger.exception("Baseline Run fehlgeschlagen")

        results.append(format_result(
            run_id=f"baseline_s{i + 1}",
            scenario_name=scenario["name"],
            mode="baseline",
            repeat=1,
            payload=scenario["payload"],
            state=state,
            error=err,
        ))
        await asyncio.sleep(SLEEP_BETWEEN_RUNS)

    # 2. NS-MAS-Runs (3 Szenarien × 3 Wiederholungen = 9x)
    for i, scenario in enumerate(SCENARIOS):
        for r in range(1, 4):
            print(f"\nNS-MAS Run: {scenario['name']} (Repeat {r}/3)")
            try:
                state = await run_nsmas(scenario["payload"])
                err = None
                if state is None:
                    err = "Run returned None"
            except Exception as e:
                state = None
                err = str(e)
                logger.exception("NS-MAS Run fehlgeschlagen")

            results.append(format_result(
                run_id=f"nsmas_s{i + 1}_r{r}",
                scenario_name=scenario["name"],
                mode="nsmas",
                repeat=r,
                payload=scenario["payload"],
                state=state,
                error=err,
            ))
            await asyncio.sleep(SLEEP_BETWEEN_RUNS)

    # 3. Summary berechnen
    summary = compute_summary(results)

    # 4. Speichern
    output = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(),
            "total_runs": len(results),
            "baseline_runs": 3,
            "nsmas_runs": 9,
        },
        "runs": results,
        "summary": summary,
    }

    output_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation", "comparison")
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2post", action="store_true", help="Output to eval_comparison_v2post.json")
    args = parser.parse_args()
    output_name = "eval_comparison_v2post.json" if args.v2post else "eval_comparison.json"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_name)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # 5. Zusammenfassung auf Konsole
    print("\n" + "=" * 60)
    print("ERGEBNIS")
    print("=" * 60)
    print(f"Baseline avg tactic_match: {summary['baseline']['avg_tactic_match_rate']:.0%}")
    print(f"NS-MAS  avg tactic_match: {summary['nsmas']['avg_tactic_match_rate']:.0%}")
    print(f"Baseline pass_rate: {summary['baseline']['pass_rate']:.0%}")
    print(f"NS-MAS  pass_rate: {summary['nsmas']['pass_rate']:.0%}")
    print(f"Improvement tactic_match: {summary['improvement']['tactic_match_delta']}")
    print(f"Improvement pass_rate: {summary['improvement']['pass_rate_delta']}")
    for s_name, repro in summary["reproducibility"].items():
        avg = repro.get("avg_technique_overlap")
        if avg is not None:
            print(f"Reproducibility {s_name}: avg overlap = {avg:.0%}")
        else:
            print(f"Reproducibility {s_name}: N/A")
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
