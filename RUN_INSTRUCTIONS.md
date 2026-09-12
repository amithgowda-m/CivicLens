# 🚀 How to Run CivicLens

This reference guide contains instructions for running the **CivicLens** multi-agent municipal document analysis system.

---

## 📋 Prerequisites

- **Python 3.10+**
- **Node.js 18+** & `npm`
- Windows / macOS / Linux

---

## ⚡ Quick Start (2 Terminals Required)

Open **two separate terminal windows/tabs** in the project root directory (`c:\Users\adars\OneDrive\Desktop\bitbybuild`).

### 1️⃣ Terminal 1 — Backend (FastAPI Server)

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```
- **API URL**: `http://127.0.0.1:8000`
- **Interactive Dashboard UI**: `http://127.0.0.1:8000/ui`

---

### 2️⃣ Terminal 2 — Frontend (Next.js App)

```powershell
cd frontend
npm run dev
```
- **Frontend App URL**: `http://localhost:3000`

---

## 🛠️ Environment Configuration (`.env`)

The `.env` file in the project root configures provider selection and features:

```ini
# LLM Provider Configuration
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b

# API Key
GROQ_API_KEY=your_groq_api_key_here

# Execution Options
AUTO_APPROVE_PENDING_AUDIT=true
CIVICLENS_MOCK_NLI=1
```

---

## ❓ Frequently Asked Questions & Troubleshooting

### Q: `[WinError 10013]` / "Port 8000 in use"
**Cause:** Another backend process or uvicorn task is already running on port 8000.  
**Fix (PowerShell):**
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Then rerun the backend command.

### Q: `[WinError 10048]` / "Port 3000 in use"
**Cause:** Another Next.js dev server is running on port 3000.  
**Fix (PowerShell):**
```powershell
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Q: Report takes 20-30 seconds to load?
- The 12-agent LangGraph network runs in the background while the UI displays live trace progress.
- Results stream automatically to `http://localhost:3000` as soon as the agents finish synthesis.
