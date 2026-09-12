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

    # 1. Search prior clauses for ward
    for clause in classified:
        ward = clause.get("ward")
        similar = vector_store.search_similar_clauses(clause.get("text", ""), ward=ward, limit=3)
        for s in similar:
            if s.get("metadata", {}).get("doc_id") != doc_id and s.get("similarity", 0) > 0.70:
                rec = ContradictionRecord(
                    claim_id=clause.get("id"),
                    ward=ward,
                    prior_doc_id=s.get("metadata", {}).get("doc_id"),
                    prior_clause_text=s.get("text"),
                    similarity_score=s.get("similarity"),
                    contradiction_flag=True,
                    notes=f"Found related historical clause in document {s.get('metadata', {}).get('doc_id')}"
                )
                contradictions.append(rec.model_dump())

    # 2. Upsert current clauses into vector store
    vector_store.upsert_clauses(classified, doc_id=doc_id)

    return {
        "contradictions": contradictions
    }
