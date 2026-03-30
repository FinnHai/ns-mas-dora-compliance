#!/usr/bin/env python3
"""
Füllt die Szenario-B-Tabellen in 02_szenario_pakete.md aus den generierten JSONs.

Voraussetzung: run_interview_scenario_b wurde erfolgreich ausgeführt, sodass
interview_sc_b_*.json und interview_sc_b_baseline_*.json existieren.

Usage:
  cd V2/backend && python -m scripts.fill_interview_scenario_b_tables
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INTERVIEW_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "entwicklung_archiv" / "interview"
SCENARIO_PAKETE = INTERVIEW_DIR / "02_szenario_pakete.md"


def _load_json(name: str) -> dict | None:
    path = INTERVIEW_DIR / name
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Fehler beim Lesen von {name}: {e}")
        return None


def _steps_from_ttp(ttp: dict) -> list[tuple[int, str, str, str, str]]:
    """Liefert [(step_num, phase, technique_id, name, tactic), ...]."""
    result = []
    step_num = 1
    phase_order = {"in": 0, "through": 1, "out": 2}
    phases = sorted(ttp.get("phases", []), key=lambda p: phase_order.get(p.get("phase", ""), 1))
    for ps in phases:
        phase = ps.get("phase", "through")
        for s in ps.get("steps", []):
            step_id = s.get("step_id", step_num)
            tech_id = s.get("technique_id", "?")
            name = s.get("technique_name", "?")
            tactic = s.get("tactic", "?")
            result.append((step_num, phase, tech_id, name, tactic))
            step_num += 1
    return result


def _validation_by_position(validation: dict) -> list[bool]:
    """Liefert [tactic_match für Schritt 1, Schritt 2, ...] in Reihenfolge."""
    return [s.get("tactic_match", True) for s in validation.get("steps", [])]


def _table_rows(steps: list, tactic_matches: list[bool]) -> str:
    lines = []
    for i, (step_num, phase, tech_id, name, tactic) in enumerate(steps):
        ok = tactic_matches[i] if i < len(tactic_matches) else True
        korrekt = "✓" if ok else "×"
        name_short = name[:40] + "…" if len(name) > 40 else name
        lines.append(f"| {step_num} | {phase:7} | {tech_id:11} | {name_short:40} | {tactic:18} | {korrekt:6} |")
    return "\n".join(lines)


def main():
    ttp = _load_json("interview_sc_b_ttp.json")
    val = _load_json("interview_sc_b_validation.json")
    ttp_base = _load_json("interview_sc_b_baseline_ttp.json")
    val_base = _load_json("interview_sc_b_baseline_validation.json")

    if not ttp or not val:
        print("NS-MAS JSONs fehlen. Führe zuerst aus:")
        print("  python -m scripts.run_interview_scenario_b --nsmas --baseline")
        sys.exit(1)

    steps_nsmas = _steps_from_ttp(ttp)
    tactic_matches_nsmas = _validation_by_position(val)
    passed = val.get("passed", False)
    iters = val.get("auditor_iterations", 0)
    n = len(steps_nsmas)
    n_val = len(tactic_matches_nsmas)
    tactic_rate = (
        (sum(tactic_matches_nsmas[i] for i in range(min(n, n_val))) + max(0, n - n_val)) / n
        if n else 0
    )

    rows_nsmas = _table_rows(steps_nsmas, tactic_matches_nsmas)
    tactic_match_nsmas = f"{tactic_rate:.2f}" if steps_nsmas else "—"
    status_nsmas = "PASS" if passed else "FAIL"

    baseline_block = ""
    if ttp_base and val_base:
        steps_base = _steps_from_ttp(ttp_base)
        tactic_matches_base = _validation_by_position(val_base)
        rows_base = _table_rows(steps_base, tactic_matches_base)
        passed_base = val_base.get("passed", False)
        n_base = len(steps_base)
        n_val_base = len(tactic_matches_base)
        tactic_rate_base = (
            (sum(tactic_matches_base[i] for i in range(min(n_base, n_val_base))) + max(0, n_base - n_val_base)) / n_base
            if n_base else 0
        )
        baseline_block = f"""### Baseline-Ergebnis (ohne Korrekturschleife)

| Step | Phase  | Technik-ID | Name                                   | Taktik          | Korrekt |
|------|--------|-----------|----------------------------------------|-----------------|---------|
{rows_base}

**Taktik-Match:** {tactic_rate_base:.2f} | **Status:** {"PASS" if passed_base else "FAIL"} | **Iterationen:** 0 (keine Korrektur)

---

"""
    else:
        baseline_block = """### Baseline-Ergebnis (ohne Korrekturschleife)

*(Baseline-Run nicht ausgeführt oder JSONs fehlen. Führe `python -m scripts.run_interview_scenario_b --baseline` aus.)*

| Step | Phase  | Technik-ID | Name                    | Taktik | Korrekt |
|------|--------|-----------|-------------------------|--------|---------|
| …    | …      | …         | …                       | …      | …       |

**Taktik-Match:** — | **Status:** — | **Iterationen:** 0

---

"""

    nsmas_block = f"""### NS-MAS-Ergebnis (mit Korrekturschleife)

| Step | Phase  | Technik-ID | Name                                   | Taktik          | Korrekt |
|------|--------|-----------|----------------------------------------|-----------------|---------|
{rows_nsmas}

**Taktik-Match:** {tactic_match_nsmas} | **Status:** {status_nsmas} | **Iterationen:** {iters}

---
"""

    # Read existing file and replace Szenario B section
    if not SCENARIO_PAKETE.exists():
        print(f"Datei nicht gefunden: {SCENARIO_PAKETE}")
        sys.exit(1)

    content = SCENARIO_PAKETE.read_text(encoding="utf-8")
    marker_start = "## SZENARIO B: APT41 / Atruvia AG"
    idx_start = content.find(marker_start)
    if idx_start == -1:
        print("Marker in 02_szenario_pakete.md nicht gefunden.")
        sys.exit(1)

    new_section = f"""## SZENARIO B: APT41 / Atruvia AG

### Eingabe

- **Zielorganisation:** Atruvia AG (IT-Dienstleister der Genossenschaftsbanken)
- **Bedrohungsakteur:** APT41
- **Scope:** Mehrstufiger Angriff auf die Rechenzentrums-Infrastruktur eines genossenschaftlichen IT-Dienstleisters. Kritische Funktionen: Kernbanksystem (agree21), Zahlungsverkehrsplattform, Online-Banking-Infrastruktur, Anbindung der Mitgliedsbanken. DORA-Kontext: Atruvia als kritischer IKT-Drittdienstleister gemäß Art. 28 DORA. Angriffsziel: Kompromittierung der zentralen Zahlungsverkehrsinfrastruktur über kompromittierte Entwickler-Zugänge.

---

{baseline_block}{nsmas_block}

*Die Tabellen wurden aus den generierten JSONs erzeugt (scripts/fill_interview_scenario_b_tables.py).*
"""

    new_content = content[:idx_start] + new_section
    SCENARIO_PAKETE.write_text(new_content, encoding="utf-8")
    print(f"✓ 02_szenario_pakete.md aktualisiert ({len(steps_nsmas)} NS-MAS-Schritte)")


if __name__ == "__main__":
    main()
