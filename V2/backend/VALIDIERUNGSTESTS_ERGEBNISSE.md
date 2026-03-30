# NS-MAS Validierungstests – Ergebnisse

**Datum:** 2026-03-20  
**Backend:** V2/backend  
**Neo4j:** dora-neo4j (bolt://localhost:7688)

---

## 1. Knowledge Graph – Neo4j-Queries ✓

| Prüfung | Ergebnis | Erwartung |
|---------|----------|-----------|
| Technique-Knoten | 823 | > 200 |
| Tactic-Knoten | 28 | 14 (oder mehr) |
| Phase-Knoten | 3 | - |
| Group-Knoten | 172 | > 0 |
| PRECEDES-Kanten | 157.396 | > 0 |
| T1566.001 existiert | JA (Spearphishing Attachment) | JA |
| Lazarus Group Techniken | 10+ gefunden | vorhanden |
| PRECEDES-Pfad T1566.001→T1570 | Pfadlänge: 2 | existiert |

**Script:** `python -m scripts.run_neo4j_validation_queries`

---

## 2. KG Auditor – Fake-Input-Tests

| Test | Ergebnis |
|------|----------|
| 2a) Fake-Tech-ID T9999 + CVE-9999-9999 | ✓ PASSED – id_exists=False, cve_valid=False |
| 2b) Phasenreihenfolge (out vor in) | ⏭ SKIP – TTPScenario sortiert Phasen immer; Szenario nicht darstellbar |

**Script:** `pytest tests/test_kg_auditor_integration.py -v -m integration`

---

## 3. Iterationsschleife – Logging ✓

Logging in `ns_mas_pipeline.py` (kg_auditor_node):
```
Auditor Iteration %d | Passed: %s | Hints: %s | Technique IDs: %s
```

---

## 4. RAG Retriever – Kontext-Logging ✓

Logging in `ttp_generator.py` (_build_rag_context):
```
RAG corpus size: %d | Top-3 retrieved: %s
```

---

## 5. Temperature – Verifikation ✓

Logging in `ttp_generator.py`:
```
LLM temperature: %s (config: %s)
```
Config: `llm_temperature: float = 0.0` (config.py)

---

## 6. Human Review Gate

**Manueller Test:** `curl -X POST http://localhost:8000/ns-mas/run ...`  
**Erwartung:** `status: "awaiting_approval"` (nicht `completed`)

---

## 7. Duplikat-Check ✓

Code-Verifikation in `kg_auditor.py`:
- Zeile 117: `prev_tech_id_full` (vollständige ID)
- Zeile 153: `dup_warning = prev_tech_id_full == tech_id_full`
- T1566.001 ≠ T1566.002 werden korrekt unterschieden

---

## 8. Smoke Test S2

**Script:** `python -m scripts.run_smoke_test_s2`  
**Output:** `full_run_s2_debug.json` (wird bei erfolgreichem Durchlauf erstellt)

---

## Abhängigkeiten

- Neo4j: `docker start dora-neo4j`
- Backend: `./run.sh`
- Optional: `OPENAI_API_KEY` oder `ANTHROPIC_API_KEY` in `.env` für LLM-Calls
