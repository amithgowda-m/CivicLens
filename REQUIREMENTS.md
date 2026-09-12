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

### Step 3: Environment Configuration
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
- **Function**: Extracts structured clauses conforming to the `Clause` schema. Source text must be copied verbatim with exact character offsets (`char_start`, `char_end`). Paraphrasing is strictly prohibited at this stage.

### Agent 4: Typology Classifier
- **File**: `backend/agents/typology.py`
- **Function**: Classifies each clause into standard civic typologies: `land_use`, `tax`, `infrastructure`, `environmental`, `budget`, or `other`.

### Agent 5: Memory & Contradiction Agent
- **File**: `backend/agents/memory.py`
- **Function**: Embeds clauses into the vector store keyed by ward and typology. Queries existing historical clauses for the same ward to detect and record policy contradictions.

### Agent 6: Verification Ensemble Gate
- **File**: `backend/agents/verification.py`
- **Function**: Executes two independent verification gates per claim:
  1. Local Cross-Encoder NLI score (`cross-encoder/nli-deberta-v3-base`).
  2. LLM-Judge evaluation (`yes` / `no` / `partial` + reasoning).
- **Gating Logic**:
  - `ADMITTED`: NLI >= 0.75 and LLM judge == `yes`.
  - `REJECTED_PRUNED`: NLI < 0.40 and LLM judge == `no`.
  - `PENDING_AUDIT`: Disagreement or borderline scores route to `human_audit_gate`.

### Agent 7: Legal Grounding Agent
- **File**: `backend/agents/legal_grounding.py`
- **Function**: Dynamically retrieves statute sections from `backend/data/legal_corpus/` (e.g., Karnataka Town and Country Planning Act 1961, Greater Bengaluru Governance Act 2024). Sets `grounded: bool` and `grounding_status` (`matched`, `contradictory`, `not_found`).

### Agent 8: Impact Analysis Agent
- **File**: `backend/agents/impact_analysis.py`
- **Function**: Evaluates admitted claims. Determines polarity (`positive`, `negative`, `neutral_mixed`) and names specific affected stakeholder groups concretely.

### Agent 9: Critic Agent (Adversarial)
- **File**: `backend/agents/critic.py`
- **Function**: Challenges each impact tag adversarially to surface counterarguments and identify overlooked subgroups. Merges review attributes directly into `ImpactTag` (`critic_confirmed`, `critic_note`, `overlooked_subgroups`).

### Agent 10: Report Generation Agent
- **File**: `backend/agents/report_generator.py`
- **Function**: Compiles the structured civic report in English using exclusively claims that survived verification and grounding. Fixed section order:
  1. Policy Summary
  2. Stakeholders Impacted
  3. Positive Impacts
  4. Negative Impacts
  5. Risk Flags
  6. Legal Grounding
  7. Claim Confidence (with source offsets)
  8. Policy Contradictions
  9. Overall Verdict (`positive`, `negative`, `mixed` — computed mathematically from polarities).
  - *Note: Bilingual translation is deferred to the final extension stage.*

### Agent 11: Action Agent (On-Demand)
- **File**: `backend/agents/action_agent.py`
- **Function**: Triggered strictly on demand via `POST /api/action`. Generates a formal objection petition if verdict is negative/mixed, or a public awareness bulletin if verdict is positive.

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
| `POST` | `/api/action` | Generates on-demand civic action artifact |
| `GET` | `/api/report/{document_id}` | Retrieves generated report object |
| `GET` | `/api/eval` | Runs evaluation harness and returns reliability metrics |

---

## 6. Deliverable Checkpoints

- [x] **Checkpoint 1**: Scaffold + Docker/Chroma dual backend + Pydantic schemas + LangGraph pipeline stubs + automated test suite passing.
- [ ] **Checkpoint 2**: Extraction + Verification ensemble working on real municipal PDF documents.
- [ ] **Checkpoint 3**: Legal Grounding (KTCP Act 1961 & GBGA 2024 indexing) + Impact Analysis + Critic Agent.
- [ ] **Checkpoint 4**: Report Generation Agent (English) + On-Demand Action Agent.
- [ ] **Checkpoint 5**: Next.js 14 frontend with real-time WebSocket trace stepper and report view.
- [ ] **Final Stage Extension**: Bilingual (Kannada) translation module.
