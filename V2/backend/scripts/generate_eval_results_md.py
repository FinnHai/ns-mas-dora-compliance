#!/usr/bin/env python3
"""
Generiert Evaluationsergebnisse S1–S3 aus eval_comparison.json als Markdown.

Erzeugt 00_eval_results_s1_s3.md mit Tabellen für alle Szenarien aus dem Bestand.
Die Tabellen werden aus eval_comparison.json abgeleitet (nicht manuell geschrieben).

Usage:
  cd V2/backend && python -m scripts.generate_eval_results_md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "evaluation"
COMPARISON_JSON = EVAL_DIR / "comparison" / "eval_comparison.json"
OUTPUT_MD = EVAL_DIR / "entwicklung_archiv" / "interview" / "00_eval_results_s1_s3.md"

# Technik-ID -> Taktik-Name (MITRE ATT&CK, vereinfacht)
TECH_TO_TACTIC: dict[str, str] = {
    "T1566": "Initial Access",
    "T1566.001": "Initial Access",
    "T1566.002": "Initial Access",
    "T1037": "Persistence",
    "T1047": "Execution",
    "T1570": "Lateral Movement",
    "T1021": "Lateral Movement",
    "T1021.008": "Lateral Movement",
    "T1091": "Lateral Movement",
    "T1550.003": "Lateral Movement",
    "T1092": "Command and Control",
    "T1020": "Exfiltration",
    "T1029": "Exfiltration",
    "T1052": "Exfiltration",
    "T1496.001": "Impact",
    "T1678": "Defense Evasion",
    "T1518.002": "Discovery",
    "T1531": "Impact",
    "T1657": "Impact",
}

# Taktik -> Phase (kill chain)
TACTIC_TO_PHASE: dict[str, str] = {
    "Initial Access": "in",
    "Execution": "in",
    "Persistence": "through",
    "Privilege Escalation": "through",
    "Defense Evasion": "through",
    "Credential Access": "through",
    "Discovery": "through",
    "Lateral Movement": "through",
    "Collection": "through",
    "Command and Control": "through",
    "Exfiltration": "out",
    "Impact": "out",
}


def _phase(tactic: str) -> str:
    return TACTIC_TO_PHASE.get(tactic, "through")


def _tactic(tech_id: str) -> str:
    return TECH_TO_TACTIC.get(tech_id, TECH_TO_TACTIC.get(tech_id.split(".")[0], "—"))


def _run_to_table(run: dict) -> str:
    ids = run.get("technique_ids", [])
    names = run.get("technique_names", [])
    tactic_ok = run.get("tactic_match_per_step", [])
    path_ok = run.get("path_reachable_per_step", [])
    lines = []
    for i, (tid, name) in enumerate(zip(ids, names)):
        tactic = _tactic(tid)
        phase = _phase(tactic)
        t_ok = tactic_ok[i] if i < len(tactic_ok) else True
        p_ok = path_ok[i] if i < len(path_ok) else True
        ok = "✓" if (t_ok and p_ok) else "×"
        name_short = (name[:40] + "…") if len(name) > 40 else name
        lines.append(f"| {i+1} | {phase} | {tid} | {name_short} | {tactic} | {ok} |")
    return "\n".join(lines) if lines else "| — | — | — | — | — | — |"


def main():
    if not COMPARISON_JSON.exists():
        print(f"Fehlt: {COMPARISON_JSON}")
        sys.exit(1)

    with open(COMPARISON_JSON, encoding="utf-8") as f:
        data = json.load(f)

    runs = {r["run_id"]: r for r in data.get("runs", [])}

    # S1: baseline_s1, nsmas_s1_r1
    # S2: baseline_s2, nsmas_s2_r1
    # S3: baseline_s3, nsmas_s3_r1
    selects = [
        ("S1", "Szenario 1 — APT29 Finanzsektor", "baseline_s1", "nsmas_s1_r1"),
        ("S2", "Szenario 2 — Lazarus Group", "baseline_s2", "nsmas_s2_r1"),
        ("S3", "Szenario 3 — FIN13", "baseline_s3", "nsmas_s3_r1"),
    ]

    parts = [
        "# Evaluationsergebnisse S1–S3 (aus eval_comparison.json)",
        "",
        "*Auto-generiert. Quelle: evaluation/comparison/eval_comparison.json*",
        "",
        "---",
        "",
    ]

    for sid, title, base_id, nsmas_id in selects:
        base = runs.get(base_id)
        nsmas = runs.get(nsmas_id)
        if not base and not nsmas:
            parts.append(f"## {sid}: {title}")
            parts.append("(Keine Daten)")
            parts.append("")
            continue

        parts.append(f"## {sid}: {title}")
        parts.append("")

        if base:
            payload = base.get("payload", {})
            org = payload.get("target_organization", "—")
            threat = payload.get("threat_profile", "—")
            scope = payload.get("scope_document", "—") or "—"
            parts.append("**Eingabe:**")
            parts.append(f"- Zielorganisation: {org}")
            parts.append(f"- Bedrohungsakteur: {threat}")
            parts.append(f"- Scope: {scope[:120]}{'…' if len(scope) > 120 else ''}")
            parts.append("")

            tactic_rate = base.get("tactic_match_rate", 0)
            passed = base.get("report_passed", False)
            iters = base.get("auditor_iterations", 0)

            parts.append("### Baseline")
            parts.append("")
            parts.append("| Step | Phase  | Technik-ID  | Name                                        | Taktik          | Korrekt |")
            parts.append("|------|--------|-------------|---------------------------------------------|-----------------|---------|")
            parts.append(_run_to_table(base))
            parts.append("")
            parts.append(f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** {iters}")
            parts.append("")

        if nsmas:
            tactic_rate = nsmas.get("tactic_match_rate", 0)
            passed = nsmas.get("report_passed", False)
            iters = nsmas.get("auditor_iterations", 0)

            parts.append("### NS-MAS")
            parts.append("")
            parts.append("| Step | Phase  | Technik-ID  | Name                                        | Taktik          | Korrekt |")
            parts.append("|------|--------|-------------|---------------------------------------------|-----------------|---------|")
            parts.append(_run_to_table(nsmas))
            parts.append("")
            parts.append(f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** {iters}")
            parts.append("")

        parts.append("---")
        parts.append("")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(parts), encoding="utf-8")
    print(f"✓ {OUTPUT_MD}")


if __name__ == "__main__":
    main()
