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
    logger.info("Executing Legal Grounding Agent with search-first multi-partitioning...")
    claims = state.get("verified_claims", [])
    grounded_claims: List[Dict[str, Any]] = []

    for item in claims:
        clause = item.get("clause", {})
        citation = clause.get("cited_legal_basis")
        item_copy = dict(item)

        if citation:
            # Infer jurisdiction if not explicitly specified on the clause
            jurisdiction = clause.get("jurisdiction_hint")
            if not jurisdiction or jurisdiction == "_default":
                inferred = normalize_jurisdiction(f"{clause.get('text', '')} {citation}")
                if inferred != "_default":
                    jurisdiction = inferred
                else:
                    jurisdiction = clause.get("jurisdiction_hint") or "_default"

            # 1. Search-First: query state + national partitions together
            matches = vector_store.search_legal_sections(citation, jurisdiction=jurisdiction, limit=10)

            # Score matches by section number and statute fidelity
            cit_low = citation.lower()
            scored_matches = []
            for m in matches:
                meta = m.get("metadata", {})
                sec = meta.get("section", "").lower()
                stat = meta.get("statute", "").lower()
                score = 0

                sec_digits = re.sub(r"[^\d]+", "", sec)
                if sec and sec in cit_low:
                    score += 10
                elif sec_digits and (
                    f"section {sec_digits}" in cit_low
                    or f"sec {sec_digits}" in cit_low
                    or f"sec. {sec_digits}" in cit_low
                    or f" {sec_digits} " in f" {cit_low} "
                    or f" {sec_digits}." in f" {cit_low} "
                ):
                    score += 8

                if any(a in cit_low for a in ("ktcp", "town and country planning")) and ("karnataka town" in stat or "ktcp" in stat):
                    score += 5
                elif any(a in cit_low for a in ("gbga", "greater bengaluru")) and ("greater bengaluru" in stat or "gbga" in stat):
                    score += 5
                elif any(a in cit_low for a in ("environment", "ep act")) and ("environment" in stat):
                    score += 5

                if score > 0:
                    scored_matches.append((score, m))

            scored_matches.sort(key=lambda x: x[0], reverse=True)
            best_match = scored_matches[0][1] if scored_matches else None

            if best_match:
                meta = best_match.get("metadata", {})
                stat_text = best_match.get("text", "").lower()
                clause_text = clause.get("text", "").lower()

                # Check for direct statutory contradiction
                is_contradictory = False
                if ("prohibit" in stat_text or "shall not" in stat_text) and any(w in clause_text for w in ("permit", "allowed", "exempt", "relaxation")):
                    is_contradictory = True

                if is_contradictory:
                    grounding = LegalGroundingResult(
                        citation=citation,
                        grounded=False,
                        grounding_status=GroundingStatus.CONTRADICTORY,
                        matched_statute_section=meta.get("section"),
                        statute_name=meta.get("statute"),
                        statute_excerpt=best_match.get("text"),
                        jurisdiction=jurisdiction,
                        notes="Statutory provision directly contradicts the operative proposal claim."
                    )
                else:
                    grounding = LegalGroundingResult(
                        citation=citation,
                        grounded=True,
                        grounding_status=GroundingStatus.MATCHED,
                        matched_statute_section=meta.get("section"),
                        statute_name=meta.get("statute"),
                        statute_excerpt=best_match.get("text"),
                        jurisdiction=jurisdiction,
                        notes=f"Statute citation grounded against {meta.get('jurisdiction', jurisdiction)} statutory corpus."
                    )
            else:
                # Distinguish NOT_FOUND from CORPUS_UNAVAILABLE
                is_avail = has_legal_corpus(jurisdiction) or jurisdiction in ("karnataka_bengaluru", "national", "_default")
                if is_avail and jurisdiction != "unindexed_state":
                    grounding = LegalGroundingResult(
                        citation=citation,
                        grounded=False,
                        grounding_status=GroundingStatus.NOT_FOUND,
                        jurisdiction=jurisdiction,
                        notes=f"Citation '{citation}' was not found in the indexed {jurisdiction} or national statutory corpus."
                    )
                else:
                    grounding = LegalGroundingResult(
                        citation=citation,
                        grounded=False,
                        grounding_status=GroundingStatus.CORPUS_UNAVAILABLE,
                        jurisdiction=jurisdiction,
                        notes=f"Legal corpus for jurisdiction '{jurisdiction}' is not yet indexed. Verified against national partition only."
                    )

            item_copy["legal_grounding"] = grounding.model_dump()
        else:
            item_copy["legal_grounding"] = None

        grounded_claims.append(item_copy)

    return {
        "grounded_claims": grounded_claims
    }
