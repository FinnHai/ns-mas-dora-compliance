#!/usr/bin/env python3
"""
Erzeugt eine standalone eval_n10_dashboard.html mit eingebetteten Daten.
Nützlich, wenn das Backend nicht läuft.

Usage: python -m scripts.generate_eval_n10_dashboard
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
EVAL_N10 = BACKEND / "evaluation" / "n10"
ARCHIVE_N10 = BACKEND / "evaluation" / "entwicklung_archiv" / "n10"
TEMPLATE = ARCHIVE_N10 / "eval_n10_dashboard.html"
OUT = ARCHIVE_N10 / "eval_n10_standalone.html"
DATA = EVAL_N10 / "eval_n10_results.json"


def main() -> int:
    if not DATA.exists():
        print(f"Keine {DATA.name} gefunden.")
        return 1

    if not TEMPLATE.exists():
        print(f"Template nicht gefunden: {TEMPLATE}")
        return 1

    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    html = TEMPLATE.read_text(encoding="utf-8")
    embed = f'<script>window.EVAL_N10_EMBEDDED_DATA = {json.dumps(data)};</script>'
    html = html.replace("<body>", "<body>\n  " + embed)

    OUT.write_text(html, encoding="utf-8")
    print(f"Erstellt: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
