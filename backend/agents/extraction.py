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
    # Escape candidate tokens and join with flexible whitespace \s+
    words = candidate.strip().split()
    if not words:
        return None

    # Take first 5 and last 5 words if candidate is long
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
        # Search approximate span in original page
        first_word = words[0]
        f_idx = page_text.lower().find(first_word.lower())
        if f_idx != -1:
            last_word = words[-1]
            l_idx = page_text.lower().find(last_word.lower(), f_idx)
            if l_idx != -1:
                end_idx = l_idx + len(last_word)
                return f_idx, end_idx, page_text[f_idx:end_idx]

    return None

def rule_based_verbatim_extractor(pages_text: List[str]) -> List[Clause]:
    """
    Deterministic rule-based extractor that segments text into sentences
    and extracts operative civic clauses (tax, setback, legal acts, deadlines).
    Guarantees 100% verbatim quotes with exact character offsets.
    """
    clauses: List[Clause] = []
    operative_patterns = [
        r"(?:setback|far|zoning|land\s+use|building\s+height|coverage)\b",
        r"(?:tax|cess|fee|penalty|rate|valuation|assessment)\b",
        r"(?:road|drainage|water|sewer|infrastructure|pipeline)\b",
        r"(?:environment|green|tree|lake|buffer|pollution)\b",
        r"(?:section\s+\d+|act\s+\d{4}|rule\s+\d+)\b",
        r"(?:objection|deadline|within\s+\d+\s+days|hearing|notice)\b"
    ]
    combined_regex = re.compile("|".join(operative_patterns), re.IGNORECASE)
    ward_regex = re.compile(r"\b(?:ward\s*(?:no\.?|number)?\s*(\d+|[A-Za-z]+))\b", re.IGNORECASE)
    deadline_regex = re.compile(r"\b(?:within\s+(\d+\s*(?:days|weeks|months)))\b", re.IGNORECASE)
    act_regex = re.compile(r"([A-Z][A-Za-z\s]+Act(?:,\s*\d{4}|\s+\d{4})?(?:\s+Section\s+\d+[A-Za-z]*)?)", re.IGNORECASE)

    clause_counter = 1
    for page_idx, page_content in enumerate(pages_text, start=1):
        if not page_content.strip():
            continue

        # Split text into paragraphs or sentences
        # Preserve sentence start and end offsets in page_content
        for sentence_match in re.finditer(r"([A-Z0-9][^.!?\n]+[.!?]?)", page_content):
            sent_text = sentence_match.group(1).strip()
            if len(sent_text) < 25:
                continue

            if combined_regex.search(sent_text):
                start = sentence_match.start(1)
                end = start + len(sent_text)
                verbatim_text = page_content[start:end]

                # Extract ward if mentioned
                ward_match = ward_regex.search(verbatim_text)
                ward = ward_match.group(1) if ward_match else None

                # Extract deadline if mentioned
                deadline_match = deadline_regex.search(verbatim_text)
                deadline = deadline_match.group(1) if deadline_match else None

                # Extract legal citation if mentioned
                act_match = act_regex.search(verbatim_text)
                citation = act_match.group(1).strip() if act_match else None

                # Determine clause type
                c_type = "operative_provision"
                if "setback" in verbatim_text.lower() or "zoning" in verbatim_text.lower():
                    c_type = "zoning_regulation"
                elif "tax" in verbatim_text.lower() or "cess" in verbatim_text.lower():
                    c_type = "taxation_rule"
                elif "objection" in verbatim_text.lower() or "deadline" in verbatim_text.lower():
                    c_type = "procedural_deadline"

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
        raw_clauses = [c.model_dump() for c in rule_clauses]

    logger.info(f"Extraction Agent produced {len(raw_clauses)} verified verbatim clauses.")
    return {
        "raw_clauses": raw_clauses
    }
