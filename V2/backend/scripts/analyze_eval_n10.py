#!/usr/bin/env python3
"""
Analysiert eval_n10_results.json: Aggregationen, Mann-Whitney-U, Jaccard, Pass-Raten.

Usage:
  cd V2/backend && python -m scripts.analyze_eval_n10
  # Mit S4: Script lädt automatisch S4 aus Backup falls eval nur 60 Runs hat

Ergänzend: analyze_correction_hints.py wertet Korrekturhinweise aus run_*.json
(Voll-State-Logs von run_eval_n10_verbose) aus; siehe ANLEITUNG_EVAL_N10_VERBOSE.md.
"""
import json
from pathlib import Path
from collections import defaultdict

try:
    from scipy.stats import mannwhitneyu
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def _mannwhitneyu_fallback(x: list[float], y: list[float], alternative: str = "greater") -> tuple[float, float]:
    """Mann-Whitney U, einseitig (NS-MAS > Baseline). Fallback ohne scipy."""
    combined = [(v, 0) for v in x] + [(v, 1) for v in y]
    combined.sort(key=lambda t: t[0])
    n1, n2 = len(x), len(y)
    R1 = sum(i + 1 for i, (_, g) in enumerate(combined) if g == 0)
    U1 = n1 * n2 + n1 * (n1 + 1) / 2 - R1
    mu = n1 * n2 / 2
    sigma = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
    if sigma == 0:
        return float(U1), 0.5
    import math
    z = (U1 - mu) / sigma
    # "greater": x stoch. > y => U tends to be small => p = P(U <= u) = left tail = norm.cdf(z)
    p_left = 0.5 * (1 + math.erf(z / (2**0.5)))
    p = p_left if alternative == "greater" else 1 - p_left
    return float(U1), float(min(1, max(0, p)))

SCRIPT_DIR = Path(__file__).resolve().parent
EVAL_DIR = SCRIPT_DIR.parent / "evaluation" / "n10"
ARCHIVE_N10 = SCRIPT_DIR.parent / "evaluation" / "entwicklung_archiv" / "n10"
EVAL_JSON = EVAL_DIR / "eval_n10_results.json"
S4_BACKUP = EVAL_DIR / "eval_n10_results_backup_20260323_1027.json"
OUT_JSON = ARCHIVE_N10 / "eval_n10_analysis.json"
OUT_MD = ARCHIVE_N10 / "eval_n10_analysis_report.md"
OUT_LATEX = ARCHIVE_N10 / "eval_n10_longtable.tex"


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def mean_jaccard(runs: list[dict]) -> float:
    """Paarweise Jaccard über alle Runs, Mittelwert."""
    sets = [set(r.get("technique_ids") or []) for r in runs]
    n = len(sets)
    if n < 2:
        return 1.0
    total, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            total += jaccard(sets[i], sets[j])
            count += 1
    return round(total / count, 4) if count else 0.0


def stable_techniques(runs: list[dict], threshold: float = 0.7) -> tuple[list[str], list[str]]:
    """Techniken mit Auftreten >= threshold (stabil), sonst variable."""
    n = len(runs)
    if n == 0:
        return [], []
    counts: dict[str, int] = defaultdict(int)
    for r in runs:
        for tid in r.get("technique_ids") or []:
            if tid:
                counts[tid] += 1
    stable = [tid for tid, c in counts.items() if c >= n * threshold]
    variable = [tid for tid, c in counts.items() if 0 < c < n * threshold]
    return sorted(stable), sorted(variable)


def main():
    with open(EVAL_JSON) as f:
        data = json.load(f)
    runs = list(data["runs"])

    if len(runs) < 80 and S4_BACKUP.exists():
        with open(S4_BACKUP) as f:
            s4 = json.load(f)
        runs.extend(s4["runs"])
        print(f"+ S4 Backup: {len(runs)} Runs gesamt")

    by_scenario_mode: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in runs:
        sid = r.get("scenario", "")
        mode = r.get("mode", "")
        key = f"{sid}_{mode}"
        by_scenario_mode[sid][mode].append(r)

    scenarios = ["s1", "s2", "s3", "s4"]
    modes = ["baseline", "nsmas"]

    # Aggregationen
    agg = {}
    for sid in scenarios:
        agg[sid] = {}
        for mode in modes:
            rs = by_scenario_mode.get(sid, {}).get(mode, [])
            if not rs:
                continue
            agg[sid][mode] = {
                "n": len(rs),
                "tactic_match_rate": round(sum(r["tactic_match_rate"] for r in rs) / len(rs), 4),
                "path_reachable_rate": round(sum(r["path_reachable_rate"] for r in rs) / len(rs), 4),
                "id_exists_rate": round(sum(r["id_exists_rate"] for r in rs) / len(rs), 4),
                "phase_conform_rate": round(sum(r["phase_conform_rate"] for r in rs) / len(rs), 4),
                "pass_count": sum(1 for r in rs if r.get("report_passed")),
                "auditor_iter_mean": round(sum(r.get("auditor_iterations", 0) for r in rs) / len(rs), 1),
                "duration_mean": round(sum(r.get("duration_seconds", 0) for r in rs) / len(rs), 1),
            }

    # Mann-Whitney-U
    def _run_mwu(nsmas_vals, base_vals):
        if len(set(nsmas_vals)) == 1 and len(set(base_vals)) == 1 and nsmas_vals[0] == base_vals[0]:
            return {"U": None, "p": None, "sig": "identisch"}
        if HAS_SCIPY:
            u, p = mannwhitneyu(nsmas_vals, base_vals, alternative="greater")
        else:
            u, p = _mannwhitneyu_fallback(nsmas_vals, base_vals, "greater")
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
        return {"U": round(float(u), 1), "p": round(float(p), 4), "sig": sig}

    mwu = {}
    for sid in scenarios:
        base = [r["tactic_match_rate"] for r in by_scenario_mode.get(sid, {}).get("baseline", [])]
        nsmas = [r["tactic_match_rate"] for r in by_scenario_mode.get(sid, {}).get("nsmas", [])]
        if not base or not nsmas:
            continue
        mwu[sid] = {"tactic_match": _run_mwu(nsmas, base)}
        base_p = [r["path_reachable_rate"] for r in by_scenario_mode.get(sid, {}).get("baseline", [])]
        nsmas_p = [r["path_reachable_rate"] for r in by_scenario_mode.get(sid, {}).get("nsmas", [])]
        mwu[sid]["path_reachable"] = _run_mwu(nsmas_p, base_p)

    # Jaccard + stabile Techniken
    jacc = {}
    for sid in scenarios:
        jacc[sid] = {}
        for mode in modes:
            rs = by_scenario_mode.get(sid, {}).get(mode, [])
            if len(rs) < 2:
                jacc[sid][mode] = {"mean": 1.0, "stable": [], "variable": []}
                continue
            stab, var = stable_techniques(rs)
            jacc[sid][mode] = {
                "mean": mean_jaccard(rs),
                "stable": stab,
                "variable": var[:15],
            }

    # Exemplar S2
    base_s2 = by_scenario_mode.get("s2", {}).get("baseline", [])
    nsmas_s2 = by_scenario_mode.get("s2", {}).get("nsmas", [])
    exemplar_baseline = next((r for r in base_s2 if not r.get("report_passed") and r.get("technique_ids")), base_s2[0] if base_s2 else None)
    exemplar_nsmas = next((r for r in nsmas_s2 if r.get("report_passed") and r.get("technique_ids")), nsmas_s2[-1] if nsmas_s2 else None)

    out = {
        "metadata": {"source": str(EVAL_JSON), "total_runs": len(runs)},
        "aggregations": agg,
        "mann_whitney_u": mwu,
        "jaccard": jacc,
        "exemplar_s2": {
            "baseline": exemplar_baseline,
            "nsmas": exemplar_nsmas,
        } if exemplar_baseline and exemplar_nsmas else None,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Gespeichert: {OUT_JSON}")

    # Markdown Report
    lines = [
        "# Eval N10 – Analyse-Report",
        "",
        "## Aggregationen (Mittelwerte pro Szenario/Modus)",
        "",
        "| Szenario | Modus | Taktik-Match | Pfad-Erreichb. | Pass | Ø Iter | Ø t(s) |",
        "|----------|-------|--------------|----------------|------|--------|--------|",
    ]
    for sid in scenarios:
        for mode in modes:
            a = agg.get(sid, {}).get(mode)
            if not a:
                continue
            pass_str = f"{a['pass_count']}/10"
            lines.append(f"| {sid.upper()} | {mode} | {a['tactic_match_rate']:.3f} | {a['path_reachable_rate']:.3f} | {pass_str} | {a['auditor_iter_mean']} | {a['duration_mean']} |")

    lines.extend([
        "",
        "## Mann-Whitney-U (NS-MAS > Baseline)",
        "",
        "| Szenario | Metrik | U | p | Sig. |",
        "|----------|--------|---|---|------|",
    ])
    for sid in scenarios:
        m = mwu.get(sid, {})
        for met in ["tactic_match", "path_reachable"]:
            mm = m.get(met, {})
            u = mm.get("U", "-")
            p = mm.get("p", "-")
            sig = mm.get("sig", "-")
            if isinstance(u, float):
                u = f"{u:.1f}"
            if isinstance(p, float):
                p = f"{p:.4f}" if p >= 0.001 else "<0.001"
            lines.append(f"| {sid.upper()} | {met} | {u} | {p} | {sig} |")

    lines.extend([
        "",
        "## Jaccard (Reproduzierbarkeit)",
        "",
        "| Szenario | NS-MAS | Baseline | Stabile (NS-MAS) |",
        "|----------|--------|----------|------------------|",
    ])
    for sid in scenarios:
        jn = jacc.get(sid, {}).get("nsmas", {})
        jb = jacc.get(sid, {}).get("baseline", {})
        stab = ", ".join(jn.get("stable", [])[:8]) or "-"
        lines.append(f"| {sid.upper()} | {jn.get('mean', 0):.3f} | {jb.get('mean', 0):.3f} | {stab} |")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print(f"Gespeichert: {OUT_MD}")

    # LaTeX Longtable
    def sort_key(r):
        sid = r.get("scenario", "s1")
        mode = r.get("mode", "nsmas")
        rep = r.get("repeat", 1)
        order = {"s1": 0, "s2": 1, "s3": 2, "s4": 3}[sid]
        mode_order = 0 if mode == "nsmas" else 1
        return (order, mode_order, rep)

    sorted_runs = sorted(runs, key=sort_key)
    latex_lines = []
    prev_key = None
    for i, r in enumerate(sorted_runs):
        sid = r.get("scenario", "s1")
        mode = r.get("mode", "nsmas")
        key = (sid, mode)
        if key != prev_key:
            if prev_key is not None:
                latex_lines.append(r"\midrule")
            label = sid.upper() + " " + ("NS-MAS" if mode == "nsmas" else "Baseline")
            latex_lines.append(f"% --- {label} ---")
            prev_key = key
        rid = r.get("run_id", "").replace("_", r"\_")
        mode_str = "NS-MAS" if mode == "nsmas" else "Baseline"
        tact = r.get("tactic_match_rate", 0)
        path = r.get("path_reachable_rate", 0)
        passed = r.get("report_passed", False)
        pass_sym = r"\checkmark" if passed else r"$\times$"
        iters = r.get("auditor_iterations", 0)
        steps = r.get("num_steps", 0)
        dur = r.get("duration_seconds", 0)
        tact_fmt = f"{tact:.3f}".replace(".", "{,}")
        path_fmt = f"{path:.3f}".replace(".", "{,}")
        dur_fmt = f"{dur:.1f}".replace(".", "{,}")
        row = rf"{rid} & {sid.upper()} & {mode_str} & {tact_fmt} & {path_fmt} & {pass_sym} & {iters} & {steps} & {dur_fmt}"
        if i % 2 == 0:
            latex_lines.append(r"\rowcolor{gray!5}")
        latex_lines.append(row + r" \\")
    latex_content = "\n".join(latex_lines)
    with open(OUT_LATEX, "w") as f:
        f.write(latex_content)
    print(f"Gespeichert: {OUT_LATEX}")
    return out

if __name__ == "__main__":
    main()
