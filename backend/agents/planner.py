import logging
from typing import Dict, Any
from backend.schemas import CivicLensState, ExecutionPlan

logger = logging.getLogger("civiclens.agent.planner")

async def planner_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Planner Agent: Inspects the uploaded document and emits a structured
    execution plan: 'sequential' or 'parallel_fan_out'.
    """
    logger.info("Executing Planner Agent...")
    pages = state.get("pages_text", [])
    page_count = len(pages) if pages else 1
    doc_id = state.get("document_id", "doc_default")

    # If document has multiple distinct sections or high page count, decide fan-out
    # In Checkpoint 1 dummy run: evaluate proposals or default to sequential
    detected_proposals = []
    if page_count > 3:
        execution_mode = "parallel_fan_out"
        detected_proposals = [f"Proposal Part {i+1}" for i in range(min(page_count, 3))]
        reasoning = f"Document has {page_count} pages with multiple bundled proposals; triggering parallel fan-out."
    else:
        execution_mode = "sequential"
        detected_proposals = ["Single Unified Proposal"]
        reasoning = "Single unified municipal notice detected; executing sequential pipeline."

    plan = ExecutionPlan(
        document_id=doc_id,
        page_count=page_count,
        execution_mode=execution_mode,
        detected_proposals=detected_proposals,
        reasoning=reasoning
    )

    return {
        "plan": plan.model_dump(),
        "execution_mode": execution_mode,
        "proposal_chunks": [{"id": f"chunk_{i}", "title": p} for i, p in enumerate(detected_proposals)]
    }
