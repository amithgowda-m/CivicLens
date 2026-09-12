import io
import os
import sys
import pytest
import asyncio

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.schemas import (
    Clause,
    VerifiedClaim,
    VerificationStatus,
    TypologyCategory,
    CivicLensState
)
from backend.agents.ingestion import extract_pdf_pages, ingestion_node
from backend.agents.extraction import (
    find_exact_offsets,
    rule_based_verbatim_extractor,
    extraction_node
)
from backend.agents.typology import classify_clause_typology, typology_node
from backend.agents.verification import (
    NLIEvaluator,
    evaluate_llm_judge,
    verification_node
)
from backend.graph import build_civiclens_graph

def create_valid_test_pdf() -> bytes:
    """Creates a valid PDF with genuine municipal notice text."""
    lines = [
        "Bruhat Bengaluru Mahanagara Palike Public Notice 2024.",
        "Under Section 14 of KTCP Act 1961, commercial setback in Ward 150 is revised to 3.0 meters.",
        "Property tax on commercial establishments shall be revised under Section 108A.",
        "All objections must be filed within 30 days of publication."
    ]
    content = "BT /F1 12 Tf " + " ".join(f"1 0 0 1 50 {700 - i*30} Tm ({l}) Tj" for i, l in enumerate(lines)) + " ET"
    stream_len = len(content)
    pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length {stream_len} >> stream
{content}
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000300 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
450
%%EOF"""
    return pdf.encode("latin1")

def test_real_pdf_ingestion():
    """Verify that pdfplumber successfully parses bytes into page text."""
    pdf_bytes = create_valid_test_pdf()
    pages = extract_pdf_pages(pdf_bytes, ocr_available=False)
    assert len(pages) >= 1
    full_text = pages[0]
    assert "Ward 150" in full_text
    assert "setback" in full_text.lower()

def test_verbatim_text_snapping():
    """Verify that find_exact_offsets accurately locates the substring in the page."""
    page_text = (
        "Official Gazette Notification: Section 14 mandates that commercial setback "
        "in Ward 150 is revised to 3.0 meters. Objections must be filed within 30 days."
    )
    candidate = "commercial setback in Ward 150 is revised to 3.0 meters."
    
    offsets = find_exact_offsets(page_text, candidate)
    assert offsets is not None
    start, end, snapped = offsets
    
    # Critical verification: the snapped text must match the slice exactly!
    assert page_text[start:end] == snapped
    assert snapped == candidate

def test_rule_based_extractor():
    """Verify that rule_based_verbatim_extractor produces structured Clause models."""
    sample_page = (
        "Bruhat Bengaluru Mahanagara Palike Notice.\n"
        "Commercial setback in Ward 150 is revised to 3.0 meters under Section 14 of KTCP Act 1961.\n"
        "Property tax on non-residential plots will increase by 5 percent.\n"
        "Objections must be filed within 30 days."
    )
    clauses = rule_based_verbatim_extractor([sample_page])
    assert len(clauses) >= 2
    
    # Check that character offsets are exact slices
    for c in clauses:
        assert sample_page[c.char_start:c.char_end] == c.text
        assert len(c.text) > 0

def test_typology_classification():
    """Verify that municipal clauses are categorized into correct typologies."""
    assert classify_clause_typology("Commercial setback is 3.0 meters") == TypologyCategory.LAND_USE
    assert classify_clause_typology("Property tax assessment rates revised") == TypologyCategory.TAX
    assert classify_clause_typology("Stormwater drainage and arterial road culverts") == TypologyCategory.INFRASTRUCTURE
    assert classify_clause_typology("Mandatory tree planting and green cover buffer") == TypologyCategory.ENVIRONMENTAL
    assert classify_clause_typology("Ward budget fund allocation of 2 crore") == TypologyCategory.BUDGET

@pytest.mark.asyncio
async def test_verification_ensemble_admitted():
    """Verify that an exact verbatim supported claim evaluates to ADMITTED."""
    os.environ["CIVICLENS_MOCK_NLI"] = "1"
    premise = "Under Section 14 of KTCP Act 1961, commercial setback in Ward 150 is revised to 3.0 meters."
    claim = "commercial setback in Ward 150 is revised to 3.0 meters."
    
    nli_score = NLIEvaluator.score_premise_hypothesis(premise, claim)
    assert nli_score >= 0.75
    
    judge_res = await evaluate_llm_judge(premise, claim)
    assert judge_res["verdict"] == "yes"
    assert judge_res["score"] >= 0.75
    
    # Both agree -> ADMITTED
    status = VerificationStatus.ADMITTED if (nli_score >= 0.75 and judge_res["verdict"] == "yes") else VerificationStatus.PENDING_AUDIT
    assert status == VerificationStatus.ADMITTED

@pytest.mark.asyncio
async def test_verification_ensemble_rejected():
    """Verify that an unsupported/hallucinated claim evaluates to REJECTED_PRUNED."""
    os.environ["CIVICLENS_MOCK_NLI"] = "1"
    premise = "Under Section 14 of KTCP Act 1961, commercial setback in Ward 150 is revised to 3.0 meters."
    fabricated = "The municipality has waived all property taxes for IT companies completely."
    
    nli_score = NLIEvaluator.score_premise_hypothesis(premise, fabricated)
    assert nli_score < 0.40
    
    judge_res = await evaluate_llm_judge(premise, fabricated)
    assert judge_res["verdict"] == "no"
    
    # Both low -> REJECTED_PRUNED
    status = VerificationStatus.REJECTED_PRUNED if (nli_score < 0.40 and judge_res["verdict"] == "no") else VerificationStatus.PENDING_AUDIT
    assert status == VerificationStatus.REJECTED_PRUNED

@pytest.mark.asyncio
async def test_act36_illustration_single_clause():
    """Verify that an Illustration block with sub-items is extracted as a single, coherent clause."""
    sample_page_61 = (
        "220\n"
        "(3) Upon scrutiny, if the authorized officer has reason to believe that any "
        "return furnished, which is deemed as assessed, is incorrect or has been under assessed resulting in evasion of property tax,\n"
        "Illustration: If payable tax is Rs.150 for the year 2021 but actual property tax "
        "paid is Rs.100 then evaded tax amount is Rs.50. If the payment is happening on "
        "23rd December 2023, then the following shall be payable —\n"
        "(i) Evaded Property Tax Amount = Rs.50\n"
        "(ii) Penalty for evasion = Rs.50\n"
        "(iii) 9% interest on the evaded property tax of Rs.50 shall be calculated as follows —\n"
        "(a) 9% interest on Rs.25 which is 50% of Rs.50, from 31st May 2021 until date of payment\n"
        "(b) 9% interest on the rest Rs.25 which is 50% of Rs.50, from 30th November 2021 until date of payment\n"
        "Provided that the penalty payable by residential properties which have tiled or sheet roof "
        "and is not more than 1000 Sq Ft, have only the ground floor and is self-occupied, shall be 25% of the evaded tax.\n"
    )
    clauses = rule_based_verbatim_extractor([sample_page_61])
    ill_clauses = [c for c in clauses if "illustration:" in c.text.lower()]
    assert len(ill_clauses) == 1, f"Expected exactly 1 illustration clause, found {len(ill_clauses)}"
    single_ill = ill_clauses[0]
    assert len(single_ill.text.split()) >= 60, "Illustration should not be sliced into fragments"
    assert "(i) Evaded Property Tax Amount" in single_ill.text
    assert "9% interest on the rest Rs.25" in single_ill.text

def test_date_and_citation_exemption():
    """Verify Point 1: Short clauses matching deadline or statutory citation patterns are exempt from 8-word floor."""
    page_text = (
        "Public Notice 2024.\n"
        "File objections within 15 days.\n"
        "Section 14 of KTCP Act 1961.\n"
        "Commercial setback is 3.0 meters."
    )
    clauses = rule_based_verbatim_extractor([page_text])
    texts = [c.text for c in clauses]
    assert any("File objections within 15 days" in t for t in texts), "Short deadline clause must be exempt from 8-word floor"
    assert any("Section 14 of KTCP Act 1961" in t for t in texts), "Statutory citation clause must be exempt from 8-word floor"

def test_extract_local_premise_window():
    """Verify Bug 2: Local premise windowing keeps context compact and avoids truncation."""
    from backend.agents.verification import extract_local_premise_window
    long_page = ("Filler sentence for background municipal context. " * 60) + \
                "Under Section 108A, property tax assessment is revised upward by 10 percent. " + \
                ("Trailing context at the end of the legal gazette document. " * 30)
    target = "Under Section 108A, property tax assessment is revised upward by 10 percent."
    char_start = long_page.find(target)
    char_end = char_start + len(target)

    window = extract_local_premise_window(long_page, char_start, char_end, window_chars=600)
    assert target in window
    assert len(window) < len(long_page)
    assert len(window) <= 1200

@pytest.mark.asyncio
async def test_red_team_false_claims():
    """
    Verify Point 3: 5 deliberately-false claims score low on BOTH NLI and Judge,
    strictly resulting in REJECTED_PRUNED.
    """
    from backend.agents.verification import NLIEvaluator, evaluate_llm_judge
    premise = (
        "Under Section 14 of KTCP Act 1961, commercial setback in Ward 150 is revised to 3.0 meters. "
        "All property owners must adhere to zoning regulations. Objections must be filed within 30 days."
    )
    false_claims = [
        "All property taxes across all wards are completely abolished and no civic fees shall ever be collected.",
        "Commercial buildings in Ward 150 are permitted to have zero setbacks with 100% road encroachment.",
        "Citizens are strictly prohibited from submitting any objections or legal petitions at any time.",
        "The municipality offers unconditional 100% cash subsidies for private residential construction.",
        "All environmental protection rules, lake buffer zones, and tree preservation mandates are repealed."
    ]

    for claim_text in false_claims:
        nli_score = NLIEvaluator.score_premise_hypothesis(premise, claim_text)
        judge_res = await evaluate_llm_judge(premise, claim_text)
        
        # Verify both gates reject
        assert nli_score < 0.40, f"Expected NLI < 0.40 for false claim '{claim_text}', got {nli_score}"
        assert judge_res["verdict"] == "no", f"Expected judge verdict 'no' for false claim '{claim_text}', got {judge_res['verdict']}"
        
        # Status must be REJECTED_PRUNED
        status = VerificationStatus.REJECTED_PRUNED if (nli_score < 0.40 and judge_res["verdict"] == "no") else VerificationStatus.PENDING_AUDIT
        assert status == VerificationStatus.REJECTED_PRUNED

@pytest.mark.asyncio
async def test_judge_source_tracking():
    """Verify Point 2: Judge results clearly attribute judge_source ('llm_judge' or 'containment_fallback')."""
    os.environ["CIVICLENS_MOCK_NLI"] = "1"
    premise = "Under Section 14 of KTCP Act 1961, commercial setback in Ward 150 is revised to 3.0 meters."
    claim = "commercial setback in Ward 150 is revised to 3.0 meters."
    
    judge_res = await evaluate_llm_judge(premise, claim)
    assert "judge_source" in judge_res
    assert judge_res["judge_source"] in ("llm_judge", "containment_fallback", "llm_unavailable_audit")
    assert "[" in judge_res["reasoning"]  # Prefixed with [Containment-Fallback] or [LLM-Judge]

@pytest.mark.asyncio
async def test_full_pipeline_checkpoint2():
    """Verify end-to-end traversal from real PDF bytes through extraction, typology, and verification ensemble."""
    os.environ["CIVICLENS_MOCK_NLI"] = "1"
    app = build_civiclens_graph(interrupt_audit=False)
    
    pdf_bytes = create_valid_test_pdf()
    initial_state = {
        "document_id": "doc_cp2_real_pdf",
        "filename": "municipal_notice_sample.pdf",
        "raw_bytes": pdf_bytes
    }
    config = {"configurable": {"thread_id": "thread_cp2"}}
    
    final_state = await app.ainvoke(initial_state, config=config)
    assert final_state is not None
    assert len(final_state.get("pages_text", [])) >= 1
    assert len(final_state.get("raw_clauses", [])) >= 1
    assert len(final_state.get("classified_clauses", [])) >= 1
    assert len(final_state.get("verified_claims", [])) >= 1
    
    # Check that verified claims contain exact character offsets and statuses
    for claim_data in final_state["verified_claims"]:
        assert "status" in claim_data
        assert claim_data["status"] in ("ADMITTED", "PENDING_AUDIT", "REJECTED_PRUNED")
        clause = claim_data["clause"]
        assert clause["char_end"] > clause["char_start"]
        assert len(clause["text"]) > 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])
