import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.schemas import CivicLensState, Clause
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.extraction")

class ExtractedClauseDTO(BaseModel):
    text: str
    page: int
    clause_type: str = "general"
    ward: Optional[str] = None
    objection_deadline: Optional[str] = None
    cited_legal_basis: Optional[str] = None

class ExtractionResponseDTO(BaseModel):
    clauses: List[ExtractedClauseDTO] = Field(default_factory=list)

def find_exact_offsets(page_text: str, candidate: str) -> Optional[Tuple[int, int, str]]:
    """
    Locates candidate text in source page text and snaps it to the exact verbatim slice.
    Handles differences in line breaks or normalized whitespace.
    """
    if not candidate or not page_text:
        return None

    # 1. Exact substring match
    idx = page_text.find(candidate)
    if idx != -1:
        return idx, idx + len(candidate), page_text[idx:idx + len(candidate)]

    # 2. Whitespace-flexible regex match
    words = candidate.strip().split()
    if not words:
        return None

    pattern_str = r"\s+".join(re.escape(w) for w in words)
    try:
        match = re.search(pattern_str, page_text, re.IGNORECASE)
        if match:
            start, end = match.span()
            return start, end, page_text[start:end]
    except Exception:
        pass

    # 3. Sliding window token search for high-overlap match
    norm_page = re.sub(r"\s+", " ", page_text)
    norm_cand = " ".join(words)
    norm_idx = norm_page.lower().find(norm_cand.lower()[:min(len(norm_cand), 40)])
    if norm_idx != -1:
        first_word = words[0]
        f_idx = page_text.lower().find(first_word.lower())
        if f_idx != -1:
            last_word = words[-1]
            l_idx = page_text.lower().find(last_word.lower(), f_idx)
            if l_idx != -1:
                end_idx = l_idx + len(last_word)
                return f_idx, end_idx, page_text[f_idx:end_idx]

    return None

ABBREV_PATTERN = re.compile(r"\b(?:Rs|No|Sec|Dr|Mr|Mrs|viz|i\.e|e\.g|Sq|Ft|vol|para)\.$", re.IGNORECASE)
DATE_OR_CITATION = re.compile(
    r"\b(?:within\s+\d+\s+(?:days?|weeks?|months?|hours?|working\s+days?)|file\s+objections?|objection\s+deadline|objections?\s+within|Section\s+\d+[A-Za-z]*|Act(?:,\s*|\s+)\d{4}|Rule\s+\d+[A-Za-z]*)\b",
    re.IGNORECASE
)
OPERATIVE_PATTERN = re.compile(
    r"(?:setback|far|zoning|land\s+use|building\s+height|coverage|tax|cess|fee|penalty|rate|valuation|assessment|road|drainage|water|sewer|infrastructure|pipeline|environment|green|tree|lake|buffer|pollution|section\s+\d+|act\s+\d{4}|rule\s+\d+|objection|deadline|within\s+\d+\s+days|hearing|notice)",
    re.IGNORECASE
)
DANGLING_END = re.compile(r"\b(?:to\s+the|of\s+the|in\s+the|at\s+the|from\s+the|and|or|by|with|for|under|that)\s*$", re.IGNORECASE)

def find_illustrations(text: str) -> List[Tuple[int, int]]:
    """Identifies complete, unbroken Illustration blocks across lines and worked steps."""
    ills: List[Tuple[int, int]] = []
    for m in re.finditer(r"Illustration\s*[:\-]", text, re.IGNORECASE):
        start = m.start()
        rest = text[start + len(m.group(0)):]
        end_match = re.search(
            r"\n\s*(?=Provided\s+(?:further\s+|also\s+)?that|Illustration\s*[:\-]|\(\d+\)\s+[A-Z]|\([a-z]\)\s+(?:if|where|may|upon|in|the|any|shall)|\d+\.\s+[A-Z])",
            rest,
            re.IGNORECASE
        )
        if end_match:
            end = start + len(m.group(0)) + end_match.start()
        else:
            end = len(text)
        ills.append((start, end))
    return ills

def rule_based_verbatim_extractor(pages_text: List[str]) -> List[Clause]:
    """
    Deterministic rule-based extractor that segments text into complete legal clauses
    (provisos, multi-line operative sections, complete Illustration blocks).
    Applies auditable validation filters with exemptions for short deadline/citation clauses.
    Guarantees 100% verbatim quotes with exact character offsets.
    """
    clauses: List[Clause] = []
    ward_regex = re.compile(r"\b(?:ward\s*(?:no\.?|number)?\s*(\d+|[A-Za-z]+))\b", re.IGNORECASE)
    deadline_regex = re.compile(r"\b(?:within\s+(\d+\s*(?:days?|weeks?|months?)))\b", re.IGNORECASE)
    act_regex = re.compile(r"([A-Z][A-Za-z\s]+Act(?:,\s*\d{4}|\s+\d{4})?(?:\s+Section\s+\d+[A-Za-z]*)?)", re.IGNORECASE)

    clause_counter = 1
    for page_idx, page_content in enumerate(pages_text, start=1):
        if not page_content.strip():
            continue

        illustrations = find_illustrations(page_content)

        # Structural markers outside illustrations
        pattern = re.compile(
            r"(?:^|\n)\s*(?="
            r"Illustration\s*[:\-]|"
            r"Provided\s+(?:further\s+|also\s+)?that|"
            r"\(\d+\)\s+[A-Z]|\([a-z]\)\s+[a-z]|"
            r"\d+\.\s+[A-Z]"
            r")",
            re.IGNORECASE
        )
        splits = [0]
        for m in pattern.finditer(page_content):
            pt = m.start()
            if not any(ill_s < pt < ill_e for ill_s, ill_e in illustrations):
                splits.append(pt)
        for s, e in illustrations:
            splits.extend([s, e])
        splits.append(len(page_content))
        splits = sorted(list(set(splits)))

        raw_units: List[Tuple[int, int, str]] = []
        for i in range(len(splits) - 1):
            s, e = splits[i], splits[i + 1]
            chunk = page_content[s:e].strip()
            if not chunk:
                continue

            is_ill = any(s >= ill_s and e <= ill_e for ill_s, ill_e in illustrations)
            if is_ill:
                orig_s = page_content.find(chunk, s)
                orig_e = orig_s + len(chunk)
                raw_units.append((orig_s, orig_e, chunk))
            else:
                # Segment sentences while preserving abbreviations and numbers with decimals
                sub_start = 0
                for sm in re.finditer(r"(?<=[.!?])\s+(?=[A-Z])", chunk):
                    prefix = chunk[:sm.start()]
                    if ABBREV_PATTERN.search(prefix) or re.search(r"\d+\.$", prefix):
                        continue
                    sent = chunk[sub_start:sm.start()].strip()
                    if sent:
                        orig_s = page_content.find(sent, s)
                        orig_e = orig_s + len(sent)
                        raw_units.append((orig_s, orig_e, sent))
                    sub_start = sm.end()
                remainder = chunk[sub_start:].strip()
                if remainder:
                    orig_s = page_content.find(remainder, s)
                    orig_e = orig_s + len(remainder)
                    raw_units.append((orig_s, orig_e, remainder))

        # Validate candidates against operative criteria, word floor, and exemptions
        for start, end, verbatim_text in raw_units:
            words = verbatim_text.split()
            word_count = len(words)
            if word_count < 3:
                continue

            # Drop dangling phrases ending mid-sentence
            if DANGLING_END.search(verbatim_text):
                continue

            # Point 1: Exempt date/deadline patterns and statutory citations from 8-word floor
            is_exempt = bool(DATE_OR_CITATION.search(verbatim_text))
            if word_count < 8 and not is_exempt:
                continue

            if not OPERATIVE_PATTERN.search(verbatim_text):
                continue

            # Extract metadata
            ward_match = ward_regex.search(verbatim_text)
            ward = ward_match.group(1) if ward_match else None

            deadline_match = deadline_regex.search(verbatim_text)
            deadline = deadline_match.group(1) if deadline_match else None

            act_match = act_regex.search(verbatim_text)
            citation = act_match.group(1).strip() if act_match else None

            # Determine clause type
            c_type = "operative_provision"
            v_low = verbatim_text.lower()
            if "setback" in v_low or "zoning" in v_low:
                c_type = "zoning_regulation"
            elif "tax" in v_low or "cess" in v_low or "penalty" in v_low:
                c_type = "taxation_rule"
            elif "objection" in v_low or "deadline" in v_low or "within" in v_low:
                c_type = "procedural_deadline"
            elif "environment" in v_low or "tree" in v_low or "lake" in v_low:
                c_type = "environmental_mandate"

            clause = Clause(
                id=f"cl_{clause_counter:02d}",
                text=verbatim_text,
                page=page_idx,
                char_start=start,
                char_end=end,
                clause_type=c_type,
                ward=ward,
                objection_deadline=deadline,
                cited_legal_basis=citation
            )
            clauses.append(clause)
            clause_counter += 1

    return clauses

async def extraction_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Extraction Agent: Ingests page map and produces structured verbatim clauses.
    Applies strict text-snapping verification to prevent paraphrasing and hallucinations.
    """
    logger.info("Executing Extraction Agent on document pages...")
    pages = state.get("pages_text", [])
    raw_clauses: List[Dict[str, Any]] = []

    if state.get("raw_clauses"):
        return {"raw_clauses": state["raw_clauses"]}

    if not pages:
        return {"raw_clauses": []}

    # Attempt LLM extraction if LLM is reachable and not in mock test mode
    llm_succeeded = False
    system_prompt = (
        "You are an expert municipal legal analyst. Extract all operative civic policy clauses from the provided document page. "
        "CRITICAL RULE: The 'text' field MUST BE COPIED VERBATIM directly from the page text. NEVER paraphrase, summarize, or alter words."
    )

    extracted_candidates: List[ExtractedClauseDTO] = []
    if os.environ.get("CIVICLENS_MOCK_NLI") != "1":
        try:
            # Check LLM extraction on pages (limit to first 3 pages for latency)
            for p_idx, p_text in enumerate(pages[:3], start=1):
                if len(p_text.strip()) < 30:
                    continue
                prompt = (
                    f"Document Page {p_idx}:\n\"\"\"\n{p_text}\n\"\"\"\n\n"
                    "Extract structured civic clauses (zoning rules, tax revisions, environmental requirements, deadlines, cited legal acts). "
                    "Output strictly JSON conforming to: {\"clauses\": [{\"text\": \"...\", \"page\": " + str(p_idx) + ", \"clause_type\": \"...\", \"ward\": \"...\", \"objection_deadline\": \"...\", \"cited_legal_basis\": \"...\"}]}"
                )
                resp = await llm_client.generate_text(prompt, system_prompt=system_prompt, json_mode=True)
                if resp and resp.strip():
                    data = json.loads(resp)
                    for item in data.get("clauses", []):
                        item["page"] = p_idx
                        extracted_candidates.append(ExtractedClauseDTO.model_validate(item))
            if extracted_candidates:
                llm_succeeded = True
        except Exception as e:
            logger.info(f"LLM extraction skipped or unavailable ({e}); utilizing rule-based verbatim extraction.")
            llm_succeeded = False

    # Snap and verify candidate clauses
    clause_counter = 1
    if llm_succeeded and extracted_candidates:
        for cand in extracted_candidates:
            page_idx = cand.page
            if page_idx <= len(pages):
                page_text = pages[page_idx - 1]
                offsets = find_exact_offsets(page_text, cand.text)
                if offsets:
                    start, end, verbatim_str = offsets
                    words = verbatim_str.split()
                    word_count = len(words)
                    is_exempt = bool(DATE_OR_CITATION.search(verbatim_str))
                    if word_count < 8 and not is_exempt:
                        continue
                    if DANGLING_END.search(verbatim_str):
                        continue
                    clause = Clause(
                        id=f"cl_{clause_counter:02d}",
                        text=verbatim_str,  # SNAPPED directly to source text
                        page=page_idx,
                        char_start=start,
                        char_end=end,
                        clause_type=cand.clause_type,
                        ward=cand.ward,
                        objection_deadline=cand.objection_deadline,
                        cited_legal_basis=cand.cited_legal_basis
                    )
                    raw_clauses.append(clause.model_dump())
                    clause_counter += 1

    # If LLM extracted no valid clauses or was offline, fallback to rule-based verbatim extraction
    if not raw_clauses:
        rule_clauses = rule_based_verbatim_extractor(pages)
        if len(rule_clauses) > 25:
            # Prioritize zoning, taxation, deadlines, and environmental infrastructure
            priority = [c for c in rule_clauses if c.clause_type in ("zoning_regulation", "taxation_rule", "procedural_deadline")]
            others = [c for c in rule_clauses if c.clause_type not in ("zoning_regulation", "taxation_rule", "procedural_deadline")]
            rule_clauses = (priority + others)[:25]
        raw_clauses = [c.model_dump() for c in rule_clauses]

    logger.info(f"Extraction Agent produced {len(raw_clauses)} verified verbatim clauses.")
    return {
        "raw_clauses": raw_clauses
    }
