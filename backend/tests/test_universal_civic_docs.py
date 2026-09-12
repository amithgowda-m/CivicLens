import pytest
import asyncio
from backend.agents.extraction import (
    extract_statutory_citation,
    rule_based_verbatim_extractor,
)
from backend.agents.report_generator import (
    synthesize_stakeholder_groups,
    report_generator_node,
)
from backend.agents.impact_analysis import impact_analysis_node
from backend.agents.critic import check_omitted_policy_categories
from backend.schemas import CivicLensState, VerificationStatus

def test_extract_statutory_citation_precision():
    # Valid legal citations must be extracted
    assert extract_statutory_citation("Under Section 14-A of the Karnataka Town and Country Planning Act, 1961, notice is issued.") is not None
    assert "Section 14-A" in extract_statutory_citation("Under Section 14-A of the Karnataka Town and Country Planning Act, 1961, notice is issued.")
    assert extract_statutory_citation("Pursuant to the Karnataka Municipal Corporations Act, 1976, rates are revised.") == "Karnataka Municipal Corporations Act, 1976"
    assert extract_statutory_citation("In accordance with Section 3 of the KTCP Act, setback rules apply.") is not None

    # False-positive English words containing "act" must be rejected
    assert extract_statutory_citation("The exact setback required for residential buildings shall be 1.5 meters.") is None
    assert extract_statutory_citation("Manufactured goods and industrial equipment are prohibited in this zone.") is None
    assert extract_statutory_citation("The economic impact of this notification will be reviewed annually.") is None
    assert extract_statutory_citation("To attract commercial investments in Ward 150.") is None
    assert extract_statutory_citation("This contract shall be enforceable by the municipal council.") is None

def test_synthesize_stakeholder_groups():
    # Fragmented list of 15+ variations
    raw_stakeholders = [
        "Commercial property developers and pedestrian commuters",
        "Commercial land developers in Ward 150",
        "Real estate developers",
        "Adjacent residential property owners",
        "Residential plot owners",
        "Small commercial shop tenants",
        "Small business owners and shop tenants",
        "Ward 150 residents",
        "General ward residents",
        "Local street vendors and shopkeepers",
        "Low-income informal residents",
        "Ward committee members",
        "Environmental civic activists",
        "Pedestrian commuters",
        "Urban infrastructure builders"
    ]
    canonical = synthesize_stakeholder_groups(raw_stakeholders)
    # Must cluster into 7 or fewer canonical groups
    assert len(canonical) <= 7
    assert len(canonical) >= 3
    # Check that major categories are represented
    assert any("Residential" in g for g in canonical)
    assert any("Commercial" in g for g in canonical)
    assert any("Developer" in g for g in canonical)
    assert any("Pedestrian" in g for g in canonical)

@pytest.mark.asyncio
async def test_contradiction_aggregation_no_duplicates():
    # Simulate 12 contradiction records cycling through 3 document IDs
    mock_contradictions = []
    doc_ids = ["c31f7fb2-aaaa", "67c0d064-bbbb", "c3cb5c98-cccc"]
    for i in range(12):
        pid = doc_ids[i % 3]
        mock_contradictions.append({
            "claim_id": f"cl_{i+1:02d}",
            "ward": "150",
            "prior_doc_id": pid,
            "prior_clause_text": f"Clause text revision {i} regarding commercial setbacks.",
            "similarity_score": 0.85,
            "contradiction_flag": True,
            "notes": f"Found related historical clause in document {pid}"
        })

    state: CivicLensState = {
        "document_id": "current_doc_123",
        "grounded_claims": [
            {
                "clause": {"id": "cl_01", "text": "Setback requirement is 2.5m.", "page": 1, "char_start": 0, "char_end": 30},
                "status": VerificationStatus.ADMITTED.value,
                "nli_score": 0.95,
                "llm_judge_score": 1.0,
            }
        ],
        "critic_reviewed_tags": [
            {
                "claim_id": "cl_01",
                "affected_group": "Commercial property developers",
                "polarity": "neutral_mixed",
                "reasoning": "Higher setbacks reduce floor space but expand pedestrian width.",
                "critic_confirmed": True,
                "critic_note": "Confirmed.",
                "overlooked_subgroups": [],
            }
        ],
        "contradictions": mock_contradictions,
        "omission_warnings": [],
    }

    result = await report_generator_node(state)
    report = result["report"]

    # Must aggregate by prior_doc_id: exactly 3 aggregated records, NOT 12!
    assert len(report["policy_contradictions"]) == 3
    for contra in report["policy_contradictions"]:
        # Check notes summarize the count and doc ID without repeating
        assert "across 4 related clauses" in contra["notes"]
        assert contra["prior_doc_id"][:8] in contra["notes"]

    # Check risk_flags also has aggregated notes without duplicate loops
    flag_notes = [f for f in report["risk_flags"] if "Historical policy variance" in f]
    assert len(flag_notes) == 3

    # Ensure Kannada translation is completely absent
    assert "kannada_translation" not in report

@pytest.mark.asyncio
async def test_procedural_safeguards_balanced_impact():
    state: CivicLensState = {
        "grounded_claims": [
            {
                "clause": {
                    "id": "cl_01",
                    "text": "Any person may file written objections or suggestions within 30 days of this notice to the Commissioner.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 100,
                    "objection_deadline": "30 days",
                    "typology": "land_use"
                },
                "status": VerificationStatus.ADMITTED.value,
                "nli_score": 0.98,
                "llm_judge_score": 1.0
            }
        ]
    }
    # Run impact analysis (fallback mode in tests without live LLM calls)
    impact_res = await impact_analysis_node(state)
    tags = impact_res["impact_tags"]
    assert len(tags) == 1
    assert tags[0]["polarity"] == "positive"
    reason_low = tags[0]["reasoning"].lower()
    assert any(w in reason_low for w in ("safeguard", "protect", "participation", "transparency", "accountability", "influence", "objection", "formal avenue"))

def test_multi_genre_civic_docs_extraction():
    # 1. Council Minutes genre
    council_minutes = (
        "PROCEEDINGS OF THE BRUHAT BENGALURU MAHANAGARA PALIKE COUNCIL MEETING.\n"
        "Resolution No. 45/2025: The Council resolves that building setback for all commercial roads in Ward 150 "
        "shall be maintained at a minimum of 3.0 meters.\n"
        "Objections may be submitted in writing within 15 days to the Commissioner, BBMP."
    )
    clauses_council = rule_based_verbatim_extractor([council_minutes])
    assert len(clauses_council) >= 2
    assert any(c.ward == "150" for c in clauses_council)
    assert any(c.objection_deadline == "15 days" for c in clauses_council)

    # 2. Zoning Regulation genre with strict statutory citation
    zoning_doc = (
        "BENGALURU DEVELOPMENT AUTHORITY (BDA) PLANNING NOTIFICATION.\n"
        "In exercise of powers conferred under Section 14-A of the Karnataka Town and Country Planning Act, 1961, "
        "the Authority hereby notifies change of land use for Ward 174.\n"
        "The exact measurements are specified in Schedule A."
    )
    clauses_zoning = rule_based_verbatim_extractor([zoning_doc])
    assert len(clauses_zoning) >= 1
    cited_clauses = [c for c in clauses_zoning if c.cited_legal_basis]
    assert len(cited_clauses) >= 1
    assert "Section 14-A" in cited_clauses[0].cited_legal_basis
    # "The exact" must NOT be extracted as a citation
    for c in clauses_zoning:
        assert c.cited_legal_basis != "The exact"


def test_detect_document_typology_enacted_vs_draft():
    """Verify autonomous detection of enacted Master Plans vs draft consultation notices."""
    from backend.agents.typology import detect_document_typology_and_status

    rmp_sample = [
        "BANGALORE DEVELOPMENT AUTHORITY\n"
        "G.O. No UDD 540 BEM AA SE 2004, Dated: 22-06-2007\n"
        "Revised Master Plan 2015 - Volume III: Zonal Regulations\n"
        "Chapter 3: Regulations for Main Land Use Zones and Setbacks."
    ]
    meta_rmp = detect_document_typology_and_status(rmp_sample, "bdazoning.pdf")
    assert meta_rmp["document_category"] == "enacted_regulation_master_plan"
    assert meta_rmp["document_legal_status"] == "gazetted_enacted_law"
    assert meta_rmp["action_type_recommended"] == "citizen_compliance_guide"
    assert "Revised Master Plan" in meta_rmp["document_title"]

    draft_sample = [
        "BANGALORE DEVELOPMENT AUTHORITY PUBLIC NOTICE\n"
        "Draft Scheme for commercial zoning revision in Bellandur.\n"
        "Objections and suggestions are invited within 30 days from publication."
    ]
    meta_draft = detect_document_typology_and_status(draft_sample, "draft_notice.pdf")
    assert meta_draft["document_category"] == "draft_consultation_notice"
    assert meta_draft["document_legal_status"] == "draft_proposal"
    assert meta_draft["action_type_recommended"] == "objection_petition"


@pytest.mark.asyncio
async def test_action_agent_enacted_master_plan_no_fabricated_deadline():
    """Verify that enacted master plans generate Citizen Compliance Guides with NO 30-day objection deadline."""
    from backend.agents.action_agent import generate_action_artifact
    from backend.schemas import ReportData

    report = ReportData(
        policy_summary="Master Plan 2015 Zonal Regulations defining setback standards and building lines.",
        overall_verdict="negative",
        negative_impacts=["Stringent building setback standards."],
        jurisdiction="karnataka_bengaluru",
        document_title="Revised Master Plan 2015 - Volume III: Zonal Regulations",
        document_category="enacted_regulation_master_plan",
        document_legal_status="gazetted_enacted_law",
        action_type_recommended="citizen_compliance_guide",
        claim_confidence=[
            {
                "id": "cl_01",
                "text": "Building line is the line up to which the plinth of a building adjoining a street may lawfully extend.",
                "page": 3,
                "status": "ADMITTED"
            }
        ]
    )

    artifact = await generate_action_artifact(report)
    assert artifact.action_type == "compliance_guide"
    assert "CITIZEN COMPLIANCE" in artifact.content.upper()
    # Must NOT have fabricated 30 days deadline
    assert "Within 30 days" not in (artifact.target_deadline or "")


@pytest.mark.asyncio
async def test_pure_document_grounding_uses_clause_text():
    """Verify that legal grounding uses the verbatim document clause as excerpt, with zero external static file quotes."""
    from backend.agents.legal_grounding import legal_grounding_node
    from backend.schemas import GroundingStatus

    clause_text = "Building setback regulations under Section 14 of Karnataka Town and Country Planning Act 1961."
    state = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_rmp",
                    "text": clause_text,
                    "page": 6,
                    "cited_legal_basis": "Section 14 of KTCP Act 1961",
                    "jurisdiction_hint": "karnataka_bengaluru"
                }
            }
        ]
    }

    res = await legal_grounding_node(state)
    lg = res["grounded_claims"][0]["legal_grounding"]
    assert lg["grounding_status"] == GroundingStatus.MATCHED.value
    assert lg["grounded"] is True
    assert lg["matched_statute_section"] == "Section 14"
    assert lg["statute_excerpt"] == clause_text

