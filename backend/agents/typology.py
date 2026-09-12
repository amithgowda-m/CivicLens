import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.schemas import CivicLensState, TypologyCategory

logger = logging.getLogger("civiclens.agent.typology")

def classify_clause_typology(text: str) -> TypologyCategory:
    """Classifies a clause text into standard civic typologies."""
    t = text.lower()
    if any(k in t for k in ["tax", "cess", "rate", "valuation", "assessment", "penalty", "betterment", "fee", "duty"]):
        return TypologyCategory.TAX
    elif any(k in t for k in ["setback", "zoning", "land use", "far", "floor area", "building height", "plot", "coverage", "commercial", "building line"]):
        return TypologyCategory.LAND_USE
    elif any(k in t for k in ["road", "drainage", "water", "sewer", "stormwater", "pipeline", "street", "pavement", "culvert", "metro"]):
        return TypologyCategory.INFRASTRUCTURE
    elif any(k in t for k in ["green", "waste", "pollution", "tree", "lake", "buffer", "park", "segregation", "garbage", "emission"]):
        return TypologyCategory.ENVIRONMENTAL
    elif any(k in t for k in ["budget", "allocation", "grant", "expenditure", "fund", "crore", "lakh"]):
        return TypologyCategory.BUDGET
    else:
        return TypologyCategory.OTHER

def detect_document_typology_and_status(pages_text: List[str], filename: Optional[str] = None) -> Dict[str, str]:
    """
    Autonomously analyzes document text (cover page, government orders, operative headings)
    to classify document category, legal status, real title, and appropriate citizen action.
    """
    sample = "\n".join(pages_text[:3]).lower() if pages_text else (filename or "").lower()

    # 1. Identify Document Title
    doc_title = "Municipal Policy & Planning Document"
    first_page = pages_text[0] if pages_text else ""
    if "revised master plan" in sample or "zonal regulations" in sample:
        vol = "Volume III: Zonal Regulations" if "volume" in sample else "Zonal Regulations"
        year_m = re.search(r"\b(20\d\d)\b", sample)
        year = year_m.group(1) if year_m else "2015"
        doc_title = f"Revised Master Plan {year} - {vol}"
    elif "council" in sample and ("proceeding" in sample or "agenda" in sample or "resolution" in sample):
        doc_title = "Municipal Corporation Council Proceedings & Resolutions"
    elif "right to information" in sample or "rti" in sample:
        doc_title = "RTI Public Information Disclosure Response"
    elif "public notice" in sample or "draft notification" in sample:
        doc_title = "Municipal Public Consultation Notice"
    elif first_page.strip():
        # Clean top lines from first page
        top_lines = [l.strip() for l in first_page.split("\n") if len(l.strip()) > 5][:3]
        if top_lines:
            doc_title = top_lines[0][:80]

    # 2. Distinguish Enacted Law/Master Plan vs Draft Notice vs Council Minutes
    has_objection_window = bool(re.search(r"\b(?:within\s+\d+\s+(?:days?|weeks?)|inviting\s+objections|file\s+objections?)\b", sample))
    is_draft = bool(re.search(r"\b(?:draft\s+notification|draft\s+scheme|preliminary\s+notice|proposed\s+revision)\b", sample))

    is_enacted_plan = bool(
        re.search(r"\b(?:revised\s+master\s+plan|zonal\s+regulations|building\s+bye-?laws|g\.o\.\s*no|government\s+order\s+no|approved\s+by\s+(?:the\s+)?government)\b", sample)
        or ("volume" in sample and "zonal" in sample)
        or ("chapter" in sample and "table" in sample and "setback" in sample and not is_draft and not has_objection_window)
    )

    is_council = bool(
        re.search(r"\b(?:council\s+meeting|proceedings\s+of\s+the\s+council|agenda\s+item|resolution\s+no)\b", sample)
    )

    is_policy = bool(
        re.search(r"\b(?:circular|office\s+memorandum|policy\s+directive|standard\s+operating\s+procedure)\b", sample)
    )

    if is_enacted_plan and not has_objection_window:
        category = "enacted_regulation_master_plan"
        status = "gazetted_enacted_law"
        action = "citizen_compliance_guide"
    elif is_council:
        category = "council_proceedings_minutes"
        status = "council_resolution"
        action = "accountability_brief"
    elif is_policy:
        category = "policy_directive"
        status = "administrative_guideline"
        action = "policy_summary"
    elif is_draft or has_objection_window:
        category = "draft_consultation_notice"
        status = "draft_proposal"
        action = "objection_petition"
    else:
        category = "general_civic_document"
        status = "public_record"
        action = "citizen_compliance_guide"

    return {
        "document_title": doc_title,
        "document_category": category,
        "document_legal_status": status,
        "action_type_recommended": action
    }

async def typology_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Typology Classifier: Tags each clause with an official civic typology,
    and classifies document-level category and legal status.
    """
    logger.info("Executing Typology Classifier Agent...")
    raw_clauses = state.get("raw_clauses", [])
    pages = state.get("pages_text", [])
    classified: List[Dict[str, Any]] = []

    for clause in raw_clauses:
        c_copy = dict(clause)
        cat = classify_clause_typology(c_copy.get("text", ""))
        c_copy["typology"] = cat.value
        classified.append(c_copy)

    doc_meta = detect_document_typology_and_status(pages, state.get("filename"))

    return {
        "classified_clauses": classified,
        "document_title": doc_meta["document_title"],
        "document_category": doc_meta["document_category"],
        "document_legal_status": doc_meta["document_legal_status"],
        "action_type_recommended": doc_meta["action_type_recommended"]
    }
