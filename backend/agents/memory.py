import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ContradictionRecord
from backend.vector_store import vector_store

logger = logging.getLogger("civiclens.agent.memory")

async def memory_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Memory & Contradiction Agent: Indexes clauses into the vector store keyed
    by ward and typology, queries prior historical clauses for that ward,
    and flags policy contradictions.
    """
    logger.info("Executing Memory & Contradiction Agent...")
    doc_id = state.get("document_id", "doc_test")
    classified = state.get("classified_clauses", [])
    contradictions: List[Dict[str, Any]] = []

    seen_contradictions = set()
    for clause in classified:
        ward = clause.get("ward")
        similar = vector_store.search_similar_clauses(clause.get("text", ""), ward=ward, limit=3)
        for s in similar:
            prior_id = s.get("metadata", {}).get("doc_id")
            prior_text = s.get("text", "").strip()
            if prior_id != doc_id and s.get("similarity", 0) > 0.70:
                dedup_key = (prior_id, ward, prior_text[:60])
                if dedup_key in seen_contradictions:
                    continue
                seen_contradictions.add(dedup_key)

                rec = ContradictionRecord(
                    claim_id=clause.get("id"),
                    ward=ward,
                    prior_doc_id=prior_id,
                    prior_clause_text=prior_text,
                    similarity_score=s.get("similarity"),
                    contradiction_flag=True,
                    notes=f"Found related historical clause in document {prior_id}"
                )
                contradictions.append(rec.model_dump())

    # 2. Upsert current clauses into vector store
    vector_store.upsert_clauses(classified, doc_id=doc_id)

    return {
        "contradictions": contradictions
    }

