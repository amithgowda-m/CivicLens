import re
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.schemas import CivicLensState, TypologyCategory

logger = logging.getLogger("civiclens.agent.typology")

# ---------------------------------------------------------------------------
# Tier 1: Heuristic Fast-Tagger  (no LLM calls, pure regex + lexical)
# ---------------------------------------------------------------------------

_TOC_RE = re.compile(r"\.{3,}\s*\d+\s*$", re.MULTILINE)
_HEADER_FOOTER_RE = re.compile(
    r"^\s*(?:\d+\s*$|gazette\s+of\s+india|karnataka\s+gazette|government\s+of\s+[a-zA-Z\s]+(?:notification|dated)|[-=]{10,}|abbreviations?\s*$|table\s+\d+\s*:|annexure\s+[a-z0-9]+\s*:|council\s+agenda\s+item|schedule\s+[ivx0-9]+\s*:|contents\s*:)",
    re.IGNORECASE | re.MULTILINE
)
_ABBREV_RE = re.compile(r"^\s*[A-Z]{2,8}\s*[:\-]\s*[A-Z]", re.MULTILINE)
_DEFN_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?|\([a-z]\))\s+"
    r"[\"'`]?[A-Z][A-Za-z\s\-]{1,60}[\"'`]?\s*"
    r"(?::|-|\bmeans\b|\bshall\s+mean\b|\brefers\s+to\b|\bincludes\b)",
    re.MULTILINE
)
# Catches standalone definition sentences without a leading numbered prefix
# e.g. '"Floor Area Ratio" means ...' or 'Gross Plot Area means ...'
_DEFN_RE2 = re.compile(
    r"^[\"'`]?[A-Z][A-Za-z\s\-]{1,60}[\"'`]?\s*"
    r"(?:\bmeans\b|\bshall\s+mean\b|\brefers\s+to\b|\bincludes\b)",
    re.MULTILINE
)

def _tier1_classify(text: str) -> str:
    t_stripped = text.strip()
    t_lower = t_stripped.lower()
    if _TOC_RE.search(t_stripped):
        return "STRUCTURAL"
    if _HEADER_FOOTER_RE.search(t_stripped):
        return "STRUCTURAL"
    if len(t_stripped) < 30 and re.match(r"^[\d\.\-\s]+$", t_stripped):
        return "STRUCTURAL"
    if len(_ABBREV_RE.findall(t_stripped)) >= 2:
        return "STRUCTURAL"
    if _DEFN_RE.search(t_stripped):
        return "DEFINITIONAL"
    if _DEFN_RE2.search(t_stripped):
        return "DEFINITIONAL"
    if re.search(r"\b(?:for the purpose of|as used in) (?:these|this) (?:regulation|bylaw|rule|act|section)\b", t_lower):
        return "DEFINITIONAL"
    operative_keywords = [
        r"\bshall (?:be|not|comply|provide|submit|obtain|maintain|pay)\b",
        r"\bmust (?:be|not|comply|provide|submit|obtain)\b",
        r"\bno (?:person|owner|developer|building|structure|vehicle)\s+shall\b",
        r"\b(?:minimum|maximum|not (?:less|more) than)\s+[\d\.]+\s*(?:m(?:etres?)?|ft|%|sq|ha)\b",
        r"\b(?:penalty|fine|prosecution|imprisonment|cancellation|revocation)\b",
        r"\b(?:is hereby|are hereby) (?:approved|notified|enacted|sanctioned)\b",
        r"\b(?:application|licence|permit|clearance|approval|noc)\s+(?:shall|must|is required)\b",
    ]
    for pat in operative_keywords:
        if re.search(pat, t_lower):
            return "OPERATIVE"
    return "UNCERTAIN"

# ---------------------------------------------------------------------------
# Tier 2: LLM Semantic Verification Gate (authoritative, overrides Tier 1)
# ---------------------------------------------------------------------------

_TIER2_SYSTEM = (
    "You are a municipal document classifier. Classify the clause into EXACTLY ONE of: "
    "STRUCTURAL, DEFINITIONAL, or OPERATIVE.\n"
    "STRUCTURAL = layout artifact, TOC entry, header/footer, signature block, abbreviation glossary.\n"
    "DEFINITIONAL = formally bounds a technical term; does NOT impose obligations, fees, penalties, or physical standards.\n"
    "OPERATIVE = directly imposes an obligation, sets a physical standard (setback/FAR/height), "
    "levies a fee/tax/penalty, grants/withdraws a legal right, or defines an enforcement action.\n"
    'Return JSON only: {"category": "STRUCTURAL"|"DEFINITIONAL"|"OPERATIVE", "confidence": 0.0-1.0}'
)

async def _tier2_classify_batch(texts: List[str]) -> List[str]:
    from backend.llm_client import llm_client
    if not texts:
        return []

    results: List[str] = ["OPERATIVE"] * len(texts)
    chunk_size = 10

    for chunk_start in range(0, len(texts), chunk_size):
        chunk_texts = texts[chunk_start:chunk_start + chunk_size]
        payload = [{"id": i, "text": t[:400]} for i, t in enumerate(chunk_texts)]
        prompt = (
            "Classify each of the following municipal clauses into EXACTLY ONE category: "
            "STRUCTURAL, DEFINITIONAL, or OPERATIVE.\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Respond strictly with a JSON object conforming to:\n"
            '{\n  "classifications": [\n    {"id": 0, "category": "STRUCTURAL"|"DEFINITIONAL"|"OPERATIVE"}\n  ]\n}'
        )
        try:
            raw = await llm_client.generate_text(prompt, system_prompt=_TIER2_SYSTEM, json_mode=True)
            clean_json = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.IGNORECASE)
            clean_json = re.sub(r'\s*```$', '', clean_json).strip()
            parsed = json.loads(clean_json)
            for item in parsed.get("classifications", []):
                idx = item.get("id")
                cat = str(item.get("category", "OPERATIVE")).upper().strip()
                if cat not in ("STRUCTURAL", "DEFINITIONAL", "OPERATIVE"):
                    cat = "OPERATIVE"
                if idx is not None and 0 <= idx < len(chunk_texts):
                    results[chunk_start + idx] = cat
        except Exception as e:
            logger.debug(f"Tier 2 batch classification failed ({e}); defaulting chunk to OPERATIVE (safe).")

    return results

def classify_clause_typology(text: str) -> TypologyCategory:
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
    sample = "\n".join(pages_text[:3]).lower() if pages_text else (filename or "").lower()
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
        top_lines = [l.strip() for l in first_page.split("\n") if len(l.strip()) > 5][:3]
        if top_lines:
            doc_title = top_lines[0][:80]

    has_objection_window = bool(re.search(
        r"\b(?:within\s+\d+\s+(?:days?|weeks?)|inviting\s+objections|file\s+objections?)\b", sample
    ))
    is_draft = bool(re.search(
        r"\b(?:draft\s+notification|draft\s+scheme|preliminary\s+notice|proposed\s+revision)\b", sample
    ))
    is_enacted_plan = bool(
        re.search(
            r"\b(?:revised\s+master\s+plan|zonal\s+regulations|building\s+bye-?laws|g\.o\.\s*no|government\s+order\s+no|approved\s+by\s+(?:the\s+)?government)\b",
            sample
        )
        or ("volume" in sample and "zonal" in sample)
        or ("chapter" in sample and "table" in sample and "setback" in sample and not is_draft and not has_objection_window)
    )
    is_council = bool(re.search(
        r"\b(?:council\s+meeting|proceedings\s+of\s+the\s+council|agenda\s+item|resolution\s+no)\b", sample
    ))
    is_policy = bool(re.search(
        r"\b(?:circular|office\s+memorandum|policy\s+directive|standard\s+operating\s+procedure)\b", sample
    ))

    if is_enacted_plan and not has_objection_window:
        category, status, action = "enacted_regulation_master_plan", "gazetted_enacted_law", "citizen_compliance_guide"
    elif is_council:
        category, status, action = "council_proceedings_minutes", "council_resolution", "accountability_brief"
    elif is_policy:
        category, status, action = "policy_directive", "administrative_guideline", "policy_summary"
    elif is_draft or has_objection_window:
        category, status, action = "draft_consultation_notice", "draft_proposal", "objection_petition"
    else:
        category, status, action = "general_civic_document", "public_record", "citizen_compliance_guide"

    return {
        "document_title": doc_title,
        "document_category": category,
        "document_legal_status": status,
        "action_type_recommended": action
    }

async def typology_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Typology Classifier Agent:
    - Two-tier SDO classification (Tier 1 regex fast-path, Tier 2 LLM for UNCERTAIN only)
    - Tier 2 is ALWAYS authoritative; overrides Tier 1 on disagreement
    - Only OPERATIVE clauses pass to downstream agents
    - STRUCTURAL/DEFINITIONAL go to provenance store only (no polarity scoring)
    """
    logger.info("Executing Typology Classifier Agent...")
    raw_clauses = state.get("raw_clauses", [])
    pages = state.get("pages_text", [])

    tier1_results: List[Tuple[Dict[str, Any], str]] = []
    uncertain_indices: List[int] = []

    for i, clause in enumerate(raw_clauses):
        cat = _tier1_classify(clause.get("text", ""))
        tier1_results.append((clause, cat))
        if cat == "UNCERTAIN":
            uncertain_indices.append(i)

    if uncertain_indices:
        uncertain_texts = [raw_clauses[i].get("text", "") for i in uncertain_indices]
        tier2_cats = await _tier2_classify_batch(uncertain_texts)
        for idx, t2cat in zip(uncertain_indices, tier2_cats):
            clause, t1cat = tier1_results[idx]
            if t1cat != "UNCERTAIN" and t1cat != t2cat:
                logger.info(
                    f"Tier disagreement clause '{clause.get('id')}': "
                    f"Tier1={t1cat} overridden by Tier2={t2cat}"
                )
            tier1_results[idx] = (clause, t2cat)

    classified: List[Dict[str, Any]] = []
    operative_clauses: List[Dict[str, Any]] = []
    provenance_only: List[Dict[str, Any]] = []

    for clause, sdo_cat in tier1_results:
        c_copy = dict(clause)
        domain_cat = classify_clause_typology(c_copy.get("text", ""))
        c_copy["typology"] = domain_cat.value
        c_copy["clause_structural_category"] = sdo_cat
        c_copy["operative"] = (sdo_cat == "OPERATIVE")
        classified.append(c_copy)
        if sdo_cat == "OPERATIVE":
            operative_clauses.append(c_copy)
        else:
            provenance_only.append(c_copy)

    logger.info(
        f"Typology: {len(operative_clauses)} OPERATIVE (forwarded to pipeline), "
        f"{len(provenance_only)} STRUCTURAL/DEFINITIONAL (provenance store only)."
    )

    doc_meta = detect_document_typology_and_status(pages, state.get("filename"))

    return {
        "classified_clauses": operative_clauses,
        "provenance_clauses": provenance_only,
        "all_classified_clauses": classified,
        "document_title": doc_meta["document_title"],
        "document_category": doc_meta["document_category"],
        "document_legal_status": doc_meta["document_legal_status"],
        "action_type_recommended": doc_meta["action_type_recommended"]
    }
