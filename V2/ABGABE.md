# Optionales ZIP-Paket (Backend + Evaluations-JSONs)

Dieses Skript packt nur einen Teil von `V2/`; das **vollständige Repository** enthält zusätzlich Frontend, `docs/`, Tests und weitere Skripte.

## Optional: lokales Archiv (nur Backend + JSONs)

Zum Erzeugen eines kompakten ZIP aus dem Backend-Teil und den kanonischen Messdaten:

```bash
cd V2 && ./package_abgabe.sh
```

Ergebnis: `DORA-Szenario-Plattform-V2-abgabe.zip` im Verzeichnis `V2/`. Freiwillige Packhilfe; für den vollen Code siehe das geklonte Repository.

## Inhalt des ZIP (falls erzeugt)

- **Backend:** `backend/app/` (FastAPI, NS-MAS, Agenten, Pipeline)
- **Skripte:** nur `scripts/seed_mitre.py` + `__init__.py` (Neo4j-Befüllung)
- **Konfiguration:** `config/` inkl. `prompts/`
- **Evaluationsdaten** (kanonische n10-/comparison-JSONs):
  - `backend/evaluation/n10/eval_n10_results.json`
  - `backend/evaluation/n10/eval_n10_results_backup_20260323_1027.json`
  - `backend/evaluation/comparison/eval_comparison.json`
- **Metadaten:** `requirements.txt`, `pyproject.toml`, `run.sh`, `.env.example`, `VALIDIERUNGSTESTS_ERGEBNISSE.md`
- **Lesetexte:** `README.md`, diese Datei, `ERGEBNISSE.md`, `backend/evaluation/README.md`

## Ergänzung: Vollständiges Repo

Das optionale ZIP enthält nur einen Teil von `V2/`. **Frontend**, **docs/**, **Tests** und weitere Skripte liegen nur im **vollständigen Klon** des Repositories.
