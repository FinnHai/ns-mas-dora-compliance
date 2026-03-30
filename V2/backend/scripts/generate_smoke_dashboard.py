#!/usr/bin/env python3
"""
Erzeugt eine standalone smoke_results_standalone.html mit eingebetteten Daten.
Nützlich, wenn das Backend nicht läuft – die HTML kann direkt geöffnet werden.

Usage: python -m scripts.generate_smoke_dashboard
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SMOKE_DIR = BACKEND / "evaluation" / "smoke"
TEMPLATE = SMOKE_DIR / "smoke_results_dashboard.html"
OUT = SMOKE_DIR / "smoke_results_standalone.html"


def main() -> int:
    results = []
    for p in sorted(SMOKE_DIR.glob("full_run_*_debug.json")):
        try:
            with open(p, encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Warnung: {p.name}: {e}", file=sys.stderr)

    if not results:
        print(f"Keine full_run_*_debug.json in {SMOKE_DIR} gefunden.")
        return 1

    if not TEMPLATE.exists():
        print(f"Template nicht gefunden: {TEMPLATE}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    embed = f'<script>window.SMOKE_EMBEDDED_DATA = {json.dumps(results)};</script>'
    html = html.replace("<body>", "<body>\n  " + embed)

    OUT.write_text(html, encoding="utf-8")
    print(f"Erstellt: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
