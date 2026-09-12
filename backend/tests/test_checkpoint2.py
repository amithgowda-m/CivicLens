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
