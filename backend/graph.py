import logging
from typing import Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.schemas import CivicLensState
from backend.config import settings

# Import Agent Nodes
from backend.agents.planner import planner_node
from backend.agents.ingestion import ingestion_node
from backend.agents.extraction import extraction_node
from backend.agents.typology import typology_node
from backend.agents.memory import memory_node
from backend.agents.verification import verification_node
from backend.agents.legal_grounding import legal_grounding_node
from backend.agents.impact_analysis import impact_analysis_node
from backend.agents.critic import critic_node
from backend.agents.report_generator import report_generator_node

logger = logging.getLogger("civiclens.graph")

# Fan-out and merge helper stubs
async def fan_out_proposals_node(state: CivicLensState) -> Dict[str, Any]:
    """Parallel Proposal Fan-out Worker: Processes sub-proposals in parallel branches."""
    logger.info("Executing Fan-out Proposals Worker...")
    chunks = state.get("proposal_chunks", [])
    # Process or parse each proposal branch
    return {"raw_clauses": [
        {
            "id": f"chunk_cl_{i}",
            "text": f"Sub-proposal {c.get('title')}: Specific municipal zoning clause.",
            "page": 1,
            "char_start": 0,
            "char_end": 50,
            "clause_type": "sub_proposal",
            "ward": "150",
            "objection_deadline": "30 days"
        }
        for i, c in enumerate(chunks)
    ]}

async def merge_proposals_node(state: CivicLensState) -> Dict[str, Any]:
    """Merge Proposals Node: Reconciles extracted clauses from fan-out branches."""
    logger.info("Merging proposals from parallel branches...")
    return {"proposal_merged": True}

# Human-In-The-Loop Audit Gate Node
async def human_audit_gate_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Audit Gate Node: If audit_pending is true and AUTO_APPROVE_PENDING_AUDIT is false,
    this node pauses for human confirmation via the /api/audit/{doc_id}/resolve endpoint.
    """
    logger.info("Entering Human Audit Gate...")
    if settings.AUTO_APPROVE_PENDING_AUDIT:
        logger.info("AUTO_APPROVE_PENDING_AUDIT is enabled. Auto-clearing audit lock.")
        return {"audit_pending": False}
    # State remains pending until external update
    return {}

# Routing Functions
def route_after_planner(state: CivicLensState) -> Literal["sequential_pipeline", "parallel_proposal_fan_out"]:
    mode = state.get("execution_mode", "sequential")
    if mode == "parallel_fan_out":
        return "parallel_proposal_fan_out"
    return "sequential_pipeline"

def route_after_verification(state: CivicLensState) -> Literal["human_audit_gate", "legal_grounding"]:
    if state.get("audit_pending") and not settings.AUTO_APPROVE_PENDING_AUDIT:
        return "human_audit_gate"
    return "legal_grounding"

def build_civiclens_graph(interrupt_audit: Optional[bool] = None):
    workflow = StateGraph(CivicLensState)

    # 1. Register Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("ingestion", ingestion_node)
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("fan_out_proposals", fan_out_proposals_node)
    workflow.add_node("merge_proposals", merge_proposals_node)
    workflow.add_node("typology", typology_node)
    workflow.add_node("memory", memory_node)
    workflow.add_node("verification", verification_node)
    workflow.add_node("human_audit_gate", human_audit_gate_node)
    workflow.add_node("legal_grounding", legal_grounding_node)
    workflow.add_node("impact_analysis", impact_analysis_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("report_generation", report_generator_node)

    # 2. Add Edges & Conditional Routing
    workflow.add_edge(START, "planner")

    # Conditional router out of Planner: Sequential vs Fan-out
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "sequential_pipeline": "ingestion",
            "parallel_proposal_fan_out": "fan_out_proposals"
        }
    )

    # Sequential Path
    workflow.add_edge("ingestion", "extraction")
    workflow.add_edge("extraction", "typology")

    # Fan-Out Path
    workflow.add_edge("fan_out_proposals", "merge_proposals")
    workflow.add_edge("merge_proposals", "typology")

    # Common Downstream Path
    workflow.add_edge("typology", "memory")
    workflow.add_edge("memory", "verification")

    # Conditional Router out of Verification: HITL gate vs direct legal grounding
    workflow.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "human_audit_gate": "human_audit_gate",
            "legal_grounding": "legal_grounding"
        }
    )
    workflow.add_edge("human_audit_gate", "legal_grounding")

    workflow.add_edge("legal_grounding", "impact_analysis")
    workflow.add_edge("impact_analysis", "critic")
    workflow.add_edge("critic", "report_generation")
    workflow.add_edge("report_generation", END)

    # Checkpointer for state persistence and interactive HITL
    checkpointer = MemorySaver()
    should_interrupt = (not settings.AUTO_APPROVE_PENDING_AUDIT) if interrupt_audit is None else interrupt_audit
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_audit_gate"] if should_interrupt else []
    )
    return app

civiclens_graph = build_civiclens_graph()
