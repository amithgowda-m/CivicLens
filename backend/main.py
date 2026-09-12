import os
import uuid
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Query, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.schemas import ReportData, ActionArtifact
from backend.graph import civiclens_graph
from backend.agents.action_agent import generate_action_artifact
from backend.agents.eval_harness import run_evaluation
from backend.ui_template import get_ui_html

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
    action: Optional[str] = None  # "APPROVE" | "REJECT"
    approved: Optional[bool] = None
    notes: Optional[str] = None

class ActionRequest(BaseModel):
    report: ReportData
    selected_grievances: Optional[List[str]] = None

@app.get("/")
async def root(request: Request):
    """
    Serves the interactive CivicLens browser analysis dashboard for browsers,
    or JSON status if requested via API client.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(content=get_ui_html())
    return JSONResponse({"name": "CivicLens API", "status": "online", "llm_provider": settings.LLM_PROVIDER})

@app.get("/ui", response_class=HTMLResponse)
async def ui_dashboard():
    """Interactive visual dashboard for uploading and verifying municipal documents."""
    return HTMLResponse(content=get_ui_html())

@app.get("/api/samples")
async def list_sample_docs():
    """Lists available municipal documents in the sample_docs directory."""
    sample_dir = "backend/data/sample_docs"
    os.makedirs(sample_dir, exist_ok=True)
    samples = [f for f in os.listdir(sample_dir) if f.lower().endswith((".pdf", ".txt"))]
    return {"samples": samples}

@app.post("/api/upload")
@app.post("/api/documents/upload")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    sample_name: Optional[str] = Form(None),
    analyze: bool = Query(False)
):
    """
    Ingests municipal PDF document via multipart upload or local sample path.
    If analyze=True, executes the pipeline immediately and returns structured extraction & verification results.
    """
    doc_id = str(uuid.uuid4())[:8]

    if file:
        content = await file.read()
        filename = file.filename
    elif sample_name:
        sample_path = os.path.join("backend/data/sample_docs", sample_name)
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                content = f.read()
            filename = sample_name
        else:
            # Graceful fallback: use rich synthetic notice so pipeline always runs
            logger.warning(f"Sample '{sample_name}' not found — using synthetic fallback content.")
            filename = sample_name
            content = (
                "BANGALORE DEVELOPMENT AUTHORITY PUBLIC NOTICE BDA/ZR/2024/150/0892\n"
                "NOTICE UNDER SECTION 14 OF THE KARNATAKA TOWN AND COUNTRY PLANNING ACT 1961\n\n"
                "Proposed revision of commercial setback regulations in Ward 150 (Bellandur, Bengaluru).\n"
                "All commercial buildings on plots between 1000-5000 sq ft shall maintain a mandatory "
                "front setback of 3.0 metres from the plot boundary, increased from the current 1.8 metres "
                "under BDA Regulation Clause 9.1(b).\n\n"
                "Land use reclassification: Survey numbers 42, 43, 44, 67, 68 of Bellandur Village "
                "are proposed for reclassification from Mixed Residential (MR-2) to Commercial (C-2) zone. "
                "Estimated 340 residential units affected.\n\n"
                "Property tax revision under Section 108A: ARV rates revised from Rs 4-8 to Rs 18-45 "
                "per sq ft per annum, representing a 3x to 5x increase for affected property owners.\n\n"
                "Small commercial establishments (1200 tenants, plots under 2000 sq ft) face mandatory "
                "structural modifications with no displacement compensation framework proposed.\n\n"
                "Objection deadline: 30 days from gazette notification. Submit to Joint Commissioner "
                "(Zoning), Bangalore Development Authority, Kumara Park East, Bengaluru 560001.\n\n"
                "Legal basis: KTCP Act 1961 Sections 12, 14, 15; GBGA 2024 Sections 4, 7; "
                "BDA Master Plan 2031 Clauses 7.3, 9.1; BBMP Property Tax Regulation Section 108A."
            ).encode("utf-8")
    else:
        filename = "bbmp_zoning_ward150_notice.pdf"
        content = (
            "BBMP ZONING NOTICE WARD 150: Synthetic demo document for CivicLens pipeline testing. "
            "Commercial setback revision from 1.8m to 3.0m under KTCP Act 1961 Section 14. "
            "Property tax ARV revision under Section 108A affects 1847 properties in Ward 150."
        ).encode("utf-8")


    DOC_STORE[doc_id] = {
        "document_id": doc_id,
        "filename": filename,
        "raw_bytes": content
    }

    resp = {
        "document_id": doc_id,
        "filename": filename,
        "trace_ws_url": f"/ws/trace/{doc_id}"
    }

    if analyze:
        initial_state = {
            "document_id": doc_id,
            "filename": filename,
            "raw_bytes": content
        }
        config = {"configurable": {"thread_id": doc_id}}
        
        async def _run_graph_bg():
            try:
                logger.info(f"Starting background graph pipeline for document_id: {doc_id}")
                final_state = await civiclens_graph.ainvoke(initial_state, config=config)
                report = final_state.get("report")
                if report:
                    DOC_STORE[doc_id]["report"] = report
                    DOC_STORE[doc_id]["final_state"] = final_state
                    logger.info(f"Background graph pipeline COMPLETED for document_id: {doc_id}")
            except Exception as e:
                logger.error(f"Background graph execution error for {doc_id}: {e}")

        asyncio.create_task(_run_graph_bg())

    return resp

@app.post("/api/documents/{document_id}/analyze")
async def analyze_document_endpoint(document_id: str):
    """
    Executes the CivicLens pipeline on an uploaded document and returns complete extraction & verification state.
    """
    doc_data = DOC_STORE.get(document_id)
    if not doc_data:
        raise HTTPException(status_code=404, detail="Document not found.")

    initial_state = {
        "document_id": document_id,
        "filename": doc_data["filename"],
        "raw_bytes": doc_data["raw_bytes"]
    }
    config = {"configurable": {"thread_id": document_id}}
    final_state = await civiclens_graph.ainvoke(initial_state, config=config)
    return {
        "document_id": document_id,
        "filename": doc_data["filename"],
        "pages_count": len(final_state.get("pages_text", [])),
        "raw_clauses": final_state.get("raw_clauses", []),
        "classified_clauses": final_state.get("classified_clauses", []),
        "verified_claims": final_state.get("verified_claims", []),
        "audit_pending": final_state.get("audit_pending", False),
        "report": final_state.get("report")
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

    act = resolution.action or ("APPROVE" if resolution.approved is not False else "REJECT")
    logger.info(f"Resolving audit for claim {resolution.claim_id}: {act}")

    # Update verified claims with human approval decision
    claims = state_snap.values.get("verified_claims", [])
    updated_claims = []
    for c in claims:
        if c.get("clause", {}).get("id") == resolution.claim_id:
            c_copy = dict(c)
            c_copy["human_audited"] = True
            c_copy["audit_decision"] = act
            c_copy["audit_notes"] = resolution.notes
            if act == "APPROVE":
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
    Accepts optional selected_grievances to scope the objection to specific citizen concerns.
    """
    artifact = await generate_action_artifact(req.report, selected_grievances=req.selected_grievances)
    return artifact

@app.get("/api/eval")
async def run_eval_endpoint():
    """Runs the precision/recall evaluation harness and returns system reliability metrics."""
    return run_evaluation()

@app.get("/api/report/{document_id}")
async def get_report(document_id: str):
    """Retrieves generated report for a given document thread."""
    # 1. Check DOC_STORE first (fastest, always populated after analyze)
    doc = DOC_STORE.get(document_id)
    if doc and doc.get("report"):
        return doc["report"]

    # 2. Fallback: check LangGraph MemorySaver thread state
    try:
        config = {"configurable": {"thread_id": document_id}}
        state = civiclens_graph.get_state(config)
        if state.values and state.values.get("report"):
            return state.values["report"]
    except Exception as e:
        logger.warning(f"LangGraph state lookup failed for {document_id}: {e}")

    raise HTTPException(status_code=404, detail="Report not generated yet for this document.")
