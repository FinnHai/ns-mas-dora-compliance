#!/usr/bin/env python3
"""
Analysiert correction_hints aus run_*.json (S1-S3, 60 Runs).

Eingabe: evaluation/entwicklung_archiv/n10/logs/eval_n10_*/run_*.json
Ausgabe: dieselben Dateien unter entwicklung_archiv/n10/

Usage:
  cd V2/backend && python -m scripts.analyze_correction_hints
"""
import sys
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
ARCHIVE_N10 = SCRIPT_DIR.parent / "evaluation" / "entwicklung_archiv" / "n10"
LOG_ROOT = ARCHIVE_N10 / "logs"
LOG_DIRS = sorted(p for p in LOG_ROOT.glob("eval_n10_*") if p.is_dir())
OUT_JSON = ARCHIVE_N10 / "correction_hints_analysis.json"
OUT_MD = ARCHIVE_N10 / "correction_hints_analysis_report.md"


def _classify_message(msg: str) -> str:
    """Klassifiziert Hinweis nach Fehlertyp."""
    if not msg:
        return "unknown"
    msg = msg.lower()
    if "taktik passt nicht" in msg:
        return "tactic"
    if "kein kausaler pfad" in msg:
        return "path"
    if "phasenreihenfolge verletzt" in msg:
        return "phase"
    if "duplikat" in msg:
        return "duplicate"
    if "existiert nicht" in msg or "nicht im mitre" in msg:
        return "id_exists"
    return "unknown"


def _normalize_tech_id(tid: str) -> str:
    """Normalisiert Technik-ID für Zählung (T1557 vs T1557.001)."""
    return (tid or "").strip()


def main():
    import json

    if not LOG_DIRS:
        print(f"Keine Log-Verzeichnisse unter {LOG_ROOT} (zuerst run_eval_n10_verbose ausführen).", file=sys.stderr)
        sys.exit(1)

    all_hints: list[dict] = []
    by_run: dict[str, list[dict]] = {}
    technique_counts: dict[str, int] = defaultdict(int)
    type_counts: dict[str, int] = defaultdict(int)
    by_scenario_mode: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    example_hints: dict[str, str] = {}  # type -> first example message

    for log_dir in LOG_DIRS:
        if not log_dir.exists():
            print(f"Skip: {log_dir} existiert nicht")
            continue
        for fp in sorted(log_dir.glob("run_*.json")):
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Warnung: {fp}: {e}")
                continue

            run_id = data.get("run_id", fp.stem)
            state = data.get("state", data)
            hints = state.get("correction_hints") or state.get("validation_report", {}).get("correction_hints") or []
            hints = [h if isinstance(h, dict) else {} for h in hints]

            run_hints = []
            for h in hints:
                msg = h.get("message", "")
                tid = _normalize_tech_id(h.get("technique_id", ""))
                hint_type = _classify_message(msg)
                run_hints.append({**h, "_type": hint_type})
                all_hints.append({**h, "_type": hint_type})
                type_counts[hint_type] += 1
                if tid:
                    technique_counts[tid] += 1
                by_scenario_mode[run_id][hint_type] = by_scenario_mode[run_id].get(hint_type, 0) + 1
                if hint_type not in example_hints and len(msg) < 200:
                    example_hints[hint_type] = msg

            by_run[run_id] = run_hints

    total = len(all_hints)
    by_type_rel = {k: round(v / total, 4) if total else 0 for k, v in type_counts.items()}

    top_techniques = sorted(
        [{"id": tid, "count": c} for tid, c in technique_counts.items() if c > 0],
        key=lambda x: -x["count"],
    )[:15]

    by_scenario_mode_agg: dict[str, dict[str, int]] = {}
    for key, counts in by_scenario_mode.items():
        parts = key.split("_")
        if len(parts) >= 3:
            sid, mode = parts[1], parts[0]
            agg_key = f"{sid}_{mode}"
            if agg_key not in by_scenario_mode_agg:
                by_scenario_mode_agg[agg_key] = defaultdict(int)
            for t, c in counts.items():
                by_scenario_mode_agg[agg_key][t] += c
    by_scenario_mode_out = {k: dict(v) for k, v in by_scenario_mode_agg.items()}

    out = {
        "metadata": {
            "source_dirs": [str(d) for d in LOG_DIRS],
            "runs_processed": len(by_run),
            "total_hints": total,
        },
        "by_type": dict(type_counts),
        "by_type_relative": by_type_rel,
        "top_techniques": top_techniques,
        "by_scenario_mode": by_scenario_mode_out,
        "example_hints": example_hints,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Gespeichert: {OUT_JSON}")

    # Markdown Report
    lines = [
        "# Correction Hints – Analyse",
        "",
        f"**Runs:** {len(by_run)} | **Gesamte Hinweise:** {total}",
        "",
        "## Fehlertyp-Häufigkeit",
        "",
        "| Typ | Absolut | Relativ |",
        "|-----|---------|---------|",
    ]
    for t in ["tactic", "path", "phase", "duplicate", "id_exists", "unknown"]:
        c = type_counts.get(t, 0)
        r = by_type_rel.get(t, 0)
        lines.append(f"| {t} | {c} | {r:.1%} |")
    lines.extend([
        "",
        "## Top-Techniken (häufigste Fehlzuordnungen)",
        "",
        "| Technik-ID | Anzahl |",
        "|------------|--------|",
    ])
    for t in top_techniques[:10]:
        lines.append(f"| {t['id']} | {t['count']} |")
    lines.extend([
        "",
        "## Beispiel-Hinweise (pro Typ)",
        "",
    ])
    for t, msg in example_hints.items():
        lines.append(f"**{t}:** \"{msg[:120]}{'…' if len(msg) > 120 else ''}\"")
        lines.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Gespeichert: {OUT_MD}")

    print(f"\nErgebnis: {total} Hinweise in {len(by_run)} Runs")
    print(f"  Taktik: {type_counts.get('tactic', 0)}, Pfad: {type_counts.get('path', 0)}, Phase: {type_counts.get('phase', 0)}, Duplikat: {type_counts.get('duplicate', 0)}")
    return out


if __name__ == "__main__":
    main()
