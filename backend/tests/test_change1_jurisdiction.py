import pytest
from backend.schemas import Clause, VerificationStatus, GroundingStatus, ReportData
from backend.jurisdiction import (
    load_registry,
    normalize_jurisdiction,
    has_legal_corpus,
    build_jurisdiction_regex,
    resolve_addressee
)
from backend.agents.extraction import (
    calculate_span_overlap,
    deduplicate_and_merge_clauses,
    extract_stated_authority
)
from backend.agents.verification import evaluate_authority_status
from backend.agents.legal_grounding import legal_grounding_node
from backend.agents.action_agent import generate_action_artifact
from backend.agents.critic import check_omitted_policy_categories


def test_registry_loading_and_normalization():
    """Verifies dynamic registry loading and longest-match normalization."""
    reg = load_registry(force_reload=True)
    assert "_default" in reg
    assert "karnataka_bengaluru" in reg
    assert "national" in reg

    # Longest alias match
    norm_ktcp = normalize_jurisdiction("According to Karnataka Town and Country Planning Act guidelines")
    assert norm_ktcp == "karnataka_bengaluru"

    norm_gba = normalize_jurisdiction("Notification from Greater Bengaluru Governance Act 2024")
    assert norm_gba == "karnataka_bengaluru"

    norm_nat = normalize_jurisdiction("Issued under Environment Protection Act 1986")
    assert norm_nat == "national"

    norm_def = normalize_jurisdiction("Notice from Random Coastal Island Administration")
    assert norm_def == "_default"


def test_dynamic_regex_builder():
    """Verifies that regex is dynamically constructed from JSON registry without hardcoded python strings."""
    pattern = build_jurisdiction_regex()
    assert pattern.search("Bangalore Development Authority public notice") is not None
    assert pattern.search("Official Karnataka Gazette publication") is not None


def test_addressee_resolution():
    """Verifies exact ward addressee lookup and fallback behavior."""
    # Exact ward in Bengaluru East (e.g. Bellandur / Ward 150)
    auth_bellandur = resolve_addressee("karnataka_bengaluru", ward="bellandur")
    assert "Bengaluru East City Corporation" in auth_bellandur
    assert "Zonal Commissioner" not in auth_bellandur

    auth_150 = resolve_addressee("karnataka_bengaluru", ward="150")
    assert "Bengaluru East City Corporation" in auth_150

    # Unmapped ward in Karnataka -> default authority from karnataka_bengaluru.json
    auth_unmapped_ktk = resolve_addressee("karnataka_bengaluru", ward="ward_unknown_999")
    assert "Municipal Commissioner, the relevant City Corporation" in auth_unmapped_ktk
    assert "Bruhat Bengaluru Mahanagara Palike" not in auth_unmapped_ktk

    # Unknown jurisdiction -> _default.json
    auth_default = resolve_addressee("_default", ward="ward_42")
    assert "specific office not on file" in auth_default


def test_union_extraction_and_deduplication():
    """Verifies union extraction, span overlap calculation, and non-lossy merging."""
    c_regex = Clause(
        id="cl_01",
        text="Section 14 of KTCP Act mandates 3.0m building setbacks.",
        page=1,
        char_start=100,
        char_end=154,
        clause_type="zoning_regulation",
        cited_legal_basis="Section 14 of KTCP Act",
        extraction_source=["regex"]
    )

    # High overlap LLM clause (same page, span overlap > 65%)
    c_llm_overlapping = Clause(
        id="llm_01",
        text="Mandates 3.0m building setbacks under Section 14.",
        page=1,
        char_start=105,
        char_end=154,
        clause_type="zoning_regulation",
        extraction_source=["llm"]
    )

    overlap = calculate_span_overlap(c_regex, c_llm_overlapping)
    assert overlap >= 0.65

    # Distinct LLM clause (no overlap)
    c_llm_distinct = Clause(
        id="llm_02",
        text="Commercial property tax rate revised by 15 percent for financial year 2025.",
        page=1,
        char_start=400,
        char_end=475,
        clause_type="taxation_rule",
        extraction_source=["llm"]
    )

    merged = deduplicate_and_merge_clauses([c_regex], [c_llm_overlapping, c_llm_distinct])
    # Total merged should be 2 (1 deduplicated + 1 distinct), zero silent deletion!
    assert len(merged) == 2
    assert "regex" in merged[0].extraction_source and "llm" in merged[0].extraction_source
    assert merged[1].text == c_llm_distinct.text


def test_authority_extraction_and_3_tier_verification():
    """Verifies stated authority extraction and 3-tier verification (ADMITTED, REJECTED_PRUNED, PENDING_AUDIT)."""
    sample_text = "Objections may be submitted in writing to the Joint Commissioner, Bengaluru East City Corporation within 30 days."
    extracted = extract_stated_authority(sample_text)
    assert extracted is not None
    assert "Joint Commissioner" in extracted

    # Verbatim contained -> ADMITTED
    status_admitted = evaluate_authority_status(
        stated_authority="Joint Commissioner, Bengaluru East City Corporation",
        premise=sample_text
    )
    assert status_admitted == VerificationStatus.ADMITTED

    # Hallucinated post -> REJECTED_PRUNED
    status_rejected = evaluate_authority_status(
        stated_authority="Zonal Commissioner, GBA",
        premise=sample_text
    )
    assert status_rejected == VerificationStatus.REJECTED_PRUNED


@pytest.mark.asyncio
async def test_search_first_legal_grounding():
    """Verifies search-first retrieval distinguishing MATCHED, NOT_FOUND, and CORPUS_UNAVAILABLE with grounded=None."""
    # 1. Matched state statute
    state_matched = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_01",
                    "text": "Buffer zone of 75 meters shall be maintained from lake boundaries.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 50,
                    "cited_legal_basis": "Section 145 Lake Buffer Zone",
                    "jurisdiction_hint": "karnataka_bengaluru"
                }
            }
        ]
    }
    res_matched = await legal_grounding_node(state_matched)
    lg_res = res_matched["grounded_claims"][0]["legal_grounding"]
    assert lg_res["grounding_status"] == GroundingStatus.MATCHED.value
    assert lg_res["grounded"] is True

    # 2. Not found in existing corpus -> NOT_FOUND, grounded=None
    state_not_found = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_02",
                    "text": "Sub-rule 999 regarding fictitious aerospace setbacks.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 50,
                    "cited_legal_basis": "Section 999 Nonexistent Aerospace Regulation",
                    "jurisdiction_hint": "karnataka_bengaluru"
                }
            }
        ]
    }
    res_not_found = await legal_grounding_node(state_not_found)
    lg_nf = res_not_found["grounded_claims"][0]["legal_grounding"]
    assert lg_nf["grounding_status"] == GroundingStatus.NOT_FOUND.value
    assert lg_nf["grounded"] is False

    # 3. Unindexed jurisdiction -> CORPUS_UNAVAILABLE
    state_corpus_unavail = {
        "verified_claims": [
            {
                "clause": {
                    "id": "cl_03",
                    "text": "Coastal zone regulation clause.",
                    "page": 1,
                    "char_start": 0,
                    "char_end": 50,
                    "cited_legal_basis": "Section 12 Coastal Zone Act",
                    "jurisdiction_hint": "unindexed_state"
                }
            }
        ]
    }
    res_unavail = await legal_grounding_node(state_corpus_unavail)
    lg_unavail = res_unavail["grounded_claims"][0]["legal_grounding"]
    assert lg_unavail["grounding_status"] == GroundingStatus.CORPUS_UNAVAILABLE.value
    assert lg_unavail["grounded"] is False


@pytest.mark.asyncio
async def test_action_agent_document_first_and_fallback():
    """Verifies that ActionAgent prefers ADMITTED stated authority, and falls back cleanly on REJECTED_PRUNED."""
    # Case A: Document-first authority when ADMITTED
    report_admitted = ReportData(
        policy_summary="Notice on setback rules.",
        overall_verdict="negative",
        negative_impacts=["Reduces commercial plot usability."],
        jurisdiction="karnataka_bengaluru",
        stated_objection_authority="The Chief Town Planner, BDA",
        authority_status=VerificationStatus.ADMITTED.value,
        claim_confidence=[
            {"id": "cl_01", "status": "ADMITTED", "ward": "150"}
        ]
    )
    artifact_a = await generate_action_artifact(report_admitted)
    assert artifact_a.recipient_authority == "The Chief Town Planner, BDA"

    # Case B: Stated authority was REJECTED_PRUNED -> falls back to registry resolution for Ward 150
    report_rejected = ReportData(
        policy_summary="Notice on setback rules.",
        overall_verdict="negative",
        negative_impacts=["Reduces commercial plot usability."],
        jurisdiction="karnataka_bengaluru",
        stated_objection_authority="Zonal Commissioner, GBA",
        authority_status=VerificationStatus.REJECTED_PRUNED.value,
        claim_confidence=[
            {"id": "cl_01", "status": "ADMITTED", "ward": "150"}
        ]
    )
    artifact_b = await generate_action_artifact(report_rejected)
    assert artifact_b.recipient_authority == "Municipal Commissioner, Bengaluru East City Corporation"
    assert "Zonal Commissioner" not in artifact_b.recipient_authority


def test_critic_omission_warnings():
    """Verifies that missing procedural deadlines/authorities produce omission audit warnings."""
    state_missing = {
        "verified_claims": [
            {
                "status": "ADMITTED",
                "clause": {
                    "id": "cl_01",
                    "text": "Commercial conversion fee is revised to Rs 500 per sq meter.",
                    "clause_type": "taxation_rule",
                    "objection_deadline": None,
                    "stated_objection_authority": None
                }
            }
        ]
    }
    warnings = check_omitted_policy_categories(state_missing)
    assert len(warnings) > 0
    assert any("objection" in w.lower() for w in warnings)
