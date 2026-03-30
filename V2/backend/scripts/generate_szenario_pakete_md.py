#!/usr/bin/env python3
"""
Generiert Dokument 2: Szenario-Pakete (02_szenario_pakete.md) im Plan-Format.

- Szenario A (Lazarus/Bundesbank): aus eval_comparison.json (baseline_s2, nsmas_s2_r1)
- Szenario B (Atruvia/APT41): aus interview_sc_b_*.json wenn vorhanden, sonst Platzhalter
- Option 3: --use-s3-for-b ersetzt Szenario B durch S3 (FIN13/Sparkasse) aus eval_comparison

Usage:
  cd V2/backend && python -m scripts.generate_szenario_pakete_md
  cd V2/backend && python -m scripts.generate_szenario_pakete_md --use-s3-for-b
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "evaluation"
INTERVIEW_DIR = EVAL_DIR / "entwicklung_archiv" / "interview"
COMPARISON_JSON = EVAL_DIR / "comparison" / "eval_comparison.json"
OUTPUT_MD = INTERVIEW_DIR / "02_szenario_pakete.md"

# Technik-ID -> Taktik (S1, S2, S3, Szenario B)
TECH_TO_TACTIC: dict[str, str] = {
    "T1566": "Initial Access", "T1566.001": "Initial Access", "T1566.002": "Initial Access",
    "T1037": "Persistence", "T1037.005": "Persistence", "T1047": "Execution",
    "T1059.001": "Execution", "T1570": "Lateral Movement", "T1018": "Discovery",
    "T1021": "Lateral Movement", "T1021.008": "Lateral Movement", "T1091": "Lateral Movement",
    "T1550.003": "Lateral Movement", "T1092": "Command and Control",
    "T1020": "Exfiltration", "T1029": "Exfiltration", "T1030": "Exfiltration", "T1052": "Exfiltration",
    "T1049": "Discovery", "T1055": "Privilege Escalation",
    "T1496.001": "Impact", "T1678": "Defense Evasion", "T1518.002": "Discovery",
    "T1531": "Impact", "T1657": "Impact",
}
TACTIC_TO_PHASE: dict[str, str] = {
    "Initial Access": "in", "Execution": "in", "Persistence": "through",
    "Privilege Escalation": "through", "Defense Evasion": "through",
    "Credential Access": "through", "Discovery": "through", "Lateral Movement": "through",
    "Collection": "through", "Command and Control": "through",
    "Exfiltration": "out", "Impact": "out",
}


def _phase(tactic: str) -> str:
    return TACTIC_TO_PHASE.get(tactic, "through")


def _tactic(tech_id: str) -> str:
    return TECH_TO_TACTIC.get(tech_id, TECH_TO_TACTIC.get(tech_id.split(".")[0], "—"))


def _eval_run_to_table(run: dict) -> str:
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
        lines.append(f"| {i+1} | {phase:7} | {tid:11} | {name_short:40} | {tactic:18} | {ok:6} |")
    return "\n".join(lines) if lines else "| — | — | — | — | — | — |"


def _baseline_error_hints(run: dict) -> list[str]:
    """Erzeugt 'Fehlerhafte Schritte' aus Baseline-Run."""
    hints = []
    ids = run.get("technique_ids", [])
    names = run.get("technique_names", [])
    tactic_ok = run.get("tactic_match_per_step", [])
    path_ok = run.get("path_reachable_per_step", [])
    for i in range(len(ids)):
        t_ok = tactic_ok[i] if i < len(tactic_ok) else True
        p_ok = path_ok[i] if i < len(path_ok) else True
        if not t_ok:
            tid = ids[i]
            tactic = _tactic(tid)
            phase = _phase(tactic)
            hints.append(
                f"- **Step {i+1}:** {tid} ({names[i] if i < len(names) else '?'}) gehört zur Taktik *{tactic}*, "
                f"die der *{phase}*-Phase zugeordnet ist. Phaseninkonformität."
            )
        elif not p_ok:
            tid = ids[i]
            hints.append(
                f"- **Step {i+1}:** Kein kausaler Pfad von {tid} ({names[i] if i < len(names) else '?'}) "
                f"zum vorherigen Schritt im Knowledge Graph — `path_reachable: false`."
            )
    return hints


def _gen_szenario_a(data: dict) -> str:
    base = data.get("baseline_s2")
    nsmas = data.get("nsmas_s2_r1")
    if not base and not nsmas:
        return "## SZENARIO A: Lazarus Group / Deutsche Bundesbank\n\n(Keine Daten in eval_comparison.json)\n\n---\n"

    parts = [
        "## SZENARIO A: Lazarus Group / Deutsche Bundesbank",
        "",
        "### Eingabe",
        "",
        "- **Zielorganisation:** Deutsche Bundesbank",
        "- **Bedrohungsakteur:** Lazarus Group",
        "- **Scope:** Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.",
        "",
        "---",
        "",
    ]

    if base:
        tactic_rate = base.get("tactic_match_rate", 0)
        passed = base.get("report_passed", False)
        iters = 0  # Baseline: keine Korrekturschleife
        parts.extend([
            "### Baseline-Ergebnis (ohne Korrekturschleife)",
            "",
            "| Step | Phase  | Technik-ID  | Name                                     | Taktik          | Korrekt |",
            "|------|--------|-------------|------------------------------------------|-----------------|---------|",
            _eval_run_to_table(base),
            "",
            f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** {iters} (keine Korrektur)",
            "",
        ])
        err_hints = _baseline_error_hints(base)
        if err_hints:
            parts.append("**Fehlerhafte Schritte:**")
            parts.extend(err_hints)
            parts.append("")
        parts.append("---")
        parts.append("")

    if nsmas:
        tactic_rate = nsmas.get("tactic_match_rate", 0)
        passed = nsmas.get("report_passed", False)
        iters = nsmas.get("auditor_iterations", 0)
        parts.extend([
            "### NS-MAS-Ergebnis (mit Korrekturschleife)",
            "",
            "| Step | Phase  | Technik-ID  | Name                                     | Taktik          | Korrekt |",
            "|------|--------|-------------|------------------------------------------|-----------------|---------|",
            _eval_run_to_table(nsmas),
            "",
            f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** {iters}",
            "",
            "---",
            "",
        ])
    return "\n".join(parts)


def _gen_szenario_b_from_s3(data: dict) -> str:
    """Option 3: Szenario B durch S3 (FIN13/Sparkasse) ersetzen – zwei funktionierende Showcases."""
    base = data.get("baseline_s3")
    nsmas = data.get("nsmas_s3_r1")
    if not base and not nsmas:
        return "## SZENARIO B: FIN13 / Sparkasse Münsterland Ost (Option 3)\n\n(Keine S3-Daten in eval_comparison.json)\n\n---\n"

    parts = [
        "## SZENARIO B: FIN13 / Sparkasse Münsterland Ost (Option 3 – ersetzt APT41/Atruvia)",
        "",
        "**Hinweis:** Szenario B zeigt S3-Daten als zweiten funktionierenden Showcase (Baseline FAIL → NS-MAS PASS). Atruvia-Bezug entfällt.",
        "",
        "### Eingabe",
        "",
        "- **Zielorganisation:** Sparkasse Münsterland Ost",
        "- **Bedrohungsakteur:** FIN13",
        "- **Scope:** Ransomware-Angriff auf Kernbanksystem. Kritische Funktionen: Kontoführung, Kartenverarbeitung, Backup-Infrastruktur.",
        "",
        "---",
        "",
    ]

    if base:
        tactic_rate = base.get("tactic_match_rate", 0)
        passed = base.get("report_passed", False)
        parts.extend([
            "### Baseline-Ergebnis (ohne Korrekturschleife)",
            "",
            "| Step | Phase  | Technik-ID  | Name                                     | Taktik          | Korrekt |",
            "|------|--------|-------------|------------------------------------------|-----------------|---------|",
            _eval_run_to_table(base),
            "",
            f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** 0 (keine Korrektur)",
            "",
        ])
        err_hints = _baseline_error_hints(base)
        if err_hints:
            parts.append("**Fehlerhafte Schritte:**")
            parts.extend(err_hints)
            parts.append("")
        parts.extend(["---", ""])

    if nsmas:
        tactic_rate = nsmas.get("tactic_match_rate", 0)
        passed = nsmas.get("report_passed", False)
        iters = nsmas.get("auditor_iterations", 0)
        parts.extend([
            "### NS-MAS-Ergebnis (mit Korrekturschleife)",
            "",
            "| Step | Phase  | Technik-ID  | Name                                     | Taktik          | Korrekt |",
            "|------|--------|-------------|------------------------------------------|-----------------|---------|",
            _eval_run_to_table(nsmas),
            "",
            f"**Taktik-Match:** {tactic_rate:.2f} | **Status:** {'PASS' if passed else 'FAIL'} | **Iterationen:** {iters}",
            "",
            "---",
            "",
        ])
    parts.append("")
    parts.append("*Auto-generiert durch scripts/generate_szenario_pakete_md.py --use-s3-for-b*")
    return "\n".join(parts)


def _load_json(name: str) -> dict | None:
    p = INTERVIEW_DIR / name
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _steps_from_ttp(ttp: dict) -> list[tuple[int, str, str, str, str]]:
    result = []
    step_num = 1
    phase_order = {"in": 0, "through": 1, "out": 2}
    phases = sorted(ttp.get("phases", []), key=lambda p: phase_order.get(p.get("phase", ""), 1))
    for ps in phases:
        phase = ps.get("phase", "through")
        for s in ps.get("steps", []):
            tech_id = s.get("technique_id", "?")
            name = s.get("technique_name", "?")
            tactic = s.get("tactic", "?")
            result.append((step_num, phase, tech_id, name, tactic))
            step_num += 1
    return result


def _gen_szenario_b() -> str:
    ttp = _load_json("interview_sc_b_ttp.json")
    val = _load_json("interview_sc_b_validation.json")
    ttp_base = _load_json("interview_sc_b_baseline_ttp.json")
    val_base = _load_json("interview_sc_b_baseline_validation.json")

    parts = [
        "## SZENARIO B: APT41 / Atruvia AG",
        "",
        "### Eingabe",
        "",
        "- **Zielorganisation:** Atruvia AG (IT-Dienstleister der Genossenschaftsbanken)",
        "- **Bedrohungsakteur:** APT41",
        "- **Scope:** Mehrstufiger Angriff auf die Rechenzentrums-Infrastruktur eines genossenschaftlichen IT-Dienstleisters. Kritische Funktionen: Kernbanksystem (agree21), Zahlungsverkehrsplattform, Online-Banking-Infrastruktur, Anbindung der Mitgliedsbanken. DORA-Kontext: Atruvia als kritischer IKT-Drittdienstleister gemäß Art. 28 DORA. Angriffsziel: Kompromittierung der zentralen Zahlungsverkehrsinfrastruktur über kompromittierte Entwickler-Zugänge.",
        "",
        "---",
        "",
    ]

    header = "| Step | Phase  | Technik-ID  | Name                                     | Taktik          | Korrekt |"
    sep = "|------|--------|-------------|------------------------------------------|-----------------|---------|"

    if ttp_base and val_base:
        steps = _steps_from_ttp(ttp_base)
        matches = [s.get("tactic_match", True) for s in val_base.get("steps", [])]
        rows = []
        for i, (sn, ph, tid, nm, tac) in enumerate(steps):
            ok = "✓" if (i < len(matches) and matches[i]) else "×"
            nm_short = nm[:40] + "…" if len(nm) > 40 else nm
            rows.append(f"| {sn} | {ph:7} | {tid:11} | {nm_short:40} | {tac:18} | {ok:6} |")
        tr = sum(matches[i] for i in range(min(len(steps), len(matches)))) / len(steps) if steps else 0
        parts.extend([
            "### Baseline-Ergebnis (ohne Korrekturschleife)",
            "",
            header, sep, "\n".join(rows), "",
            f"**Taktik-Match:** {tr:.2f} | **Status:** {'PASS' if val_base.get('passed') else 'FAIL'} | **Iterationen:** 0 (keine Korrektur)",
            "", "---", "",
        ])
    else:
        parts.extend([
            "### Baseline-Ergebnis (ohne Korrekturschleife)",
            "",
            "*(Nach Durchführung des Runs: `python -m scripts.run_interview_scenario_b --baseline`)*",
            "",
            header, sep, "| … | … | … | … | … | … |", "",
            "**Taktik-Match:** — | **Status:** — | **Iterationen:** 0", "", "---", "",
        ])

    if ttp and val:
        steps = _steps_from_ttp(ttp)
        matches = [s.get("tactic_match", True) for s in val.get("steps", [])]
        rows = []
        for i, (sn, ph, tid, nm, tac) in enumerate(steps):
            ok = "✓" if (i < len(matches) and matches[i]) else "×"
            nm_short = nm[:40] + "…" if len(nm) > 40 else nm
            rows.append(f"| {sn} | {ph:7} | {tid:11} | {nm_short:40} | {tac:18} | {ok:6} |")
        tr = sum(matches[i] for i in range(min(len(steps), len(matches)))) / len(steps) if steps else 0
        parts.extend([
            "### NS-MAS-Ergebnis (mit Korrekturschleife)",
            "",
            header, sep, "\n".join(rows), "",
            f"**Taktik-Match:** {tr:.2f} | **Status:** {'PASS' if val.get('passed') else 'FAIL'} | **Iterationen:** {val.get('auditor_iterations', '—')}",
            "", "---", "",
        ])
    else:
        parts.extend([
            "### NS-MAS-Ergebnis (mit Korrekturschleife)",
            "",
            "*(Nach Durchführung des Runs: `python -m scripts.run_interview_scenario_b --nsmas`)*",
            "",
            header, sep, "| … | … | … | … | … | … |", "",
            "**Taktik-Match:** — | **Status:** — | **Iterationen:** —", "", "---", "",
        ])

    # Option 2 Fallback: Hinweis, wenn Baseline PASS aber NS-MAS FAIL (invertiertes Szenario)
    baseline_passed = val_base.get("passed", False) if val_base else False
    nsmas_passed = val.get("passed", False) if val else False
    if baseline_passed and not nsmas_passed:
        parts.extend([
            "",
            "> **Hinweis zum Szenario B (Option 2 – ehrliche Darstellung):** In diesem Fall hat die Baseline zufällig ein korrektes, aber einfacheres Szenario erzeugt. NS-MAS hat ein komplexeres Szenario angestrebt und ist an der Korrekturgrenze gescheitert. Dies entspricht dem bekannten Muster aus S4: Mehr Komplexität erzeugt mehr Fehlerfläche.",
            "",
        ])

    parts.append("")
    parts.append("*Auto-generiert durch scripts/generate_szenario_pakete_md.py*")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Generiert 02_szenario_pakete.md")
    parser.add_argument("--use-s3-for-b", action="store_true", help="Option 3: Szenario B durch S3 (FIN13/Sparkasse) ersetzen – zwei funktionierende Showcases")
    args = parser.parse_args()

    # Szenario A aus eval_comparison
    eval_data = {}
    if COMPARISON_JSON.exists():
        with open(COMPARISON_JSON, encoding="utf-8") as f:
            runs = json.load(f).get("runs", [])
        eval_data = {r["run_id"]: r for r in runs}

    szenario_a = _gen_szenario_a(eval_data)
    szenario_b = _gen_szenario_b_from_s3(eval_data) if args.use_s3_for_b else _gen_szenario_b()

    content = [
        "# Szenario-Pakete — Qualitative Evaluation NS-MAS",
        "",
        "---",
        "",
        szenario_a,
        szenario_b,
    ]

    INTERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(content), encoding="utf-8")
    suffix = " (Option 3: S3 für B)" if args.use_s3_for_b else ""
    print(f"✓ {OUTPUT_MD} (Dokument 2: Szenario-Pakete{suffix})")


if __name__ == "__main__":
    main()
