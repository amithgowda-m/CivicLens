# CivicLens — System Requirements & Specifications

---

## 1. System Overview

CivicLens is a multi-agent civic document analysis system designed for municipal transparency. It ingests municipal documents (zoning notices, council agendas, RTI replies, and gazette notifications) and produces an auditable, structured civic impact report through a compiled LangGraph pipeline.

---

## 2. Runtime Environment & Toolchain Requirements

The system requires the following runtime versions and tools:

| Component | Required Version | Verification Command |
|---|---|---|
| **Python** | `3.11.15` (CPython 3.11.x) | `python --version` |
| **Node.js** | `v18.x`, `v20.x`, or `v24.19.x` | `node --version` |
| **Package Manager** | `pip >= 24.0` | `pip --version` |
| **Container Engine** | Docker & Docker Compose (Optional) | `docker --version` |
| **Local LLM Engine** | Ollama (Optional offline fallback) | `ollama --version` |

### Core Python Dependencies (Pinned)
All dependencies are pinned in `backend/requirements.lock`:
- `fastapi==0.141.1`
- `uvicorn==0.52.4`
- `langgraph==1.2.11`
- `langchain-core==1.6.3`
- `pydantic==2.13.5`
- `pydantic-settings==2.15.0`
- `chromadb==1.5.9`
- `sentence-transformers==6.0.1`
- `torch==2.14.0`
- `pdfplumber==0.11.10`
- `pytesseract==0.3.13`
- `tenacity==9.1.4`
- `pytest==9.1.1`
- `pytest-asyncio==1.4.0`
- `httpx==0.28.1`
- `asyncpg==0.31.0`
- `psycopg2-binary==2.9.13`

---

## 3. Environment Setup & Dependency Installation

### Step 1: Virtual Environment Setup
```bash
# Windows (PowerShell):
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1

# Linux / macOS:
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
```

### Step 2: Install Locked Dependencies
```bash
pip install -r backend/requirements.lock
```

### Step 3: Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The frontend UI will be accessible at `http://localhost:3000`.

### Step 4: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configuration settings:
- `LLM_PROVIDER`: `ollama` | `gemini` | `anthropic` | `openai` (default: `ollama`)
- `LLM_MODEL`: `llama3.1:8b`
- `LLM_TIMEOUT_SECONDS`: `30`
- `LLM_MAX_RETRIES`: `3`
- `VECTOR_STORE_BACKEND`: `auto` (auto-detects PostgreSQL; falls back to embedded ChromaDB)
- `AUTO_APPROVE_PENDING_AUDIT`: `false` (enables Human-In-The-Loop breakpoint)
- `CHROMA_PERSIST_DIR`: `backend/data/chroma_db`

---

## 4. Pipeline Agent Specifications

### Agent 1: Planner Agent
- **File**: `backend/agents/planner.py`
- **Function**: Inspects document page count and proposal structure. Emits an `ExecutionPlan` designating execution mode as either `sequential` or `parallel_fan_out`.
- **LangGraph Routing**: Implements conditional routing out of START (`route_after_planner`).

### Agent 2: Ingestion Agent
- **File**: `backend/agents/ingestion.py`
- **Function**: Ingests document bytes dynamically from `/api/upload` or `backend/data/sample_docs/`. Extracts text per page using `pdfplumber`. Probes system for `pytesseract`; executes OCR on scanned pages only if the binary is present.

### Agent 3: Extraction Agent
- **File**: `backend/agents/extraction.py`
- **Function**: Extracts structured clauses conforming to the `Clause` schema. Employs a union of regex and LLM extraction with span deduplication. Source text is snapped verbatim with exact character offsets (`char_start`, `char_end`).

### Agent 4: Typology Classifier & Document Classifier
- **File**: `backend/agents/typology.py`
- **Function**: 
  1. Clause-level: Classifies each clause into standard civic typologies: `land_use`, `tax`, `infrastructure`, `environmental`, `budget`, or `other`.
  2. Document-level: Runs autonomous document categorization (`detect_document_typology_and_status`):
     - Extracts authentic document title from cover/page 1 (e.g. *Revised Master Plan 2015 - Volume III: Zonal Regulations*).
     - Categorizes document: `enacted_regulation_master_plan`, `draft_consultation_notice`, `council_proceedings_minutes`, `policy_directive`, or `general_civic_document`.
     - Assigns legal status: `gazetted_enacted_law`, `draft_proposal`, `council_resolution`, `administrative_guideline`, or `public_record`.
     - Determines recommended citizen action type.

### Agent 5: Memory & Contradiction Agent
- **File**: `backend/agents/memory.py`
- **Function**: Embeds clauses into vector store keyed by ward and typology. Queries historical clauses for the same ward to detect and record policy contradictions. Aggregates findings thematically by prior document ID to prevent duplicate listings.

### Agent 6: Verification Ensemble Gate
- **File**: `backend/agents/verification.py`
- **Function**: Executes dual-gate verification per claim:
  1. Local Cross-Encoder NLI score (`cross-encoder/nli-deberta-v3-base`) with token-overlap windowing (prevents neutral-bias penalties on authentic tables/definitions).
  2. LLM-Judge evaluation (`yes` / `no` / `partial` + reasoning).
- **Gating Logic**:
  - `ADMITTED`: NLI >= 0.75 and LLM judge == `yes`.
  - `REJECTED_PRUNED`: NLI < 0.40 and LLM judge == `no`.
  - `PENDING_AUDIT`: Disagreement or borderline scores route to `human_audit_gate`.

### Agent 7: Pure Document Legal Grounding Agent
- **File**: `backend/agents/legal_grounding.py`
- **Function**: Grounds cited legal bases strictly against the document's own verified text and statutory context. All external static statutory text files (`*.txt`) have been eliminated, guaranteeing zero hallucinated statutory quotes or synthetic setback numbers:
  - `MATCHED`: Authentic cited authority; excerpt is taken verbatim from the document clause itself (`grounded: true`).
  - `NOT_FOUND`: Fictitious/non-existent statutory citations (`grounded: false`).
  - `CORPUS_UNAVAILABLE`: Unindexed jurisdiction hints (`grounded: false`).

### Agent 8: Impact Analysis Agent
- **File**: `backend/agents/impact_analysis.py`
- **Function**: Evaluates admitted claims. Determines polarity (`positive`, `negative`, `neutral_mixed`) and names specific affected stakeholder groups concretely with context-derived reasoning.

### Agent 9: Critic Agent (Adversarial)
- **File**: `backend/agents/critic.py`
- **Function**: Challenges each impact tag adversarially to surface counterarguments and identify overlooked subgroups. Merges review attributes directly into `ImpactTag` (`critic_confirmed`, `critic_note`, `overlooked_subgroups`). Checks for structural policy omission warnings.

### Agent 10: Report Generation Agent
- **File**: `backend/agents/report_generator.py`
- **Function**: Compiles the structured civic report in English using exclusively claims that survived verification and grounding. Fixed section order:
  1. Executive Policy Summary (derived strictly from top verified clauses)
  2. Stakeholders Impacted (canonical clustering)
  3. Positive Impacts
  4. Negative Impacts (with dual-agent Impact + Critic perspectives)
  5. Adversarial Risk Flags & Policy Omissions
  6. Statutory Legal Grounding (clause-verbatim excerpts)
  7. Claim Confidence & Source Offsets
  8. Policy Contradictions (deduplicated by prior doc ID)
  9. Overall Verdict (`positive`, `negative`, `mixed` — computed mathematically from polarities).

### Agent 11: Action Agent (On-Demand & Context-Aware)
- **File**: `backend/agents/action_agent.py`
- **Function**: Triggered on demand via `POST /api/action`. Dynamically produces context-appropriate civic engagement artifacts:
  - **Enacted Regulations / Master Plans**: Generates a **Citizen Compliance & Rights Guide** (zoning standards, building line rules, grandfathering protections for pre-existing lawful uses, clearance steps, appeal channels). Target deadline is set to `"Enacted Statutory Regulation (In Force)"` with zero fabricated 30-day deadlines.
  - **Draft Consultation Notices**: Generates a formal objection petition based on citizen grievances.
  - **Positive Notices**: Generates a community awareness bulletin.
  - **Council Minutes**: Generates an accountability brief.

### Agent 12: Evaluation Harness
- **File**: `backend/agents/eval_harness.py`
- **Function**: Evaluates pipeline extraction precision, recall, and impact tag agreement against ground truth files in `backend/data/gold_test_set/`. Exposes results via `GET /api/eval`.

---

## 5. API Endpoint Contracts

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | System health check and active LLM provider status |
| `GET` | `/api/samples` | Lists municipal documents in `backend/data/sample_docs/` |
| `POST` | `/api/upload` | Ingests document file or sample name; returns `document_id` |
| `WS` | `/ws/trace/{document_id}` | Streams LangGraph events in real-time via `astream_events(v2)` |
| `POST` | `/api/audit/{document_id}/resolve` | Resolves `PENDING_AUDIT` and resumes paused thread execution |
| `POST` | `/api/action` | Generates on-demand context-aware action artifact (compliance guide / objection petition) |
| `GET` | `/api/report/{document_id}` | Retrieves generated report object |
| `GET` | `/api/eval` | Runs evaluation harness and returns reliability metrics |

---

## 6. Deliverable Checkpoints

- [x] **Checkpoint 1**: Scaffold + Docker/Chroma dual backend + Pydantic schemas + LangGraph pipeline stubs + automated test suite passing.
- [x] **Checkpoint 2**: Extraction + Verification ensemble working on real municipal PDF documents.
- [x] **Checkpoint 3**: Multi-partition legal grounding + Impact Analysis + Adversarial Critic Agent.
- [x] **Checkpoint 4**: Report Generation Agent (English) + On-Demand Action Agent.
- [x] **Universal Multi-Doc Extension**: Pure Document Grounding (zero external statutory `.txt` files), autonomous document typology, citizen compliance guide generation, and resilient token-overlap NLI verification.

