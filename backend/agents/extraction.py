import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.schemas import CivicLensState, Clause
from backend.llm_client import llm_client
from backend.jurisdiction import load_registry, normalize_jurisdiction, build_jurisdiction_regex

logger = logging.getLogger("civiclens.agent.extraction")

class ExtractedClauseDTO(BaseModel):
    text: str
    page: int
    clause_type: str = "general"
    ward: Optional[str] = None
    objection_deadline: Optional[str] = None
    cited_legal_basis: Optional[str] = None
    stated_objection_authority: Optional[str] = None
    jurisdiction_hint: Optional[str] = None

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

AUTHORITY_PATTERN = re.compile(
    r"(?:objections?|suggestions?|representations?|claims?)\s+(?:may\s+be\s+|shall\s+be\s+)?(?:submitted|sent|addressed|filed|forwarded|delivered|lodged)\s+(?:in\s+writing\s+)?(?:to|with)\s+(?:the\s+)?([A-Z][A-Za-z0-9\s,\.\-]{3,80}?(?:Commissioner|Secretary|Officer|Authority|Magistrate|Collector|Director|Planner|Corporation|Board|Committee))",
    re.IGNORECASE
)

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

CIVIC_STOPWORDS = {
    "committee", "committees", "sabha", "sabhas", "development", "fund", "funds",
    "area", "areas", "office", "officer", "councillor", "councillors", "member",
    "members", "boundary", "boundaries", "from", "which", "to", "the", "of",
    "in", "by", "for", "under", "each", "every", "all", "any", "such", "said",
    "new", "plan", "plans", "corporation", "corporations", "authority", "rule", "rules", "level"
}

def extract_ward_number(text: str) -> Optional[str]:
    """Extracts a valid municipal ward number or name, filtering out civic administrative stopwords."""
    num_match = re.search(r"\bward\s*(?:no\.?|number)?\s*[:\-]?\s*(\d+[A-Za-z]?)\b", text, re.IGNORECASE)
    if num_match:
        return num_match.group(1).strip()

    name_match = re.search(r"\bward\s+(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z]+)\b", text, re.IGNORECASE)
    if name_match:
        cand = name_match.group(1).strip()
        if cand.lower() not in CIVIC_STOPWORDS:
            return cand

    return None

def extract_stated_authority(text: str, page_text: Optional[str] = None) -> Optional[str]:
    """Extracts stated objection authority from clause text or surrounding page context."""
    # 1. Look in clause text first
    m = AUTHORITY_PATTERN.search(text)
    if m:
        cand = m.group(1).strip()
        # Clean trailing commas or punctuation
        cand = re.sub(r"[,\.\s]+$", "", cand)
        if len(cand) >= 5:
            return cand

    # 2. Look in full page text if available
    if page_text:
        m2 = AUTHORITY_PATTERN.search(page_text)
        if m2:
            cand = m2.group(1).strip()
            cand = re.sub(r"[,\.\s]+$", "", cand)
            if len(cand) >= 5:
                return cand

    return None

def rule_based_verbatim_extractor(pages_text: List[str], doc_jurisdiction: Optional[str] = None) -> List[Clause]:
    """
    Deterministic rule-based extractor that segments text into complete legal clauses
    (provisos, multi-line operative sections, discrete definitions, complete Illustration blocks).
    Applies auditable validation filters with exemptions for short deadline/citation clauses.
    Guarantees 100% verbatim quotes with exact character offsets.
    """
    if not doc_jurisdiction:
        doc_jurisdiction = normalize_jurisdiction("\n".join(pages_text[:3]))

    clauses: List[Clause] = []
    deadline_regex = re.compile(r"\b(?:within\s+(\d+\s*(?:days?|weeks?|months?)))\b", re.IGNORECASE)
    act_regex = re.compile(r"([A-Z][A-Za-z\s]+Act(?:,\s*\d{4}|\s+\d{4})?(?:\s+Section\s+\d+[A-Za-z]*)?)", re.IGNORECASE)

    clause_counter = 1
    for page_idx, page_content in enumerate(pages_text, start=1):
        if not page_content.strip():
            continue

        illustrations = find_illustrations(page_content)

        # Structural markers outside illustrations (including definition numbers with quotes)
        pattern = re.compile(
            r"(?:^|\n)\s*(?="
            r"Illustration\s*[:\-]|"
            r"Provided\s+(?:further\s+|also\s+)?that|"
            r"\(\d+\)\s*[\"“\u201c\u201d\ufffd\'A-Za-z]|"
            r"\([a-z]\)\s+[A-Za-z]|"
            r"\d+\.\s*[\"“\u201c\u201d\ufffd\'A-Za-z]"
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

            # Skip unmapped CID font artifacts or gazette cover metadata
            if len(re.findall(r"\(cid:\d+\)", chunk)) > 1:
                continue
            if re.search(r"\b(?:DEPARTMENT OF PARLIAMENTARY AFFAIRS|NOTIFICATION NO:\s*DPAL|EXTRAORDINARY GAZETTE)\b", chunk, re.IGNORECASE):
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

            # Exempt date/deadline patterns and statutory citations from 8-word floor
            is_exempt = bool(DATE_OR_CITATION.search(verbatim_text))
            if word_count < 8 and not is_exempt:
                continue

            if not OPERATIVE_PATTERN.search(verbatim_text):
                continue

            # Extract validated metadata
            ward = extract_ward_number(verbatim_text)

            deadline_match = deadline_regex.search(verbatim_text)
            deadline = deadline_match.group(1) if deadline_match else None

            act_match = act_regex.search(verbatim_text)
            citation = act_match.group(1).strip() if act_match else None

            stated_auth = extract_stated_authority(verbatim_text, page_content)

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
                cited_legal_basis=citation,
                stated_objection_authority=stated_auth,
                jurisdiction_hint=doc_jurisdiction,
                extraction_source=["regex"]
            )
            clauses.append(clause)
            clause_counter += 1

    return clauses

def calculate_span_overlap(c1: Clause, c2: Clause) -> float:
    """Calculates directional overlap fraction relative to the shorter span."""
    if c1.page != c2.page:
        return 0.0
    overlap = max(0, min(c1.char_end, c2.char_end) - max(c1.char_start, c2.char_start))
    shorter_len = min(c1.char_end - c1.char_start, c2.char_end - c2.char_start)
    return (overlap / shorter_len) if shorter_len > 0 else 0.0

def deduplicate_and_merge_clauses(regex_clauses: List[Clause], llm_clauses: List[Clause]) -> List[Clause]:
    """
    Merges regex and LLM clauses:
    - If overlap >= 0.65: deduplicates, keeping the better text (regex for citations/deadlines, LLM for prose).
    - Merges metadata and tags extraction_source = ['regex', 'llm'].
    - If non-overlapping, retains both to prevent silent extraction loss.
    """
    merged: List[Clause] = []
    matched_llm_ids = set()

    for r_cl in regex_clauses:
        best_llm: Optional[Clause] = None
        best_overlap = 0.0

        for l_cl in llm_clauses:
            overlap = calculate_span_overlap(r_cl, l_cl)
            if overlap >= 0.65 and overlap > best_overlap:
                best_overlap = overlap
                best_llm = l_cl

        if best_llm:
            matched_llm_ids.add(best_llm.id)
            # Choose text representation: prefer regex if citation/deadline present, else LLM for prose
            has_citation = bool(r_cl.cited_legal_basis or r_cl.objection_deadline)
            chosen_text = r_cl.text if has_citation else best_llm.text
            chosen_start = r_cl.char_start if has_citation else best_llm.char_start
            chosen_end = r_cl.char_end if has_citation else best_llm.char_end

            merged_cl = Clause(
                id=r_cl.id,
                text=chosen_text,
                page=r_cl.page,
                char_start=chosen_start,
                char_end=chosen_end,
                clause_type=best_llm.clause_type or r_cl.clause_type,
                ward=r_cl.ward or best_llm.ward,
                objection_deadline=r_cl.objection_deadline or best_llm.objection_deadline,
                cited_legal_basis=r_cl.cited_legal_basis or best_llm.cited_legal_basis,
                stated_objection_authority=r_cl.stated_objection_authority or best_llm.stated_objection_authority,
                jurisdiction_hint=r_cl.jurisdiction_hint or best_llm.jurisdiction_hint,
                extraction_source=["regex", "llm"]
            )
            merged.append(merged_cl)
        else:
            merged.append(r_cl)

    # Append unmatched LLM clauses
    for l_cl in llm_clauses:
        if l_cl.id not in matched_llm_ids:
            merged.append(l_cl)

    # Renumber sequentially
    for idx, cl in enumerate(merged, start=1):
        cl.id = f"cl_{idx:02d}"

    return merged

async def extraction_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Extraction Agent: Ingests page map and produces structured verbatim clauses.
    Runs union of regex + LLM extraction with span deduplication and jurisdiction/authority tracking.
    """
    logger.info("Executing Extraction Agent on document pages...")
    load_registry()

    pages = state.get("pages_text", [])
    if state.get("raw_clauses"):
        return {"raw_clauses": state["raw_clauses"]}

    if not pages:
        return {"raw_clauses": []}

    # Determine document jurisdiction hint dynamically
    doc_sample = "\n".join(pages[:3])
    doc_jurisdiction = normalize_jurisdiction(doc_sample)

    # 1. Deterministic rule-based extraction
    rule_clauses = rule_based_verbatim_extractor(pages, doc_jurisdiction)

    # 2. LLM-based extraction (if not mocked / offline)
    llm_clauses: List[Clause] = []
    if os.environ.get("CIVICLENS_MOCK_NLI") != "1":
        system_prompt = (
            "You are an expert municipal legal analyst. Extract all operative civic policy clauses from the provided document page. "
            "CRITICAL RULE: The 'text' field MUST BE COPIED VERBATIM directly from the page text. NEVER paraphrase, summarize, or alter words. "
            "Extract 'stated_objection_authority' if the document explicitly specifies an authority or officer to whom objections/suggestions must be submitted."
        )
        try:
            for p_idx, p_text in enumerate(pages[:3], start=1):
                if len(p_text.strip()) < 30:
                    continue
                prompt = (
                    f"Document Page {p_idx}:\n\"\"\"\n{p_text}\n\"\"\"\n\n"
                    "Extract structured civic clauses (zoning rules, tax revisions, environmental requirements, deadlines, cited legal acts, stated objection authorities). "
                    "Output strictly JSON conforming to: {\"clauses\": [{\"text\": \"...\", \"page\": " + str(p_idx) + ", \"clause_type\": \"...\", \"ward\": \"...\", \"objection_deadline\": \"...\", \"cited_legal_basis\": \"...\", \"stated_objection_authority\": \"...\"}]}"
                )
                resp = await llm_client.generate_text(prompt, system_prompt=system_prompt, json_mode=True)
                if resp and resp.strip():
                    data = json.loads(resp)
                    for item in data.get("clauses", []):
                        cand_text = item.get("text", "")
                        offsets = find_exact_offsets(p_text, cand_text)
                        if offsets:
                            start, end, verbatim_str = offsets
                            words = verbatim_str.split()
                            if len(words) < 3:
                                continue
                            if DANGLING_END.search(verbatim_str):
                                continue
                            is_exempt = bool(DATE_OR_CITATION.search(verbatim_str))
                            if len(words) < 8 and not is_exempt:
                                continue

                            cl = Clause(
                                id=f"llm_{len(llm_clauses)+1}",
                                text=verbatim_str,
                                page=p_idx,
                                char_start=start,
                                char_end=end,
                                clause_type=item.get("clause_type", "operative_provision"),
                                ward=item.get("ward") or extract_ward_number(verbatim_str),
                                objection_deadline=item.get("objection_deadline"),
                                cited_legal_basis=item.get("cited_legal_basis"),
                                stated_objection_authority=item.get("stated_objection_authority") or extract_stated_authority(verbatim_str, p_text),
                                jurisdiction_hint=doc_jurisdiction,
                                extraction_source=["llm"]
                            )
                            llm_clauses.append(cl)
        except Exception as e:
            logger.info(f"LLM extraction skipped or encountered error ({e}); relying on rule-based extraction.")

    # 3. Union & deduplication
    if llm_clauses:
        final_clauses = deduplicate_and_merge_clauses(rule_clauses, llm_clauses)
    else:
        final_clauses = rule_clauses

    if len(final_clauses) > 30:
        priority = [c for c in final_clauses if c.clause_type in ("zoning_regulation", "taxation_rule", "procedural_deadline")]
        others = [c for c in final_clauses if c.clause_type not in ("zoning_regulation", "taxation_rule", "procedural_deadline")]
        final_clauses = (priority + others)[:30]

    raw_clauses = [c.model_dump() for c in final_clauses]
    logger.info(f"Extraction Agent produced {len(raw_clauses)} verified verbatim clauses (union mode).")
    return {
        "raw_clauses": raw_clauses
    }
