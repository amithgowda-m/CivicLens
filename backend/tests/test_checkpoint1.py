import pytest
import asyncio
import os
import sys

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.schemas import (
    Clause,
    VerifiedClaim,
    VerificationStatus,
    GroundingStatus,
    LegalGroundingResult,
    ImpactTag,
    ReportData,
    ExecutionPlan
)
from backend.config import settings
from backend.llm_client import llm_client
from backend.vector_store import ChromaVectorStore, vector_store
from backend.graph import civiclens_graph
from backend.agents.action_agent import generate_action_artifact
from backend.agents.eval_harness import run_evaluation

def test_schemas_validation():
    """Verify all Pydantic schemas validate correctly."""
    clause = Clause(
        id="c1",
        text="All commercial establishments in Ward 150 must provide 3.0m setback.",
        page=1,
        char_start=0,
        char_end=68,
        clause_type="zoning",
        ward="150",
        objection_deadline="30 days",
        cited_legal_basis="KTCP Act 1961 Section 14"
    )
    assert clause.text.startswith("All commercial")
    assert clause.ward == "150"

    claim = VerifiedClaim(
        clause=clause,
        nli_score=0.88,
        llm_judge_score=0.92,
        llm_judge_verdict="yes",
        llm_judge_reasoning="Verbatim match",
        status=VerificationStatus.ADMITTED
    )
    assert claim.status == VerificationStatus.ADMITTED

    grounding = LegalGroundingResult(
        citation="KTCP Act 1961 Section 14",
        grounded=True,
        grounding_status=GroundingStatus.MATCHED,
        matched_statute_section="Section 14",
        statute_name="Karnataka Town and Country Planning Act 1961",
        statute_excerpt="Enforcement of master plan and setback requirements"
    )
    assert grounding.grounded is True
    assert grounding.grounding_status == GroundingStatus.MATCHED

    impact = ImpactTag(
        claim_id="c1",
        polarity="negative",
        affected_group="Commercial tenants",
        reasoning="Reduces available shop floor space",
        critic_confirmed=True,
        critic_note="Pedestrians benefit from wider walkways",
        overlooked_subgroups=["Street vendors"]
    )
    assert impact.critic_confirmed is True
    assert "Street vendors" in impact.overlooked_subgroups

def test_vector_store_chroma():
    """Verify embedded Chroma fallback initializes, upserts, and searches."""
    test_clauses = [
        {"id": "test_1", "text": "Setback requirement for ward 150 is 3.0 meters.", "ward": "150", "page": 1, "typology": "land_use"},
        {"id": "test_2", "text": "Property tax rates for ward 150 increased by 5 percent.", "ward": "150", "page": 1, "typology": "tax"}
    ]
    vector_store.upsert_clauses(test_clauses, doc_id="doc_test_101")
    results = vector_store.search_similar_clauses("setback requirement in meters", ward="150", limit=2)
    assert len(results) > 0
    assert "setback" in results[0]["text"].lower()

from backend.graph import civiclens_graph, build_civiclens_graph

@pytest.mark.asyncio
async def test_sequential_graph_execution():
    """Verify graph runs end-to-end through sequential route with dummy input."""
    original_setting = settings.AUTO_APPROVE_PENDING_AUDIT
    settings.AUTO_APPROVE_PENDING_AUDIT = True

    try:
        app = build_civiclens_graph(interrupt_audit=False)
        initial_state = {
            "document_id": "test_doc_seq",
            "filename": "seq_notice.pdf",
            "pages_text": [
                "BBMP Zoning Notice: Ward 150 setback revision to 3.0m under KTCP Act Section 14."
            ]
        }
        config = {"configurable": {"thread_id": "test_thread_seq"}}

        final_state = await app.ainvoke(initial_state, config=config)
        assert final_state is not None
        assert final_state.get("plan") is not None
        assert final_state.get("execution_mode") == "sequential"
        assert len(final_state.get("raw_clauses", [])) > 0
        assert final_state.get("report") is not None
        report = final_state.get("report")
        assert report.get("overall_verdict") in ("positive", "negative", "mixed")
    finally:
        settings.AUTO_APPROVE_PENDING_AUDIT = original_setting

@pytest.mark.asyncio
async def test_fanout_graph_execution():
    """Verify graph executes conditional fan-out and merge when multiple proposals are detected."""
    original_setting = settings.AUTO_APPROVE_PENDING_AUDIT
    settings.AUTO_APPROVE_PENDING_AUDIT = True

    try:
        app = build_civiclens_graph(interrupt_audit=False)
        # 4 pages triggers fan-out per planner logic
        initial_state = {
            "document_id": "test_doc_fanout",
            "filename": "multi_proposal_notice.pdf",
            "pages_text": [
                "Proposal 1: Commercial setback revisions in Bellandur.",
                "Proposal 2: Municipal property tax restructuring for ward 150.",
                "Proposal 3: Stormwater drain infrastructure buffer zones.",
                "Proposal 4: Solid waste segregation mandates."
            ]
        }
        config = {"configurable": {"thread_id": "test_thread_fanout"}}

        final_state = await app.ainvoke(initial_state, config=config)
        assert final_state.get("execution_mode") == "parallel_fan_out"
        assert final_state.get("proposal_merged") is True
        assert final_state.get("report") is not None
    finally:
        settings.AUTO_APPROVE_PENDING_AUDIT = original_setting

@pytest.mark.asyncio
async def test_action_agent():
    """Verify Action Agent produces valid objection letters and awareness summaries."""
    report = ReportData(
        policy_summary="Ward 150 setback and tax changes.",
        stakeholders_impacted=["Shop owners"],
        positive_impacts=[],
        negative_impacts=["Increased financial burden"],
        risk_flags=["Lack of prior notice"],
        overall_verdict="negative"
    )
    artifact = await generate_action_artifact(report)
    assert artifact.action_type == "objection_letter"
    assert "FORMAL OBJECTION" in artifact.content

    report_pos = ReportData(
        policy_summary="Green park expansion.",
        stakeholders_impacted=["Residents"],
        positive_impacts=["Cleaner air"],
        negative_impacts=[],
        risk_flags=[],
        overall_verdict="positive"
    )
    artifact_pos = await generate_action_artifact(report_pos)
    assert artifact_pos.action_type == "awareness_summary"
    assert "COMMUNITY CIVIC BULLETIN" in artifact_pos.content

@pytest.mark.asyncio
async def test_hitl_interrupt_and_resume():
    """Verify LangGraph pauses before human_audit_gate when audit_pending is true and resumes on state update."""
    app = build_civiclens_graph(interrupt_audit=True)
    initial_state = {
        "document_id": "test_doc_hitl",
        "filename": "hitl_notice.pdf",
        "pages_text": [
            "Notice regarding Ward 150 building setback guidelines and parking standards."
        ],
        "raw_clauses": [
            {
                "id": "cl_ambiguous",
                "text": "Proposed amendment: Building setback guidelines may be conditionally revised.",
                "page": 1,
                "char_start": 0,
                "char_end": 70,
                "clause_type": "zoning_regulation",
                "ward": "150",
                "objection_deadline": "30 days",
                "cited_legal_basis": "KTCP Act",
                "typology": "land_use"
            }
        ]
    }
    config = {"configurable": {"thread_id": "test_thread_hitl"}}

    # Execute up to interrupt
    step_state = await app.ainvoke(initial_state, config=config)
    snapshot = app.get_state(config)
    # Graph pauses before human_audit_gate
    assert "human_audit_gate" in snapshot.next

    # Simulate human auditor approving the pending claim via update_state
    app.update_state(
        config,
        {"audit_pending": False},
        as_node="human_audit_gate"
    )

    # Resume execution to completion
    resumed_state = await app.ainvoke(None, config=config)
    assert resumed_state.get("report") is not None

def test_eval_harness_empty():
    """Verify evaluation harness reports awaiting_gold_data and None score when empty."""
    res = run_evaluation("backend/data/gold_test_set")
    assert res["status"] == "awaiting_gold_data"
    assert res["system_reliability_score"] is None
    assert res["eval_documents_count"] == 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])

