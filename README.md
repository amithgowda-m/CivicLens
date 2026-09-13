# CivicLens

CivicLens is a multi-agent civic document analysis system designed for municipal transparency. It ingests official municipal notifications, zoning orders, city council agendas, and RTI replies, producing an auditable, structured civic impact report through an orchestrated LangGraph multi-agent pipeline.

---

## Technical Specifications

- **Python Runtime**: Python 3.11 (CPython 3.11.15)
- **Node.js**: Node.js 18+ / 20+ / 24+
- **Backend Framework**: FastAPI (async), Uvicorn, LangGraph
- **Vector Store**: Dual-backend interface supporting PostgreSQL with pgvector, with zero-configuration fallback to embedded ChromaDB
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (Local)
- **Verification Cross-Encoder**: `cross-encoder/nli-deberta-v3-base` (Local)
- **LLM Abstraction**: Configurable via `LLM_PROVIDER` (`gemini`, `anthropic`, `openai`, `ollama`), defaulting to local Ollama (`llama3.1:8b`)

---

## Environment Setup

### 1. Repository Setup & Virtual Environment

```bash
git clone <repository_url>
cd CivicLens

# Windows (PowerShell):
py -3.11 -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1

# Linux / macOS:
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
```

### 2. Install Pinned Dependencies

```bash
pip install -r backend/requirements.lock
```

### 3. Configure Environment Variables

Create `.env` from `.env.example`:
```bash
cp .env.example .env
```

Default configuration values:
```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=3
VECTOR_STORE_BACKEND=auto
AUTO_APPROVE_PENDING_AUDIT=false
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000
```

### 4. Pre-warm Neural Models (Optional)

Pre-download embedding and cross-encoder weights to the local HuggingFace cache:
```bash
python backend/scripts/prewarm_models.py
```

---

## Running the Application

### 1. Start the FastAPI Backend
```bash
# Windows (PowerShell):
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Linux / macOS:
source backend/.venv/bin/activate
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# or alternatively:
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Documentation (Swagger)**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/`
- **WebSocket Agent Trace**: `ws://127.0.0.1:8000/ws/trace/{document_id}`
- **System Reliability Benchmark**: `http://127.0.0.1:8000/api/eval`

### 2. Start the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```

- **Web Dashboard**: `http://localhost:3000`

---

## Verification & Automated Testing

Execute the automated test suite across all agents and pipeline flows:

```bash
# Windows (PowerShell):
$env:CIVICLENS_MOCK_NLI="1"; backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Linux / macOS:
CIVICLENS_MOCK_NLI="1" PYTHONPATH=. pytest backend/tests/ -v
```

### Verified Test Coverage (38 Tests Passing):
1. **Pydantic Schema Validation**: `Clause`, `VerifiedClaim`, `ReportData`, `ActionArtifact`, `ExecutionPlan`.
2. **Vector Store & Semantic Retrieval**: Embedded ChromaDB indexing and deterministic similarity scoring.
3. **Execution Modes**: Sequential execution and parallel fan-out proposal routing with proposal merge.
4. **Pure Document Legal Grounding**: Verified against authentic document text; zero external statutory `.txt` file quote hallucinations.
5. **Autonomous Typology & Status**: Identifies enacted Master Plans vs draft consultation notices vs council minutes.
6. **Context-Aware Action Artifacts**: Generates Citizen Compliance & Rights Guides for enacted regulations (no fabricated 30-day deadlines), formal objection petitions for draft proposals, and community bulletins for positive notices.
7. **Human-In-The-Loop Audit**: State pause at `human_audit_gate` and resumption via `/api/audit/{id}/resolve`.
8. **Multi-Genre Civic Documents**: Precision extraction, thematic contradiction aggregation, and procedural safeguards balance.

