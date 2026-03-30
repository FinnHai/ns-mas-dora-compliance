# DORA Szenario-Plattform | High-Level Architektur

## Übersicht

Die Plattform ist ein **neuro-symbolisches Multi-Agenten-System (NS-MAS)** zur Unterstützung der Szenario-Entwicklung im Kontext von DORA (Digital Operational Resilience Act). Sie kombiniert LLM-basierte Generierung mit wissensgraph-basierter Validierung (MITRE ATT&CK).

---

## High-Level Architekturdiagramm

![Architektur](v2_architecture.png)

### Mermaid-Quelle (für Editoren mit Mermaid-Support)

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        User[Benutzer]
        Browser[Browser]
    end

    subgraph Frontend["Frontend (React + Vite :5173)"]
        Dashboard[Dashboard]
        Scenario[Scenario]
        Validation[Validation]
        Evaluate[Evaluate]
        NSMAS[NS-MAS Pipeline]
    end

    subgraph Backend["Backend (FastAPI :8000)"]
        API[API Gateway]
        
        subgraph Routes["API Routes"]
            R1[scenarios]
            R2[validation]
            R3[evaluation]
            R4[graph]
            R5[agent-config]
            R6[ns-mas]
        end

        subgraph Services["Services"]
            ScenarioSvc[Scenario Service]
            ValidationSvc[Validation Service]
            NsMasPipeline[NS-MAS Pipeline]
        end

        subgraph Orchestration["LangGraph Orchestrierung"]
            GenVal["Generator ↔ Validator"]
            NSMASFlow["Planner → TTP Gen → Auditor → Review → Synthesizer"]
        end

        subgraph Agents["Agents"]
            Planner[Scenario Planner]
            TTPGen[TTP Generator]
            Auditor[KG Auditor]
            Synthesizer[Report Synthesizer]
        end
    end

    subgraph External["Externe Systeme"]
        LLM["LLM (OpenAI / Anthropic)"]
        Neo4j[(Neo4j Knowledge Graph)]
        RAG["RAG (BM25 + Re-Ranker)"]
    end

    User --> Browser
    Browser --> Frontend
    Frontend -->|HTTP, SSE| API
    API --> Routes
    Routes --> Services
    Services --> Orchestration
    Orchestration --> Agents
    Agents --> LLM
    Agents --> Neo4j
    TTPGen --> RAG
    RAG --> Neo4j
```

---

## Datenfluss – Zwei Haupt-Pipelines

### Pipeline A: Klassische Szenario-Generierung

```mermaid
sequenceDiagram
    participant F as Frontend
    participant API as FastAPI
    participant Svc as Scenario Service
    participant Graph as LangGraph
    participant Gen as Generator (LLM)
    participant Val as Validator (Neo4j)

    F->>API: POST /scenarios/generate
    API->>Svc: generate()
    Svc->>Graph: run()
    loop bis flag_achieved
        Graph->>Gen: generiere Angriffssequenz
        Gen->>Graph: Sequenz
        Graph->>Val: validiere gegen MITRE
        Val->>Neo4j: Cypher-Query
        Neo4j-->>Val: Pfad gültig?
        Val->>Graph: Ergebnis
    end
    Graph->>Svc: ScenarioResponse
    Svc->>API: Response
    API->>F: Szenario
```

### Pipeline B: NS-MAS-Pipeline

```mermaid
sequenceDiagram
    participant F as Frontend
    participant API as FastAPI
    participant Pipeline as NS-MAS Pipeline
    participant Planner as Scenario Planner
    participant TTP as TTP Generator
    participant Auditor as KG Auditor
    participant Review as Human Review
    participant Synth as Report Synthesizer

    F->>API: POST /ns-mas/run
    API->>Pipeline: run()
    Pipeline->>Planner: UserInput → AttackSketch
    Planner->>Pipeline: AttackSketch
    Pipeline->>TTP: RAG + LLM → TTPScenario
    TTP->>Pipeline: TTPScenario
    loop max. 3 Iterationen
        Pipeline->>Auditor: Neo4j-Validierung
        Auditor->>Pipeline: Feedback / OK
    end
    Pipeline->>Review: Interrupt (wartet auf Freigabe)
    F->>API: POST /ns-mas/resume
    API->>Pipeline: resume()
    Pipeline->>Synth: MSEL-Report
    Synth->>Pipeline: Report
    Pipeline->>API: Ergebnis
    API->>F: MSEL-Report
```

---

## Komponenten-Übersicht

| Schicht | Komponente | Technologie | Beschreibung |
|---------|------------|-------------|--------------|
| **Frontend** | React App | React, TypeScript, Vite | Dashboard, Szenario-Erstellung, Validierung, Evaluation, NS-MAS |
| **Backend** | FastAPI | FastAPI, Uvicorn | REST-API, CORS, Routen |
| **Orchestrierung** | LangGraph | LangGraph, LangChain | StateGraph, Checkpointer, Generator–Validator, NS-MAS-Flow |
| **Agents** | Planner, TTP Gen, Auditor, Synthesizer | Python | LLM-gesteuerte Agenten |
| **Knowledge Graph** | Neo4j | Neo4j, Cypher | MITRE ATT&CK (Tactic, Technique, PRECEDES) |
| **RAG** | Retriever | BM25, Re-Ranker | Technik-Retrieval für TTP Generator |
| **LLM** | OpenAI / Anthropic | gpt-4o-mini, Claude | Generierung, Planung, Synthese |

---

## API-Endpunkte

| Prefix | Methoden | Funktion |
|--------|----------|----------|
| `/scenarios` | POST /generate, /generate/stream, GET /, GET /{id} | Szenario-Generierung (sync/stream), Liste, Detail |
| `/validation` | POST / | Validierung gegen MITRE ATT&CK |
| `/evaluation` | POST /compare | Neuro vs. Baseline |
| `/graph` | GET /tactics, /techniques, POST /validate-path | Neo4j-Taktiken, Techniken, Pfadvalidierung |
| `/agent-config` | GET | Agent-Konfiguration |
| `/ns-mas` | POST /run, POST /resume | NS-MAS-Pipeline (inkl. Human Review) |
| `/health` | GET | Health-Check |

---

## Konfiguration

- **`config/settings.yaml`**: LLM, Neo4j, RAG, Pipeline-Parameter
- **`.env`**: API-Keys, Neo4j-Credentials (Pydantic Settings)

---

*Erstellt für die DORA Szenario-Plattform*
