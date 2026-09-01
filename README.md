# Nitivayu — Crowdsourced Societal Challenge Pipeline

**Problem Statement ID:** SIH26043 | **Theme:** Governance & Administration | **Team:** QuantumQuest

Nitivayu is a durable, multi-agent AI pipeline that converts messy, multilingual citizen grievances into structured, academically matched, funded, and milestone-tracked research challenges with enforceable Service Level Agreements (SLAs).

📖 **[Complete User Manual & Operations Guide (USER.md)](USER.md)** — Step-by-step operating instructions for Citizens, Nodal Officers, Universities, CSR Partners, and Admins.

## Architecture

```mermaid
graph TD
    subgraph Client Layer [Modern Scalable Web UI - React 18 + Vite + Tailwind]
        CitizenApp[Citizen Intake PWA & Live Tracker]
        OfficerQueue[Officer High-Density Triage Queue]
        UniPortal[University IIC & Milestone Workspace]
        CSRHub[CSR Discovery & Funding Portal]
        GovAnalytics[Scalable Public Governance Dashboard]
    end

    subgraph Gateway & API Layer
        FastAPI[FastAPI Async Backend :8000]
        Auth[JWT Auth + RBAC Guard]
        BatchCtrl[Batch Triage Trigger & Schedule Manager]
    end

    subgraph Durable Workflow Engine
        TemporalSvr[Temporal Dev Server / Engine :7233]
        TemporalUI[Temporal Web UI :8233]
    end

    subgraph Temporal Scheduled & Real-Time Workflows
        RealTimeWF[ChallengeTriageWorkflow - Real-Time Fast-Path]
        WeeklyBatchWF[WeeklyBatchTriageWorkflow - Cron: Every Mon 00:00]
        MonthlyMacroWF[MonthlyMacroTriageWorkflow - Cron: 1st of Month]
        SLAEscalationWF[UniversitySLAWorkflow - 7d Auto-Reroute]
    end

    subgraph Agent Worker Fleet [Scalable Temporal Python Workers]
        ExtractAgent[Intake Extraction Agent]
        ClassifyAgent[Taxonomy Classification Agent]
        DedupAgent[pgvector Semantic Dedup Agent]
        RouteAgent[Explainable University Routing Agent]
        ClusterAgent[Batch Cross-District Clustering Agent]
        FlywheelAgent[Monthly Prototype Re-Centering Agent]
        ReportGenAgent[Compliant Report & Export Generator]
    end

    subgraph AI & ML Subsystem
        OpenRouter[OpenRouter Free Tier Gateway - Gemini 2.0 / Llama 3.3]
        LocalMiniLM[sentence-transformers / paraphrase-multilingual-MiniLM-L12-v2]
        LLMCache[Deterministic Cache / Seed Fallback]
    end

    subgraph Data & Storage Layer
        PostgreSQL[(PostgreSQL 16 + pgvector :5432)]
        FileSystem[/output Directory - CSV, PDF, JSONL, XLSX/]
    end

    ClientLayer -->|REST / Form Data / SSE| FastAPI
    FastAPI --> Auth
    FastAPI --> BatchCtrl
    FastAPI -->|Start Realtime & Signal| TemporalSvr
    FastAPI -->|CRUD & Read Queries| PostgreSQL
    TemporalSvr --> RealTimeWF
    TemporalSvr --> WeeklyBatchWF
    TemporalSvr --> MonthlyMacroWF
    TemporalSvr --> SLAEscalationWF
    RealTimeWF --> AgentWorkerFleet
    WeeklyBatchWF --> AgentWorkerFleet
    MonthlyMacroWF --> AgentWorkerFleet
    SLAEscalationWF --> AgentWorkerFleet
    ExtractAgent --> OpenRouter
    ExtractAgent --> LLMCache
    ClassifyAgent --> LocalMiniLM
    ClassifyAgent --> OpenRouter
    DedupAgent --> LocalMiniLM
    DedupAgent --> PostgreSQL
    RouteAgent --> LocalMiniLM
    RouteAgent --> PostgreSQL
    ClusterAgent --> LocalMiniLM
    ClusterAgent --> PostgreSQL
    FlywheelAgent --> PostgreSQL
    ReportGenAgent --> FileSystem
    AgentWorkerFleet -->|State Updates & Vectors| PostgreSQL
    TemporalSvr --> TemporalUI
```

## Prerequisites
- **Docker** & **Docker Compose**
- **OpenRouter API Key** (for accessing free-tier LLMs)

## Quick Start (Windows)

For single-click management on Windows:

1. **One-Time Setup** (Run once on a new system):
   ```cmd
   installation.bat
   ```
   *Checks Docker prerequisites, configures `.env`, verifies output directories, and pre-builds all Docker images.*

2. **Start Platform**:
   ```cmd
   start.bat
   ```
   *Launches all services in the background and displays live links.*

3. **Stop Platform**:
   ```cmd
   stop.bat
   ```
   *Gracefully shuts down all containers while preserving database and workflow state.*

---

## Manual Setup Instructions

1. Clone the repository.
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Update the `.env` file with your `OPENROUTER_API_KEY`.
4. Run the multi-service composition:
   ```bash
   docker compose up --build
   ```

## Service URLs
- **Frontend (Web UI)**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000) (Swagger UI at `/docs`)
- **Temporal Web UI**: [http://localhost:8233](http://localhost:8233)

## Seed Data
The database is pre-seeded with:
- **6 Universities**: BIT Mesra, NIT Jamshedpur, IIT (ISM) Dhanbad, CUJ, Ranchi University, XLRI
- **15 Ground Truth Civic Challenges**: Realistic submissions representing problems in Jharkhand across water contamination, industrial pollution, coal mining dust, tribal handicrafts, and education.

## Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | React 18, Vite 5, Tailwind CSS, Lucide Icons, TanStack Virtual |
| **Backend API** | FastAPI (Python 3.12, AsyncIO, Pydantic v2) |
| **Workflow Engine** | Temporal.io (Dev Server container / Python SDK) |
| **Database & Vectors** | PostgreSQL 16 + `pgvector` extension |
| **LLM Inference** | OpenRouter Free-Tier (`google/gemini-2.0-flash-exp:free`) |
| **Local Embeddings** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **Containerization** | Docker Compose v2 |

## API Endpoints Summary
- `POST /api/v1/submissions` - Submit a new civic challenge
- `GET /api/v1/submissions/{id}` - Get submission status
- `GET /api/v1/challenges/queue` - Get triage queue for officers
- `POST /api/v1/challenges/{id}/approve` - Officer approval
- `GET /api/v1/reports/weekly` - Generate and fetch weekly report

---
*Built with ❤️ by Team QuantumQuest*
