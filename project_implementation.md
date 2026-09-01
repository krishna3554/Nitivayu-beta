# Nitivayu — Technical Implementation Blueprint & Architecture Specification
**Crowdsourced Societal Challenge & Civic Innovation Pipeline (Jharkhand)**  
**Problem Statement ID:** SIH26043 | **Theme:** Governance & Administration | **Team:** QuantumQuest  

---

## 1. Executive Summary & Core Architectural Philosophy

### 1.1 The Core Insight
> *"Helplines close tickets. We solve problems."*

Traditional grievance platforms (CPGRAMS, Jharkhand CM Helpline) function as transactional complaint registers that optimize for rapid ticket closure rather than systemic problem-solving. Meanwhile, Jharkhand’s **30+ higher education institutions** (including BIT Mesra, NIT Jamshedpur, IIT (ISM) Dhanbad, CUJ, Ranchi University, and XLRI) seek authentic real-world engineering and governance challenges under the **National Education Policy (NEP) 2020** experiential learning mandate, while over **₹1,475 Cr in CSR funds** remains disconnected from grassroots civic innovation.

**Nitivayu** bridges this gap through a durable, multi-agent AI pipeline that converts messy, multilingual citizen grievances into structured, academically matched, funded, and milestone-tracked research challenges with enforceable Service Level Agreements (SLAs).

```
┌─────────────────┐       ┌─────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│ Citizen Intake  │       │  Temporal Core  │       │  Multi-Agent Engine  │       │ Action & Outcomes    │
│ (Hindi/Hinglish/├──────►│ (Durable State, ├──────►│ (Extract, Classify,  ├──────►│ Officer Gate, Uni    │
│  English + Geo) │       │  Timers, Retry) │       │  Dedup, Route, Alert)│       │ Assignment, CSR Link │
└─────────────────┘       └─────────────────┘       └──────────────────────┘       └──────────────────────┘
```

### 1.2 "Control in Code, Judgement in AI, Accountability in Humans"
* **Deterministic Control Flow:** Orchestrated exclusively by **Temporal.io** durable workflows (state persistence, auto-escalation timers, human-in-the-loop approval signals, scheduled batch cycles, exponential backoff retries).
* **Stochastic Judgement:** Confined within atomic Temporal Activity tasks powered by **OpenRouter Free-Tier LLMs** (with prompt engineering, strict JSON schema output, and deterministic local fallback caching) combined with **Local Multilingual MiniLM Embeddings** on CPU.
* **Human Governance:** Government nodal officers hold the ultimate approval and re-routing authority at verification gates with auto-escalating SLA countdowns.

---

## 2. System Architecture & Topology

Nitivayu is architected as a modular, containerized system orchestrated with Docker Compose, providing clean isolation between web intake, API routing, temporal coordination, worker execution, and vector-relational storage.

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

---

## 3. Technology Stack Justification & Trade-Off Matrix

| Layer | Technology | Key Justification | Hackathon & Production Trade-Off |
| :--- | :--- | :--- | :--- |
| **Frontend** | React 18, Vite 5, Tailwind CSS, Lucide Icons, TanStack Virtual | Sub-second cold start, clean high-density layout, virtualized rendering for 10,000+ submissions without lag. | Single-page application without unnecessary SSR complexity; responsive from 320px mobile to 4K dashboard displays. |
| **Backend API** | FastAPI (Python 3.12, AsyncIO, Pydantic v2, asyncpg) | High-performance asynchronous non-blocking I/O, native schema validation, auto-generated OpenAPI documentation. | Shares identical data models and Python runtime with Temporal agent workers. |
| **Workflow Engine** | Temporal.io (Dev Server container / Python SDK) | Built-in durable state machine, cron scheduling, non-blocking sleep timers up to 30 days, human signal handling, zero data loss. | Exceptional demo asset (Temporal Web UI visually renders executing activities live to hackathon judges). |
| **Database & Vectors** | PostgreSQL 16 + `pgvector` extension | Single unified engine for ACID relational transactions and high-speed cosine vector similarity searches. | Eliminates the operational overhead and synchronization lag of managing a separate vector database like Pinecone/Milvus. |
| **LLM Inference** | OpenRouter Free-Tier Gateway (`openrouter/free` models) | Zero marginal cost; access to state-of-the-art open models (e.g. `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-72b-instruct:free`). | Wrapped with exponential backoff retries, strict JSON schemas, and an offline local caching layer (`LLM_CACHE=1`) for demo resilience. |
| **Local Embeddings** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Lightweight (120 MB), runs locally on CPU in ~45ms, excellent native comprehension of Hindi, Hinglish, and English. | 384-dimensional vector embeddings stored directly in pgvector with zero external API calls or latency spikes. |
| **Containerization** | Docker Compose v2 | Single-command deployment (`docker compose up --build`), reproducible execution across laptops, staging VMs, or cloud instances. | Compose-only architecture avoiding over-engineered Kubernetes setups while supporting horizontal worker scaling (`--scale worker=3`). |

---

## 4. AI Triage Engine: Real-Time vs Scheduled Weekly/Monthly Cadence

Civic grievances exhibit two distinct operational characteristics:
1. **Urgent individual submissions** that require rapid initial structuring and immediate triage confirmation.
2. **Systemic, cross-district societal challenges** that require scheduled periodic batch aggregation, time-windowed vector clustering, dynamic university capacity re-balancing, and administrative governance reporting.

Nitivayu provides a unified **Dual-Cadence Triage Architecture**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                DUAL-CADENCE AI TRIAGE ARCHITECTURE                      │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│      1. REAL-TIME FAST-PATH TRIAGE       │        2. SCHEDULED BATCH TRIAGE (TEMPORAL) │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ • Latency: < 10 seconds                  │ • Cadence: Configurable (Weekly / Monthly)  │
│ • Scope: Single submission               │ • Scope: All unprocessed/accumulated intake │
│ • Steps: Extract -> Classify -> Local    │ • Steps: Global Dedup -> Macro Clustering   │
│   Vector Match -> Instant Candidate List │   -> Capacity Balancing -> Official Reports │
│ • Trigger: Citizen Form Submission       │ • Trigger: Temporal Cron Schedule / Admin UI│
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

### 4.1 Real-Time Fast-Path Triage
* **Trigger:** Citizen submits a complaint via web/mobile.
* **Execution:** Invoked immediately by `ChallengeTriageWorkflow(submission_id)`.
* **Processing:**
  1. **Intake Extraction Agent:** Strips PII (phone/Aadhaar/name), calls OpenRouter Free-Tier LLM (`google/gemini-2.0-flash-exp:free` or cached fallback) with strict JSON schema to generate `title`, `summary`, `category`, `severity` (1-5), and `location_hint`.
  2. **Taxonomy Classification Agent:** Generates 384-d MiniLM embedding of the summary and computes cosine similarity against the 10 theme prototypes.
  3. **Fast Deduplication:** Queries pgvector for cosine similarity $> 0.85$ within the same district.
  4. **Initial Candidate Routing:** Computes initial university scores and queues the submission for officer validation.

---

### 4.2 Scheduled Weekly Batch AI Triage Run (`WeeklyBatchTriageWorkflow`)
* **Schedule:** Automated Temporal Cron (e.g. `0 0 * * MON` — every Monday at 00:00 UTC) or triggered on-demand via the Admin Dashboard.
* **Workflow Definition:**

```python
@workflow.defn
class WeeklyBatchTriageWorkflow:
    """
    Weekly Cron Workflow: Aggregates all submissions from the past 7 days,
    executes global deduplication, re-balances university capacity loads,
    and publishes the official weekly AI Triage CSV and PDF Routing Report.
    """
    @workflow.run
    async def run(self, batch_params: dict) -> dict:
        batch_id = f"BATCH-{workflow.now().strftime('%Y%m%d-%H%M%S')}"
        
        # 1. Fetch all unprocessed/unrouted submissions in the time window
        submissions = await workflow.execute_activity(
            fetch_pending_batch_submissions_activity,
            batch_params,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # 2. Batch AI Extraction & Embedding Generation
        extracted_batch = await workflow.execute_activity(
            batch_extract_and_embed_activity,
            submissions,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # 3. Cross-District Semantic Deduplication & Cluster Merging
        clustered_data = await workflow.execute_activity(
            cluster_and_deduplicate_batch_activity,
            extracted_batch,
            start_to_close_timeout=timedelta(minutes=10)
        )

        # 4. Global University Scoring & Dynamic Capacity Load Balancing
        routing_results = await workflow.execute_activity(
            global_university_routing_activity,
            clustered_data,
            start_to_close_timeout=timedelta(minutes=10)
        )

        # 5. Generate Standard Output Files (IO Spec Compliant)
        triage_csv_path = await workflow.execute_activity(
            generate_triage_csv_report_activity,
            routing_results,
            start_to_close_timeout=timedelta(minutes=5)
        )

        weekly_pdf_path = await workflow.execute_activity(
            generate_weekly_routing_pdf_report_activity,
            routing_results,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # 6. Notify Nodal Officers with Weekly Digest
        await workflow.execute_activity(
            notify_officers_weekly_digest_activity,
            {"batch_id": batch_id, "csv": triage_csv_path, "pdf": weekly_pdf_path},
            start_to_close_timeout=timedelta(minutes=2)
        )

        return {
            "batch_id": batch_id,
            "processed_count": len(submissions),
            "csv_report": triage_csv_path,
            "pdf_report": weekly_pdf_path,
            "status": "COMPLETED"
        }
```

#### Key Responsibilities of the Weekly Batch Triage:
1. **Cross-District Semantic Cluster Discovery:** Identifies macro-patterns that span multiple villages or districts (e.g. 14 separate village complaints about fluoride contamination across Garhwa and Palamu districts are grouped into a single **Macro-Challenge**).
2. **Dynamic University Capacity Equalization:** Prevents over-allocation to single departments by factoring in current student/faculty workload across BIT Mesra, NIT Jamshedpur, IIT (ISM) Dhanbad, CUJ, Ranchi University, and XLRI.
3. **Automated IO Spec Output File Generation:**
   * Generates `/output/triage/Nitivayu_triage_<YYYYMMDD>_<HHMMSS>.csv` containing the full batch triage snapshot.
   * Generates `/output/reports/Nitivayu_routing_report_<YYYYMMDD>.pdf` containing the weekly executive summary, university leaderboard, and SLA compliance metrics.

---

### 4.3 Scheduled Monthly Macro Triage & Prototype Refresh Run (`MonthlyMacroTriageWorkflow`)
* **Schedule:** Automated Temporal Cron (`0 0 1 * *` — 1st of every month).
* **Purpose:** Implements the **Continuous Learning Flywheel** and macroeconomic alignment:

```mermaid
graph LR
    subgraph Officer Actions
        Review[Officer Validations & Overrides]
    end

    subgraph Monthly Flywheel
        AuditDB[(Audit Logs & Corrections)]
        EvalEngine[Accuracy & Confusion Matrix Evaluator]
        CentroidUpdate[Theme Centroid Vector Re-Calculation]
        SeasonalAdjust[Seasonal Weight Adjustment Engine]
        CSRMatcher[CSR Industry Funding Match Engine]
    end

    subgraph Deliverables
        NewPrototypes[Refreshed 10 Theme Embeddings]
        CSRExcel[/output/csr/Nitivayu_csr_matches_*.xlsx]
    end

    Review --> AuditDB
    AuditDB --> EvalEngine
    EvalEngine --> CentroidUpdate
    CentroidUpdate --> NewPrototypes
    AuditDB --> SeasonalAdjust
    SeasonalAdjust --> CSRMatcher
    CSRMatcher --> CSRExcel
```

1. **Active Feedback Loop (Data Flywheel):**
   * Inspects every manual override made by government nodal officers over the previous 30 days.
   * Recomputes centroid embeddings for each of the **10 Jharkhand Theme Prototypes** using validated real-world civic statements.
   * Enables continuous self-improvement without fine-tuning expensive deep learning models.
2. **Seasonal Trend Weight Balancing:**
   * Adjusts priority coefficients based on seasonal governance shifts (e.g., boosting waterborne disease & drainage weights during monsoon months July–September; boosting forest fire & groundwater scarcity weights during April–June).
3. **CSR Match & Funding Matrix Export:**
   * Matches all validated, university-accepted research challenges against the registered corporate CSR focus areas (e.g. Tata Steel CSR, CCL, BCCL, Vedanta, Adani Foundation).
   * Generates the monthly Excel export `/output/csr/Nitivayu_csr_matches_<YYYYMMDD>_<HHMMSS>.xlsx`.

---

### 4.4 Admin Cadence Control & On-Demand Manual Trigger

The system provides flexible cadence controls in the Admin Panel:
* **Schedule Modes:** `Continuous Real-Time` | `Daily at 00:00 UTC` | `Weekly on Mondays` | `Monthly on 1st`
* **On-Demand "Run Batch Triage Now" Button:** Allows administrators to trigger an immediate batch run with live progress streaming via Server-Sent Events (SSE).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ADMIN CADENCE & BATCH CONTROL                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│  Current Active Schedule: [ Weekly (Every Monday 00:00 UTC) ▼ ]              │
│  Last Batch Run: 2026-08-31 00:00:14 UTC (142 submissions processed)         │
│  Next Scheduled Run: In 5 days, 14 hours                                     │
│  Unprocessed Submissions in Queue: 28 items                                  │
│                                                                              │
│  [ ▶ Run Batch Triage Now ]     [ ⚙ Configure Cron ]     [ 📥 Download Logs ] │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Explainable AI Triage & Routing Mathematical Formulation

To ensure transparency and eliminate "black-box" decisions for government officers, university routing uses a multi-factor mathematical scoring model:

$$\text{Total Match Score} = w_s \cdot S_{\text{semantic}} + w_t \cdot S_{\text{theme}} + w_c \cdot S_{\text{capacity}} + w_g \cdot S_{\text{geo}}$$

Where weights are calibrated to:
* $w_s = 0.60$ (Semantic embedding similarity)
* $w_t = 0.20$ (Categorical department specialization match)
* $w_c = 0.10$ (Institutional capacity & current load)
* $w_g = 0.10$ (Geographic proximity to the problem site)

### Component Formulations:
1. **Semantic Similarity ($S_{\text{semantic}}$):**
   $$S_{\text{semantic}} = \frac{\vec{E}_{\text{problem}} \cdot \vec{E}_{\text{uni}}}{\|\vec{E}_{\text{problem}}\| \|\vec{E}_{\text{uni}}\|}$$
   Computed locally in ~45ms using 384-dimensional multilingual embeddings.

2. **Theme Specialization Match ($S_{\text{theme}}$):**
   $$S_{\text{theme}} = \begin{cases} 1.0 & \text{if primary department directly matches category} \\ 0.5 & \text{if secondary department matches} \\ 0.1 & \text{general engineering/management capacity} \end{cases}$$

3. **Capacity Availability ($S_{\text{capacity}}$):**
   $$S_{\text{capacity}} = 1.0 - \left(\frac{\text{Current Active Projects}}{\text{Maximum Cap}}\right)$$
   Prevents any single institution from being overloaded.

4. **Geographic Proximity ($S_{\text{geo}}$):**
   $$S_{\text{geo}} = \frac{1}{1 + 0.008 \cdot d_{\text{km}}}$$
   Where $d_{\text{km}}$ is the Haversine distance between problem coordinates and university campus.

---

## 6. Database Schema Design (PostgreSQL 16 + pgvector)

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Citizens Table
CREATE TABLE citizens (
    citizen_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_encrypted BYTEA NOT NULL,
    email_encrypted BYTEA,
    language_pref VARCHAR(10) DEFAULT 'hi', -- 'hi', 'en', 'hi-Latn'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Submissions Table (Raw intake)
CREATE TABLE submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    citizen_id UUID REFERENCES citizens(citizen_id) ON DELETE SET NULL,
    raw_text TEXT NOT NULL,
    photo_url VARCHAR(512),
    geo_lat DECIMAL(9, 6),
    geo_lng DECIMAL(9, 6),
    geo_district VARCHAR(100),
    geo_block VARCHAR(100),
    batch_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'INGESTED', -- INGESTED, TRIAGING, OFFICER_REVIEW, ROUTED, REJECTED, MERGED, COMPLETED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Problems Table (Structured, triaged challenges)
CREATE TABLE problems (
    problem_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID UNIQUE REFERENCES submissions(submission_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    category VARCHAR(100) NOT NULL, -- Water, Environment, Infrastructure, Health, Education, Livelihood, Energy, Agriculture, Sanitation, Governance
    severity_score INTEGER CHECK (severity_score BETWEEN 1 AND 5),
    confidence_score DECIMAL(4, 3),
    summary_embedding vector(384),
    assigned_officer_id UUID,
    temporal_workflow_id VARCHAR(255),
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_id UUID REFERENCES problems(problem_id),
    cluster_group_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'PENDING_OFFICER_REVIEW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Universities Table (Jharkhand Academic Network)
CREATE TABLE universities (
    university_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    short_code VARCHAR(50) UNIQUE NOT NULL, -- BIT_MESRA, NIT_JSR, IIT_ISM, CUJ, RANCHI_UNIV, XLRI
    iic_code VARCHAR(100),
    district VARCHAR(100) NOT NULL,
    geo_lat DECIMAL(9, 6) NOT NULL,
    geo_lng DECIMAL(9, 6) NOT NULL,
    domain_specializations TEXT[] NOT NULL,
    active_capacity INTEGER DEFAULT 10,
    current_load INTEGER DEFAULT 0,
    capability_embedding vector(384),
    nodal_contact_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Route Assignments Table
CREATE TABLE route_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    university_id UUID REFERENCES universities(university_id) ON DELETE CASCADE,
    rank_order INTEGER NOT NULL, -- 1, 2, 3
    match_score DECIMAL(5, 4) NOT NULL,
    score_breakdown JSONB NOT NULL, -- {semantic: 0.91, theme: 1.0, capacity: 0.8, geo: 0.95}
    sla_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'OFFERED', -- OFFERED, ACCEPTED, DECLINED, EXPIRED, AUTO_REROUTED
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP WITH TIME ZONE
);

-- 6. Project Teams & Milestones
CREATE TABLE project_teams (
    team_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID REFERENCES route_assignments(assignment_id) ON DELETE CASCADE,
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    university_id UUID REFERENCES universities(university_id) ON DELETE CASCADE,
    faculty_mentor_name VARCHAR(255) NOT NULL,
    student_lead_name VARCHAR(255) NOT NULL,
    team_members JSONB,
    proposal_title VARCHAR(255),
    proposal_document_url VARCHAR(512),
    status VARCHAR(50) DEFAULT 'TEAM_FORMED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE milestones (
    milestone_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID REFERENCES project_teams(team_id) ON DELETE CASCADE,
    milestone_num INTEGER CHECK (milestone_num IN (1, 2, 3)),
    title VARCHAR(255) NOT NULL, -- M1: Feasibility, M2: Prototype, M3: Field Validation
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, SUBMITTED, VERIFIED, DELAYED
    evidence_url VARCHAR(512),
    verified_by UUID,
    verified_at TIMESTAMP WITH TIME ZONE
);

-- 7. Industries & CSR Links
CREATE TABLE industries (
    industry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100) NOT NULL, -- Mining, Steel, Energy, IT, Healthcare
    csr_focus_areas TEXT[] NOT NULL,
    csr_budget_inr DECIMAL(15, 2),
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE funding_links (
    link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    team_id UUID REFERENCES project_teams(team_id) ON DELETE SET NULL,
    industry_id UUID REFERENCES industries(industry_id) ON DELETE CASCADE,
    pledged_amount_inr DECIMAL(15, 2),
    status VARCHAR(50) DEFAULT 'PLEDGED', -- PLEDGED, DISBURSED, COMPLETED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Officers & Admins Table
CREATE TABLE officers (
    officer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    department VARCHAR(150) NOT NULL,
    district VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL, -- district_officer, senior_officer, state_admin
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Immutable System Audit Logs Table
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    actor_id VARCHAR(255) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    before_snapshot JSONB,
    after_snapshot JSONB,
    ip_address VARCHAR(50),
    request_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- High-Performance ANN Vector Indexing & Query Acceleration
CREATE INDEX idx_problems_vector ON problems USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_universities_vector ON universities USING ivfflat (capability_embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX idx_problems_status ON problems(status);
CREATE INDEX idx_submissions_district ON submissions(geo_district);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
```

---

## 7. Clean, High-Density & Scalable UI Design System

The user interface is engineered for clarity, speed, and massive scale. It balances low-bandwidth responsiveness for rural citizens with high data density and instant telemetry for government administrators.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  NITIVAYU | Civic Innovation Pipeline                                  Jharkhand Admin Portal  [🔔 3] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  [📊 Governance Overview]   [📋 Officer Triage Queue (14)]   [🎓 University Workspace]   [⚙ System Scale]│
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  LIVE PIPELINE TELEMETRY                                                                               │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐ │
│  │ Intake Volume        │ │ Triage Throughput    │ │ SLA Compliance       │ │ Active Temporal Fleet  │ │
│  │ 1,420 Submissions    │ │ 120 RPS | 6.8s Avg   │ │ 98.4% On-Time        │ │ 3 Workers (0 Queue Lag)│ │
│  │ ↑ +14% this week     │ │ (OpenRouter + MiniLM)│ │ 0 Breaches Escalated │ │ Dev Server Healthy     │ │
│  └──────────────────────┘ └──────────────────────┘ └──────────────────────┘ └────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  OFFICER TRIAGE QUEUE — VIRTUALIZED TABLE (Showing 1–10 of 142 Active Challenges)                      │
│  [ Search by District, Keyword, or ID... ]  [ Filter: Category ▼ ]  [ Status: Pending Review ▼ ]       │
│                                                                                                        │
│  ID       Title & Summary                     District    Severity  Top Match (Score)   SLA Timer  Action  │
│  ────────────────────────────────────────────────────────────────────────────────────────────────────  │
│  #JH-8831 Fluoride in Handpumps (4 villages)  Garhwa      🔴 5/5    BIT Mesra (0.912)   ⏳ 68h 12m  [Approve]│
│  #JH-8830 Subarnarekha Chemical Effluent      Adityapur   🔴 5/5    NIT Jsr (0.894)     ⏳ 71h 45m  [Approve]│
│  #JH-8829 Coal Dust Pollution Katras          Dhanbad     🟡 4/5    IIT-ISM (0.878)     ⏳ 45h 00m  [Approve]│
│  #JH-8828 Dokra Artisan Supply Middlemen      Khunti      🟢 3/5    XLRI Jsr (0.865)    ⏳ 70h 20m  [Approve]│
│  #JH-8827 Torpa Tribal School Roof Leak       Khunti      🟡 4/5    CUJ Ranchi (0.842)  ⏳ 52h 10m  [Approve]│
│                                                                                                        │
│  [ ⚡ Bulk Approve (Selected: 0) ]     [ 🔄 Run Batch Triage Now ]     [ 📑 Export Weekly Report (PDF) ]│
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Design Tokens & Aesthetic Standards
* **Typography:** Clean, sans-serif variable typeface (`Inter` / `Plus Jakarta Sans`) with clear visual hierarchy and tabular numeric alignments.
* **Palette:**
  * **Neutral Base:** Slate-50 background, Zinc-900 high-contrast text.
  * **Status Accents:**
    * Success / Active: Emerald-600 (`#059669`)
    * Warning / Pending SLA: Amber-500 (`#F59E0B`)
    * Critical Severity / Breach: Rose-600 (`#E11D48`)
    * Academic / University: Indigo-600 (`#4F46E5`)
    * Corporate CSR: Sky-600 (`#0284C7`)
* **Micro-Interactions & Speed:**
  * Keyboard navigation for nodal officers (`j`/`k` to traverse rows, `a` to approve, `r` to reject, `x` to select for bulk action).
  * Optimistic UI updates with instant rollback on network error.

### 7.2 Scalability Features on the UI
1. **Virtualized List Rendering (`@tanstack/react-virtual`):**
   * Smoothly handles and scrolls through **10,000+ submission cards** with sub-60fps rendering performance.
2. **Real-Time Scalability & Health Dashboard:**
   * Live gauge of worker pool size, OpenRouter API token consumption, CPU inference latency (MiniLM ~45ms), and database query latency (pgvector ANN <15ms).
3. **Low-Bandwidth Mobile Citizen Intake:**
   * Compressed payload footprint (<40 KB initial bundle).
   * Offline form caching via Service Worker with auto-sync when network returns.
   * Auto-detected GPS coordinates with graceful fallback to interactive district/block selector.

---

## 8. System Output File Specifications (IO Compliance)

The system strictly complies with the **Output File Specification** by automating file generation and rolling logs in `/output/`:

### 8.1 Specification Summary Table

| Output File Type | File Pattern | Format & Encoding | Frequency & Mode | Consumers |
| :--- | :--- | :--- | :--- | :--- |
| **AI Triage Report** | `/output/triage/Nitivayu_triage_<YYYYMMDD>_<HHMMSS>.csv` | CSV (UTF-8 with BOM) | Per Batch Run / Write | Nodal Officers, Admins |
| **SLA & Escalation Log** | `/output/sla/Nitivayu_sla_log_<YYYYMMDD>.csv` | CSV (UTF-8) | Daily / Append-only | Compliance Auditors |
| **University Routing Report** | `/output/reports/Nitivayu_routing_report_<YYYYMMDD>.pdf` | PDF (Binary) | Weekly / Write | Dept of Higher Education |
| **System Audit Log** | `/output/audit/Nitivayu_audit_<YYYYMMDD>.jsonl` | JSONL (UTF-8) | Daily / Append-only | Security, Immutability |
| **CSR Funding Matches** | `/output/csr/Nitivayu_csr_matches_<YYYYMMDD>_<HHMMSS>.xlsx` | XLSX (Office Open XML)| Monthly/On-Demand / Write | Industry / CSR Partners |

### 8.2 Exact Schemas & Format Samples

```csv
# 1. AI Triage Report (CSV Header & Sample Row)
submission_id,citizen_id,timestamp_submitted,raw_text_preview,category,severity,geo_district,dedup_flag,dup_of_id,uni_match_1,score_1,uni_match_2,score_2,uni_match_3,score_3,triage_status
sub-001,cit-042,2026-08-30T09:15:00Z,"Hamare gaon mein paani...",Water,5,Garhwa,false,,BIT Mesra,0.912,NIT Jamshedpur,0.874,CUJ Ranchi,0.792,routed

# 2. SLA & Escalation Log (CSV Header & Sample Row)
event_id,problem_id,assignment_id,event_type,actor_id,actor_role,event_ts,sla_deadline,days_remaining,escalation_level,notes
evt-901,prob-102,asgn-055,sla_warning,system,temporal_sla_worker,2026-08-31T12:00:00Z,2026-09-02T12:00:00Z,2.0,level_1,48h remaining for university acceptance

# 3. System Audit Log (JSONL Record)
{"log_id":"log-00127","ts":"2026-08-30T14:15:32.841Z","entity_type":"route_assignment","entity_id":"asgn-0055","action":"officer_approved","actor_id":"off-007","actor_role":"officer","before_snapshot":{"status":"pending_review"},"after_snapshot":{"status":"approved","approved_at":"2026-08-30T14:15:32Z"},"ip_address":"10.0.1.45","request_id":"req-abc123"}

# 4. CSR Matches Export (XLSX Column Schema)
problem_id,problem_summary,category,severity,university_assigned,industry_partner,sector,csr_budget_inr,match_score,contact_email,status,sla_deadline
```

---

## 9. Docker Compose Multi-Container Deployment

```yaml
version: '3.8'

services:
  # 1. PostgreSQL 16 with pgvector
  postgres:
    image: pgvector/pgvector:pg16
    container_name: nitivayu-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: nitivayu_db
      POSTGRES_USER: nitivayu_user
      POSTGRES_PASSWORD: nitivayu_secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/scripts/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nitivayu_user -d nitivayu_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  # 2. Temporal Dev Server & UI
  temporal:
    image: temporalio/dev-server:1.1.1
    container_name: nitivayu-temporal
    restart: unless-stopped
    command: ["--ip", "0.0.0.0", "--port", "7233", "--ui-port", "8233", "--db-filename", "/tmp/temporal.db"]
    ports:
      - "7233:7233"   # Temporal gRPC
      - "8233:8233"   # Temporal Web UI
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "7233"]
      interval: 5s
      timeout: 5s
      retries: 10

  # 3. FastAPI Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: nitivayu-backend
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      temporal:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://nitivayu_user:nitivayu_secure_password@postgres:5432/nitivayu_db
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
      - OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
      - LLM_CACHE=1
      - JWT_SECRET=nitivayu_super_secret_jwt_key_2026
    ports:
      - "8000:8000"
    volumes:
      - output_data:/app/output
      - ./backend:/app
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 4. Scalable Temporal Python Worker Fleet
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    container_name: nitivayu-worker
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
      temporal:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://nitivayu_user:nitivayu_secure_password@postgres:5432/nitivayu_db
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
      - OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
      - LLM_CACHE=1
      - SENTENCE_TRANSFORMERS_HOME=/root/.cache/torch/sentence_transformers
    volumes:
      - output_data:/app/output
      - model_cache:/root/.cache/torch/sentence_transformers

  # 5. React + Vite Frontend (Nginx)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: nitivayu-frontend
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "3000:80"

volumes:
  postgres_data:
  output_data:
  model_cache:
```

---

## 10. Comprehensive Seed Dataset: Jharkhand Universities & Ground Truth Challenges

### 10.1 Seed Universities

```json
[
  {
    "name": "Birla Institute of Technology (BIT), Mesra",
    "short_code": "BIT_MESRA",
    "iic_code": "IIC-JH-BIT-01",
    "district": "Ranchi",
    "geo_lat": 23.4123,
    "geo_lng": 85.4399,
    "domain_specializations": ["Water Purification", "Remote Sensing & GIS", "Solid Waste Management", "Renewable Energy", "Environmental Engineering"],
    "active_capacity": 15,
    "nodal_contact_email": "iic.head@bitmesra.ac.in"
  },
  {
    "name": "National Institute of Technology (NIT), Jamshedpur",
    "short_code": "NIT_JSR",
    "iic_code": "IIC-JH-NIT-02",
    "district": "East Singhbhum",
    "geo_lat": 22.7766,
    "geo_lng": 86.1444,
    "domain_specializations": ["Industrial Effluent Treatment", "Metallurgical Innovation", "Civil Infrastructure", "IoT Sensor Networks"],
    "active_capacity": 12,
    "nodal_contact_email": "iic.coord@nitjsr.ac.in"
  },
  {
    "name": "Indian Institute of Technology (IIT-ISM), Dhanbad",
    "short_code": "IIT_ISM",
    "iic_code": "IIC-JH-ISM-03",
    "district": "Dhanbad",
    "geo_lat": 23.8143,
    "geo_lng": 86.4412,
    "domain_specializations": ["Mine Dust Suppression", "Heavy Metal Soil Remediation", "Clean Coal Technology", "Geotechnical Engineering"],
    "active_capacity": 15,
    "nodal_contact_email": "dean.rnd@iitism.ac.in"
  },
  {
    "name": "Central University of Jharkhand (CUJ)",
    "short_code": "CUJ_RANCHI",
    "iic_code": "IIC-JH-CUJ-04",
    "district": "Ranchi (Brambe)",
    "geo_lat": 23.3644,
    "geo_lng": 85.1581,
    "domain_specializations": ["Tribal Livelihoods", "Solar Microgrids", "Indigenous Forest Produce Processing", "Rural Healthcare Tech"],
    "active_capacity": 10,
    "nodal_contact_email": "iic@cuj.ac.in"
  },
  {
    "name": "Ranchi University",
    "short_code": "RANCHI_UNIV",
    "iic_code": "IIC-JH-RU-05",
    "district": "Ranchi",
    "geo_lat": 23.3700,
    "geo_lng": 85.3250,
    "domain_specializations": ["Community Health Monitoring", "Primary Education Technologies", "Botanical Herb Formulations", "Groundwater Surveying"],
    "active_capacity": 8,
    "nodal_contact_email": "research@ranchiuniversity.ac.in"
  },
  {
    "name": "XLRI Xavier School of Management",
    "short_code": "XLRI_JSR",
    "iic_code": "IIC-JH-XLRI-06",
    "district": "East Singhbhum",
    "geo_lat": 22.8028,
    "geo_lng": 86.1854,
    "domain_specializations": ["Dokra Artisan Supply Chains", "Rural Self-Help Group Economics", "CSR Policy Evaluation", "Public Administration Logistics"],
    "active_capacity": 10,
    "nodal_contact_email": "social.innovation@xlri.ac.in"
  }
]
```

### 10.2 Ground Truth Civic Challenges (Jharkhand-Realistic)

1. **Water Contamination:** `"Garhwa block ke handpump mein fluoride aur peela rang aa raha hai, baccho ke daant kharab ho rahe hain."` $\rightarrow$ **Target:** BIT Mesra (Score: 0.912)
2. **Industrial Pollution:** `"Adityapur industrial area toxic effluent is being discharged into Subarnarekha River."` $\rightarrow$ **Target:** NIT Jamshedpur (Score: 0.894)
3. **Coal Mining Dust:** `"झरिया कोयला ढुलाई से भारी धूल प्रदूषण और बच्चों में अस्थमा बढ़ रहा है।"` $\rightarrow$ **Target:** IIT (ISM) Dhanbad (Score: 0.878)
4. **Tribal Handicrafts:** `"Khunti Dokra and Lac artisans getting exploited by middlemen, need direct catalog linkage."` $\rightarrow$ **Target:** XLRI Jamshedpur (Score: 0.865)
5. **Tribal Education:** `"तोरपा आवासीय विद्यालय में बरसात की वजह से छत टपक रही है और बिजली बैकअप नहीं है।"` $\rightarrow$ **Target:** CUJ Ranchi (Score: 0.842)

---

## 11. API Specification & Interface Contracts

```yaml
# 1. Citizen Problem Submission
POST /api/v1/submissions
Content-Type: multipart/form-data
Body:
  - raw_text: string
  - photo: file (optional)
  - geo_lat: float
  - geo_lng: float
  - language_pref: string ("hi" | "en" | "hi-Latn")
Response 202:
  {
    "submission_id": "8f3b20c1-3d9a-412e-967c-1793a38f3810",
    "tracking_token": "NITIVAYU-2026-JH-8831",
    "status": "INGESTED"
  }

# 2. Trigger Batch Triage On-Demand
POST /api/v1/admin/triage/trigger-batch
Header: Authorization: Bearer <JWT_TOKEN>
Body:
  {
    "cadence_type": "WEEKLY_MANUAL",
    "include_unassigned_only": true
  }
Response 202:
  {
    "batch_workflow_id": "BATCH-20260901-094500",
    "status": "STARTED",
    "stream_url": "/api/v1/admin/triage/batch-jobs/BATCH-20260901-094500/stream"
  }

# 3. Get & Update Cadence Schedules
GET /api/v1/admin/triage/schedules
Response 200:
  {
    "active_cadence": "WEEKLY",
    "cron_expression": "0 0 * * MON",
    "next_run_utc": "2026-09-07T00:00:00Z",
    "monthly_macro_cron": "0 0 1 * *",
    "monthly_next_run_utc": "2026-10-01T00:00:00Z"
  }

# 4. Officer Review Decision
POST /api/v1/officer/reviews/{problem_id}/decision
Header: Authorization: Bearer <JWT_TOKEN>
Body:
  {
    "decision": "APPROVE",
    "override_university_id": null,
    "comments": "Verified with district PHED."
  }
Response 200:
  {
    "problem_id": "...",
    "workflow_signal": "RECEIVED",
    "new_status": "ROUTED_TO_UNIVERSITY"
  }

# 5. Live Scalability & Telemetry Metrics
GET /api/v1/admin/telemetry/scale
Response 200:
  {
    "temporal_workers_active": 3,
    "queue_lag_seconds": 0.04,
    "system_rps": 124,
    "minilm_cpu_latency_ms": 42.1,
    "openrouter_token_consumption_rpm": 4200,
    "llm_cache_hit_rate_pct": 91.5
  }
```

---

## 12. Complete Directory Structure

```
Nitivayu/
├── docker-compose.yml              # Multi-service composition (pgvector, temporal, backend, worker, frontend)
├── .env.example                    # Environment template (OpenRouter keys, DB URL)
├── README.md                       # Quickstart instructions
├── project_implementation.md       # Master technical specification (this document)
│
├── backend/
│   ├── Dockerfile                  # FastAPI container image
│   ├── Dockerfile.worker           # Temporal Python worker container image
│   ├── requirements.txt            # FastAPI, temporalio, sentence-transformers, asyncpg, reportlab, openpyxl
│   ├── app/
│   │   ├── main.py                 # App entry point & CORS
│   │   ├── config.py               # App configuration & OpenRouter settings
│   │   ├── api/
│   │   │   ├── deps.py             # JWT auth & DB injection
│   │   │   └── routes/
│   │   │       ├── submissions.py  # Citizen submission & tracking
│   │   │       ├── officer.py      # Officer review queue & signals
│   │   │       ├── university.py   # University acceptance & milestones
│   │   │       ├── industry.py     # CSR funding & pledges
│   │   │       ├── batch_triage.py # Batch trigger & cron schedule endpoints
│   │   │       └── analytics.py    # Public stats & report downloads
│   │   ├── workflows/
│   │   │   ├── triage_workflow.py  # ChallengeTriageWorkflow (Real-time fast-path)
│   │   │   ├── weekly_batch.py     # WeeklyBatchTriageWorkflow (Cron)
│   │   │   ├── monthly_macro.py    # MonthlyMacroTriageWorkflow (Flywheel & CSR)
│   │   │   └── sla_workflow.py     # UniversitySLAWorkflow (7d auto-reroute)
│   │   ├── activities/
│   │   │   ├── extract.py          # OpenRouter LLM extraction (JSON schema)
│   │   │   ├── classify.py         # Category classification & MiniLM embeddings
│   │   │   ├── dedup.py            # pgvector semantic deduplication query
│   │   │   ├── route.py            # Explainable 4-factor university scoring
│   │   │   ├── cluster.py          # Batch cross-district clustering
│   │   │   ├── notify.py           # In-app, SMS, email notifications
│   │   │   └── report_gen.py       # IO spec report generators (CSV, PDF, JSONL, XLSX)
│   │   ├── db/
│   │   │   ├── models.py           # SQLAlchemy async models
│   │   │   └── session.py          # Database session manager
│   │   └── cache/
│   │       └── llm_cache.json      # Offline deterministic fallback cache
│   └── scripts/
│       ├── init_db.sql             # SQL schema + pgvector setup
│       └── seed_data.py            # Seeds 6 universities & 15 challenges
│
├── frontend/
│   ├── Dockerfile                  # Multi-stage Node/Nginx build
│   ├── package.json                # React 18, Vite, Tailwind, TanStack Virtual, Lucide
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                 # Route manager
│       ├── components/
│       │   ├── CitizenIntakeForm.jsx   # Clean low-bandwidth submission form
│       │   ├── LiveTrackingCard.jsx    # Real-time citizen progress card
│       │   ├── OfficerReviewQueue.jsx  # High-density virtualized review table
│       │   ├── BatchTriageControl.jsx  # Schedule manager & manual batch trigger
│       │   ├── UniversityPortal.jsx    # Academic inbox & 3-checkpoint milestones
│       │   ├── CSRFundingPortal.jsx    # Industry fund discovery & pledge modal
│       │   └── ScalabilityDashboard.jsx# Worker telemetry & throughput charts
│       └── services/
│           └── api.js                  # Axios client
│
└── output/                         # Mounted persistent directory for IO compliance
    ├── triage/                     # Generated Nitivayu_triage_*.csv files
    ├── sla/                        # Append-only Nitivayu_sla_log_*.csv files
    ├── reports/                    # Generated Nitivayu_routing_report_*.pdf files
    ├── audit/                      # Append-only Nitivayu_audit_*.jsonl files
    └── csr/                        # Generated Nitivayu_csr_matches_*.xlsx files
```

---

## 13. Summary Checklist for Flawless Execution

- [x] **Dual-Cadence AI Triage:** Complete specifications for both real-time instant triage and scheduled weekly/monthly batch cron cycles (`WeeklyBatchTriageWorkflow` & `MonthlyMacroTriageWorkflow`).
- [x] **Durable Temporal Orchestration:** Workflows manage state, retries, cron schedules, and 72h / 7d SLA timers with auto-escalation.
- [x] **OpenRouter Free-Tier & Local MiniLM:** Uses high-speed free-tier models with strict JSON schema, local CPU embeddings (~45ms), and deterministic fallback caching (`LLM_CACHE=1`).
- [x] **Clean, High-Density Scalable UI:** Virtualized table for 10,000+ items, keyboard shortcuts, low-bandwidth mobile intake, and live scalability/worker telemetry.
- [x] **Strict IO Spec Compliance:** Fully specified output generation for CSV with BOM, daily append CSV, weekly PDF, immutable JSONL, and monthly XLSX.
- [x] **Production Docker Compose:** Self-contained orchestration for PostgreSQL 16 pgvector, Temporal dev server, FastAPI backend, worker fleet, and Nginx frontend.
