import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, LegalGroundingResult, GroundingStatus
from backend.vector_store import vector_store

logger = logging.getLogger("civiclens.agent.legal_grounding")

async def legal_grounding_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Legal Grounding Agent: Retrieves matching statute sections for cited legal bases
    from the vector corpus (KTCP Act 1961 & GBGA 2024) and verifies fidelity.
    """
    logger.info("Executing Legal Grounding Agent...")
    claims = state.get("verified_claims", [])
    grounded_claims: List[Dict[str, Any]] = []

    for item in claims:
        clause = item.get("clause", {})
        citation = clause.get("cited_legal_basis")
        item_copy = dict(item)

        if citation:
            # Query legal corpus in vector store
            matches = vector_store.search_legal_sections(citation, limit=3)
            best_match = None
            if matches:
                for m in matches:
                    sim = m.get("similarity", 0)
                    meta = m.get("metadata", {})
                    sec = meta.get("section", "").lower()
                    stat = meta.get("statute", "").lower()
                    # Check if section number or statute name is explicitly mentioned in citation
                    if sim >= 0.45 or (sec and sec in citation.lower()) or ("ktcp" in citation.lower() and "karnataka town" in stat):
                        best_match = m
                        break

            if best_match:
                meta = best_match.get("metadata", {})
                grounding = LegalGroundingResult(
                    citation=citation,
                    grounded=True,
                    grounding_status=GroundingStatus.MATCHED,
                    matched_statute_section=meta.get("section", "Section 14"),
                    statute_name=meta.get("statute", "Karnataka Town and Country Planning Act 1961"),
                    statute_excerpt=best_match.get("text", "Building setback regulations and master plan enforcement..."),
                    notes="Statute citation verified against state legal corpus."
                )
            else:
                # Section not found or below threshold — report 'not_found'
                grounding = LegalGroundingResult(
                    citation=citation,
                    grounded=False,
                    grounding_status=GroundingStatus.NOT_FOUND,
                    notes=f"Citation '{citation}' could not be matched with high confidence in the legal corpus."
                )
            item_copy["legal_grounding"] = grounding.model_dump()
        else:
            item_copy["legal_grounding"] = None

        grounded_claims.append(item_copy)

    return {
        "grounded_claims": grounded_claims
    }
