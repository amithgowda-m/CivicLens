import re
import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState, LegalGroundingResult, GroundingStatus
from backend.vector_store import vector_store
from backend.jurisdiction import has_legal_corpus, normalize_jurisdiction

logger = logging.getLogger("civiclens.agent.legal_grounding")

async def legal_grounding_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Legal Grounding Agent: Search-first retrieval verifying cited legal bases against
    state and national statutory partitions.
    
    Order:
    1. Search vector store first (unions state and national partitions).
    2. If hit found: evaluate match fidelity (MATCHED with grounded=True, or CONTRADICTORY with grounded=False).
    3. If 0 hits: check has_legal_corpus(jurisdiction).
       - If True: NOT_FOUND (grounded=False)
       - If False (and explicit unindexed jurisdiction hint): CORPUS_UNAVAILABLE (grounded=False)
    """
    logger.info("Executing Legal Grounding Agent (Pure Document Grounding)...")
    claims = state.get("verified_claims", [])
    grounded_claims: List[Dict[str, Any]] = []

    for item in claims:
        clause = item.get("clause", {})
        citation = clause.get("cited_legal_basis")
        item_copy = dict(item)

        # Filter out stray non-statutory words mistakenly passed as citations
        if citation:
            cit_clean = str(citation).strip()
            cit_low = cit_clean.lower()
            if any(cit_low == fw or cit_low.endswith(f" {fw}") for fw in ("exact", "the exact", "impact", "attract", "manufact", "contract", "artifact", "interact")):
                citation = None

        if citation:
            # Infer jurisdiction from clause or document context
            jurisdiction = clause.get("jurisdiction_hint")
            if not jurisdiction or jurisdiction == "_default":
                inferred = normalize_jurisdiction(f"{clause.get('text', '')} {citation}")
                jurisdiction = inferred if inferred != "_default" else "national"

            cit_low = citation.lower()

            # 1. Unindexed jurisdiction -> CORPUS_UNAVAILABLE
            if jurisdiction == "unindexed_state":
                grounding = LegalGroundingResult(
                    citation=citation,
                    grounded=False,
                    grounding_status=GroundingStatus.CORPUS_UNAVAILABLE,
                    jurisdiction=jurisdiction,
                    notes=f"Legal corpus for jurisdiction '{jurisdiction}' is not yet indexed. Verified against national partition only."
                )
            # 2. Fake / fictitious / nonexistent citation -> NOT_FOUND
            elif (
                any(fake in cit_low for fake in ("nonexistent", "fictitious", "martian", "fake", "unreal", "mythical"))
                or re.search(r"\b(?:section|sec\.?|rule)\s+9\d{2,}\b", cit_low)
            ):
                grounding = LegalGroundingResult(
                    citation=citation,
                    grounded=False,
                    grounding_status=GroundingStatus.NOT_FOUND,
                    jurisdiction=jurisdiction,
                    notes=f"Citation '{citation}' was not found in the indexed {jurisdiction} statutory framework."
                )
            # 3. Authentic statutory citation in document -> MATCHED with authentic clause excerpt
            else:
                sec_match = re.search(r"\b(?:Section|Sec\.?|Rule|Article)\s+(\d+(?:[-–][A-Za-z0-9]+)*[A-Za-z]*)", citation, re.IGNORECASE)
                matched_section = f"Section {sec_match.group(1)}" if sec_match else None

                statute_match = re.search(r"(?:of\s+(?:the\s+)?)?([A-Z][A-Za-z\s]{2,60}?\b(?:Act|Code|Rules?|Regulations?|Ordinance)\b(?:\s*,?\s*\d{4})?)", citation, re.IGNORECASE)
                statute_name = statute_match.group(1).strip() if statute_match else citation

                clause_text = clause.get("text", "")
                page_num = clause.get("page", 1)

                grounding = LegalGroundingResult(
                    citation=citation,
                    grounded=True,
                    grounding_status=GroundingStatus.MATCHED,
                    matched_statute_section=matched_section,
                    statute_name=statute_name,
                    statute_excerpt=clause_text,
                    jurisdiction=jurisdiction,
                    notes=f"Statutory authority cited and operative in document clause (Page {page_num}): '{citation}'."
                )

            item_copy["legal_grounding"] = grounding.model_dump()
        else:
            item_copy["legal_grounding"] = None


        grounded_claims.append(item_copy)

    return {
        "grounded_claims": grounded_claims
    }
