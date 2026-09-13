import re
import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState, ContradictionRecord
from backend.vector_store import vector_store

logger = logging.getLogger("civiclens.agent.memory")

# ---------------------------------------------------------------------------
# Parameter Extraction for Policy-Diff Logic
# ---------------------------------------------------------------------------

def _extract_numeric_params(text: str) -> Optional[float]:
    """
    Extract the first meaningful numeric parameter from a clause text.
    Returns: float if found, None if the clause is qualitative/ambiguous.
    """
    t_low = text.lower()
    # Match values like "3.0 m", "1.5 metres", "50%", "FSI 2.5", "Rs. 500", "25 percent"
    m = re.search(
        r"\b(?:fsi|far|setback|height|width|distance|coverage|rate|fee|tax|penalty|fine|area|lakh|crore|rs\.?|inr)\s*"
        r"(?:of\s+|is\s+|=\s*)?(\d+(?:\.\d+)?)",
        t_low
    )
    if m:
        return float(m.group(1))

    # Units: metres, meters, %, percent, ft, sq m, days, years
    m2 = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:m(?:etres?|eters?)?|ft|%|percent|sq\.?\s*m|hectares?|lakh|crore|days?|years?)\b", t_low)
    if m2:
        return float(m2.group(1))

    # Standalone percentages or ratios e.g. "increased by 25%"
    m3 = re.search(r"\b(\d+(?:\.\d+)?)\s*%", t_low)
    if m3:
        return float(m3.group(1))

    return None


def _classify_contradiction(
    current_text: str,
    prior_text: str,
    similarity: float,
    doc_id: str,
    prior_doc_id: str
) -> str:
    """
    Section 3 parameter-diff logic returning one of:
      POLICY_REVERSAL      - same subject, parameters differ
      IDENTICAL_PROVISION  - same subject, parameters match (suppress from alerts)
      PENDING_AUDIT        - high similarity, parameters unextractable (qualitative)
      IRRELEVANT           - low similarity, skip
    """
    # Self-document guard: discard matches from same document
    if prior_doc_id == doc_id:
        return "IRRELEVANT"

    # Require substantive semantic alignment (>= 0.75) to avoid false qualitative matches
    if similarity < 0.75:
        return "IRRELEVANT"

    # Exact or near-identical text match -> identical provision (suppress)
    cur_clean = current_text.strip().lower()
    pri_clean = prior_text.strip().lower()
    if cur_clean == pri_clean:
        return "IDENTICAL_PROVISION"

    cur_words = set(re.findall(r"\b\w{3,}\b", cur_clean))
    pri_words = set(re.findall(r"\b\w{3,}\b", pri_clean))
    if cur_words and pri_words:
        jaccard = len(cur_words & pri_words) / len(cur_words | pri_words)
        if jaccard >= 0.80:
            return "IDENTICAL_PROVISION"

    current_param = _extract_numeric_params(current_text)
    prior_param = _extract_numeric_params(prior_text)

    if current_param is not None and prior_param is not None:
        if abs(current_param - prior_param) > 1e-6:
            return "POLICY_REVERSAL"
        else:
            return "IDENTICAL_PROVISION"
    else:
        # High similarity but qualitative change - surface for human review
        return "PENDING_AUDIT"


async def memory_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Memory & Contradiction Agent:
    1. Self-document guard: ignores matches from the same document.
    2. Parameter-diff contradiction detection:
       - POLICY_REVERSAL: same subject, numerically different standard.
       - IDENTICAL_PROVISION: same subject, same parameter (suppressed from alerts).
       - PENDING_AUDIT: qualitative change requiring human review.
    3. Indexes only OPERATIVE clauses into the vector store.
    """
    logger.info("Executing Memory & Contradiction Agent...")
    doc_id = state.get("document_id", "doc_test")
    classified = state.get("classified_clauses", [])   # OPERATIVE clauses only
    contradictions: List[Dict[str, Any]] = []
    seen = set()

    total_attempted = 0
    param_succeeded = 0
    param_failed = 0
    suppressed_identical = 0

    for clause in classified:
        ward = clause.get("ward")
        similar = vector_store.search_similar_clauses(clause.get("text", ""), ward=ward, limit=5)

        for s in similar:
            prior_doc_id = s.get("metadata", {}).get("doc_id", "")
            prior_text = s.get("text", "").strip()
            similarity = s.get("similarity", 0.0)

            total_attempted += 1
            cur_p = _extract_numeric_params(clause.get("text", ""))
            pri_p = _extract_numeric_params(prior_text)
            if cur_p is not None and pri_p is not None:
                param_succeeded += 1
            else:
                param_failed += 1

            contradiction_type = _classify_contradiction(
                current_text=clause.get("text", ""),
                prior_text=prior_text,
                similarity=similarity,
                doc_id=doc_id,
                prior_doc_id=prior_doc_id
            )

            if contradiction_type in ("IRRELEVANT", "IDENTICAL_PROVISION"):
                if contradiction_type == "IDENTICAL_PROVISION":
                    suppressed_identical += 1
                continue  # Suppress identical provisions and irrelevant matches

            dedup_key = (prior_doc_id, ward, prior_text[:60])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            is_reversal = (contradiction_type == "POLICY_REVERSAL")
            rec = ContradictionRecord(
                claim_id=clause.get("id"),
                ward=ward,
                prior_doc_id=prior_doc_id,
                prior_clause_text=prior_text,
                similarity_score=similarity,
                contradiction_flag=is_reversal,
                notes=(
                    f"[{contradiction_type}] Found related historical clause in document {prior_doc_id}. "
                    f"Similarity: {similarity:.2f}"
                )
            )
            contradictions.append(rec.model_dump())

    reversal_count = sum(1 for c in contradictions if c.get("contradiction_flag"))
    pending_count = sum(1 for c in contradictions if not c.get("contradiction_flag"))

    logger.info(
        f"[Memory Diff Diagnostics] {total_attempted} comparisons attempted | "
        f"{param_succeeded} params extracted, {param_failed} qualitative | "
        f"{reversal_count} POLICY_REVERSAL(s), {suppressed_identical} IDENTICAL (suppressed), {pending_count} PENDING_AUDIT(s)"
    )

    # Index only OPERATIVE clauses into vector store (not definitions/layout)
    if classified:
        vector_store.upsert_clauses(classified, doc_id=doc_id)

    return {"contradictions": contradictions}
