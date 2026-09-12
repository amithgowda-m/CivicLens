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

## Running the Backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/`
- **WebSocket Agent Trace**: `ws://localhost:8000/ws/trace/{document_id}`
- **Evaluation Harness**: `http://localhost:8000/api/eval`

---

## Verification & Testing

Execute the automated test suite:
```bash
# Set CIVICLENS_MOCK_NLI=1 for fast heuristic testing without loading heavy weights:
# Windows (PowerShell):
$env:CIVICLENS_MOCK_NLI="1"; pytest backend/tests/test_checkpoint1.py -v

# Linux / macOS:
CIVICLENS_MOCK_NLI=1 pytest backend/tests/test_checkpoint1.py -v
```

Verified test coverage:
1. Pydantic schema validation (`Clause`, `VerifiedClaim`, `ReportData`, `ActionArtifact`)
2. Embedded ChromaDB vector indexing and cosine similarity retrieval
3. LangGraph sequential plan traversal
4. LangGraph parallel fan-out routing and proposal merge
5. On-demand Action Agent generation
6. Human-In-The-Loop interrupt and state resumption via `update_state`
7. System evaluation benchmark harness
