# Evaluationsdaten (kanonische JSONs)

In diesem Ordner liegen die maschinenlesbaren **Referenzmessdaten** der Evaluation:

| Datei | Inhalt |
|-------|--------|
| `n10/eval_n10_results.json` | S1–S3 (60 Runs: NS-MAS + Baseline) |
| `n10/eval_n10_results_backup_20260323_1027.json` | S4 (20 Runs) |
| `comparison/eval_comparison.json` | Vergleichsläufe inkl. Walkthrough-Daten (`nsmas_s2_r1`) |

Alle **übrigen** Rohdaten (Verbose-Logs, Interview-Szenario B, Smoke-Tests, Dashboards, Analysen, verworfene Läufe) befinden sich unter **`entwicklung_archiv/`** — nicht gelöscht, nur ausgelagert. Siehe [entwicklung_archiv/README.md](entwicklung_archiv/README.md).

## Reproduktion der 80-Run-Evaluation

Erfordert das vollständige Repository inkl. `scripts/run_eval_n10_verbose.py` (laufendes Backend, Neo4j, API). Neue Läufe schreiben wieder unter `n10/logs/…`; nach Abschluss kannst du alte Logs bei Bedarf nach `entwicklung_archiv/n10/logs/` verschieben.

```bash
cd backend && source .venv/bin/activate
python -m scripts.run_eval_n10_verbose
```

## Qualitative Evaluation (Szenario B)

Artefakte unter `entwicklung_archiv/interview/`; Backend-Endpunkt `GET /evaluation/generated` liest von dort.
