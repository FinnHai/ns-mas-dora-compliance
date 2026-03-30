# DORA Szenario-Plattform – Frontend

React + TypeScript + Vite Frontend für das neuro-symbolische Multi-Agenten-System (NS-MAS) zur DORA-Szenario-Entwicklung.

## Seiten

| Route | Beschreibung |
|-------|--------------|
| `/` | Dashboard – Übersicht, Szenario-Liste, Links |
| `/scenario` | Neues Szenario – Bedrohungskontext eingeben, Generierung starten |
| `/scenario/:id` | Szenario-Details – MITRE-Validierung, Execution Trace |
| `/validation/:id` | Validierungsansicht – Action Alignment Score, Event-Details |
| `/evaluate` | Vergleich – Neuro-symbolisch vs. Baseline (reines LLM) |
| `/ns-mas` | NS-MAS Pipeline – Planner → Generator → Auditor → Human Review → Synthesizer |

## NS-MAS Pipeline

Die NS-MAS-Seite (`/ns-mas`) steuert die vollständige Pipeline:

1. **Scenario Planner** – High-Level-Angriffsskizze (Phasen in/through/out)
2. **TTP Generator** – Konkrete MITRE ATT&CK Schritte (mit RAG)
3. **KG Auditor** – Validierung gegen Neo4j (max. 3 Iterationen)
4. **Human Review Gate** – Manuelle Freigabe vor Report
5. **Report Synthesizer** – TIBER-EU MSEL-Format

Eingabe: Zielorganisation, Bedrohungsprofil (z.B. APT29), optional Scope. Bei Human Review: Freigeben oder Ablehnen.

## Entwicklung

```bash
npm install
npm run dev      # Dev-Server auf http://localhost:5173
npm run build    # Produktions-Build
npm run preview  # Vorschau des Builds
```

### BA-Screenshots (KG Auditor + Human Review)

**Variante A – echter Pipeline-Lauf (empfohlen für Prüfer:innen):** Backend auf Port 8000 (Neo4j, `.env`), Frontend Dev-Server auf 5173. Dann:

```bash
npx playwright install chromium
npm run dev          # Terminal 1
npm run capture-thesis-screenshots:live   # Terminal 2
```

Playwright lädt S2 über „Eval S2 (Bundesbank / Lazarus)“, startet die Pipeline und speichert die PNGs nach Erreichen des Human-Review-Zustands. Timeout standardmäßig 12 Min (`THESIS_PIPELINE_TIMEOUT_MS` überschreibbar).

**Variante B – statische Fixture (ohne Backend):** `http://localhost:5173/ns-mas?fixture=thesis-s2-hitl` im Browser, oder:

```bash
npm run dev
npm run capture-thesis-screenshots
```

Gleiche React-Komponenten wie in A, aber feste Demo-Daten aus `fixtures/nsMasThesisS2Fixture.ts` (inhaltlich an Kap. 4.4 / Eval S2 angelehnt).

Ausgabe (beide Varianten): `Projekt Latex BA/figures/screenshot_validierung.png` und `screenshot_human_review.png`.

## API-Client

Der Client (`src/api/client.ts`) spricht das Backend unter `http://localhost:8000` an:

- `generateScenario` / `generateScenarioStream` – Szenario-Generierung
- `validateScenario` – Action Alignment Score
- `evaluateCompare` – Neuro vs. Baseline
- `nsMasRun` / `nsMasResume` – NS-MAS Pipeline (mit Human Review)
