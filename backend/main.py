import os
import uuid
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.schemas import ReportData, ActionArtifact
from backend.graph import civiclens_graph
from backend.agents.action_agent import generate_action_artifact
from backend.agents.eval_harness import run_evaluation

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civiclens.server")

app = FastAPI(
    title="CivicLens API",
    description="Multi-Agent Civic Document Analysis System Backend",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active document buffers in memory for analysis
DOC_STORE: Dict[str, Dict[str, Any]] = {}

class AuditResolutionRequest(BaseModel):
    claim_id: str
    action: str  # "APPROVE" | "REJECT"
    notes: Optional[str] = None

class ActionRequest(BaseModel):
    report: ReportData

@app.get("/")
async def root():
    return {"name": "CivicLens API", "status": "online", "llm_provider": settings.LLM_PROVIDER}

@app.get("/api/samples")
async def list_sample_docs():
    """Lists available municipal documents in the sample_docs directory."""
    sample_dir = "backend/data/sample_docs"
    os.makedirs(sample_dir, exist_ok=True)
    samples = [f for f in os.listdir(sample_dir) if f.lower().endswith((".pdf", ".txt"))]
    return {"samples": samples}

@app.post("/api/upload")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    sample_name: Optional[str] = Query(None)
):
    """
    Accepts either an uploaded PDF file or a selection from sample_docs.
    Returns a unique document_id to track the live WebSocket trace.
    """
    doc_id = str(uuid.uuid4())[:8]

    if file:
        content = await file.read()
        filename = file.filename
    elif sample_name:
        sample_path = os.path.join("backend/data/sample_docs", sample_name)
        if not os.path.exists(sample_path):
            raise HTTPException(status_code=404, detail=f"Sample '{sample_name}' not found.")
        with open(sample_path, "rb") as f:
            content = f.read()
        filename = sample_name
    else:
        # Provide synthetic demo notice for zero-setup execution
        filename = "bbmp_zoning_ward150_notice.pdf"
        content = b"%PDF-1.4 CivicLens synthetic municipal notice for testing"

    DOC_STORE[doc_id] = {
        "document_id": doc_id,
        "filename": filename,
        "raw_bytes": content
    }

    return {
        "document_id": doc_id,
        "filename": filename,
        "trace_ws_url": f"/ws/trace/{doc_id}"
    }

@app.websocket("/ws/trace/{document_id}")
async def trace_websocket(websocket: WebSocket, document_id: str):
    """
    Streams LangGraph agent execution events to the Next.js client in real-time
    using LangGraph's native astream_events(..., version='v2').
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for document_id: {document_id}")

    doc_data = DOC_STORE.get(document_id)
    if not doc_data:
        # Initialize default demo state if not pre-uploaded
        doc_data = {
            "document_id": document_id,
            "filename": "demo_notice.pdf",
            "raw_bytes": b"%PDF-1.4 demo bytes"
        }
        DOC_STORE[document_id] = doc_data

    initial_state = {
        "document_id": document_id,
        "filename": doc_data["filename"],
        "raw_bytes": doc_data["raw_bytes"]
    }
    config = {"configurable": {"thread_id": document_id}}

    try:
        # Stream discrete node start, end, and planner events
        async for event in civiclens_graph.astream_events(initial_state, config=config, version="v2"):
            kind = event["event"]
            node_name = event.get("metadata", {}).get("langgraph_node")

            if kind == "on_chain_start" and node_name:
                await websocket.send_json({
                    "event_type": "node_start",
                    "node": node_name,
                    "timestamp": event.get("created_at")
                })

            elif kind == "on_chain_end" and node_name:
                output_data = event.get("data", {}).get("output")
                # Detect planner's printed execution plan
                if node_name == "planner" and output_data:
                    await websocket.send_json({
                        "event_type": "planner_plan",
                        "node": "planner",
                        "plan": output_data.get("plan")
                    })

                await websocket.send_json({
                    "event_type": "node_end",
                    "node": node_name,
                    "output": output_data
                })

        # Check current state in memory
        current_state = civiclens_graph.get_state(config)
        if current_state.next and "human_audit_gate" in current_state.next:
            await websocket.send_json({
                "event_type": "pipeline_paused",
                "reason": "human_audit_required",
                "next_nodes": current_state.next
            })
        else:
            final_report = current_state.values.get("report")
            await websocket.send_json({
                "event_type": "pipeline_complete",
                "report": final_report
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for document {document_id}")
    except Exception as e:
        logger.error(f"Error during graph execution trace: {e}")
        try:
            await websocket.send_json({"event_type": "error", "message": str(e)})
        except Exception:
            pass

@app.post("/api/audit/{document_id}/resolve")
async def resolve_audit(document_id: str, resolution: AuditResolutionRequest):
    """
    Human-In-The-Loop Audit Endpoint:
    Receives human decision, updates the paused thread state in MemorySaver,
    and resumes graph execution from the breakpoint.
    """
    config = {"configurable": {"thread_id": document_id}}
    state_snap = civiclens_graph.get_state(config)

    if not state_snap.values:
        raise HTTPException(status_code=404, detail="Document thread not found or expired.")

    logger.info(f"Resolving audit for claim {resolution.claim_id}: {resolution.action}")

    # Update verified claims with human approval decision
    claims = state_snap.values.get("verified_claims", [])
    updated_claims = []
    for c in claims:
        if c.get("clause", {}).get("id") == resolution.claim_id:
            c_copy = dict(c)
            c_copy["human_audited"] = True
            c_copy["audit_decision"] = resolution.action
            c_copy["audit_notes"] = resolution.notes
            if resolution.action == "APPROVE":
                c_copy["status"] = "ADMITTED"
            else:
                c_copy["status"] = "REJECTED_PRUNED"
            updated_claims.append(c_copy)
        else:
            updated_claims.append(c)

    # Resume graph by updating state and unblocking audit gate
    civiclens_graph.update_state(
        config,
        {"verified_claims": updated_claims, "audit_pending": False},
        as_node="human_audit_gate"
    )

    # Continue execution to completion
    resumed_output = await civiclens_graph.ainvoke(None, config=config)
    return {
        "status": "audit_resolved",
        "document_id": document_id,
        "report": resumed_output.get("report")
    }

@app.post("/api/action", response_model=ActionArtifact)
async def invoke_action_agent(req: ActionRequest):
    """
    Action Agent Endpoint (On-Demand only):
    Drafts an objection letter or public awareness summary based on computed report verdict.
    """
    artifact = await generate_action_artifact(req.report)
    return artifact

@app.get("/api/eval")
async def run_eval_endpoint():
    """Runs the precision/recall evaluation harness and returns system reliability metrics."""
    return run_evaluation()

@app.get("/api/report/{document_id}")
async def get_report(document_id: str):
    """Retrieves generated report for a given document thread."""
    config = {"configurable": {"thread_id": document_id}}
    state = civiclens_graph.get_state(config)
    if not state.values or not state.values.get("report"):
        raise HTTPException(status_code=404, detail="Report not generated yet for this document.")
    return state.values.get("report")
