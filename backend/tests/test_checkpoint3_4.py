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
    CivicLensState
)
from backend.vector_store import vector_store
from backend.agents.legal_grounding import legal_grounding_node
from backend.agents.impact_analysis import impact_analysis_node
from backend.agents.critic import critic_node
from backend.agents.report_generator import report_generator_node
from backend.agents.action_agent import generate_action_artifact

@pytest.mark.asyncio
async def test_legal_grounding_agent_matched():
    """Verify Legal Grounding Agent matches valid KTCP Act citation against legal corpus."""
    state: CivicLensState = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_ktcp",
                    "text": "Development permission is subject to Section 14 setback rules under KTCP Act 1961.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 80,
                    "clause_type": "land_use",
                    "ward": "150",
                    "objection_deadline": "15 days",
                    "cited_legal_basis": "KTCP Act 1961 Section 14",
                    "typology": "land_use"
                },
                "nli_score": 0.89,
                "llm_judge_score": 0.95,
                "status": VerificationStatus.ADMITTED.value
            }
        ]
    }
    result = await legal_grounding_node(state)
    grounded_claims = result.get("grounded_claims", [])
    assert len(grounded_claims) == 1
    lg = grounded_claims[0].get("legal_grounding")
    assert lg is not None
    assert lg.get("grounded") is True
    assert lg.get("grounding_status") == GroundingStatus.MATCHED.value

@pytest.mark.asyncio
async def test_legal_grounding_agent_not_found():
    """Verify Legal Grounding Agent reports NOT_FOUND for non-existent statutory citations."""
    state: CivicLensState = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_fake",
                    "text": "Pursuant to NonExistent Martian Act Section 9999.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 45,
                    "cited_legal_basis": "NonExistent Martian Act Section 9999",
                    "typology": "other"
                },
                "nli_score": 0.80,
                "llm_judge_score": 0.85,
                "status": VerificationStatus.ADMITTED.value
            }
        ]
    }
    result = await legal_grounding_node(state)
    grounded_claims = result.get("grounded_claims", [])
    assert len(grounded_claims) == 1
    lg = grounded_claims[0].get("legal_grounding")
    assert lg is not None
    assert lg.get("grounded") is False
    assert lg.get("grounding_status") == GroundingStatus.NOT_FOUND.value

@pytest.mark.asyncio
async def test_impact_analysis_agent():
    """Verify Impact Analysis Agent generates concrete impact tags for admitted claims."""
    state: CivicLensState = {
        "grounded_claims": [
            {
                "clause": {
                    "id": "cl_tax",
                    "text": "Property tax surcharge on commercial plot conversion increased by 18 percent.",
                    "page": 2,
                    "typology": "tax",
                    "ward": "150"
                },
                "status": VerificationStatus.ADMITTED.value
            }
        ]
    }
    result = await impact_analysis_node(state)
    tags = result.get("impact_tags", [])
    assert len(tags) == 1
    assert tags[0]["polarity"] in ("positive", "negative", "neutral_mixed")
    assert len(tags[0]["affected_group"]) > 0

@pytest.mark.asyncio
async def test_critic_agent():
    """Verify Critic Agent adversarially audits impact tags and surfaces overlooked subgroups."""
    state: CivicLensState = {
        "impact_tags": [
            {
                "claim_id": "cl_tax",
                "polarity": "negative",
                "affected_group": "Commercial shopkeepers",
                "reasoning": "Increased operational surcharge overhead.",
                "critic_confirmed": False,
                "critic_note": "",
                "overlooked_subgroups": [],
                "requires_audit": False
            }
        ]
    }
    result = await critic_node(state)
    reviewed = result.get("critic_reviewed_tags", [])
    assert len(reviewed) == 1
    assert reviewed[0]["critic_confirmed"] in (True, False)
    assert len(reviewed[0]["critic_note"]) > 0

@pytest.mark.asyncio
async def test_report_generator_and_action_agent():
    """Verify Report Generator compiles fixed sections and Action Agent generates targeted artifacts."""
    state: CivicLensState = {
        "grounded_claims": [
            {
                "clause": {"id": "c1", "text": "Setback revision under Section 14 KTCP Act.", "page": 1},
                "status": VerificationStatus.ADMITTED.value,
                "legal_grounding": {
                    "citation": "KTCP Act 1961 Section 14",
                    "grounded": True,
                    "grounding_status": "matched"
                }
            }
        ],
        "critic_reviewed_tags": [
            {
                "claim_id": "c1",
                "polarity": "negative",
                "affected_group": "Shop owners",
                "reasoning": "Higher cost overhead.",
                "overlooked_subgroups": ["Street vendors"]
            }
        ],
        "contradictions": []
    }
    result = await report_generator_node(state)
    report_dict = result.get("report")
    assert report_dict is not None
    assert report_dict["overall_verdict"] == "negative"

    report_obj = ReportData.model_validate(report_dict)
    action_art = await generate_action_artifact(report_obj)
    assert action_art.action_type == "objection_letter"
    assert "objection" in action_art.content.lower()

if __name__ == "__main__":
    pytest.main(["-v", __file__])
