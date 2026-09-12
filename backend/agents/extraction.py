import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, Clause

logger = logging.getLogger("civiclens.agent.extraction")

async def extraction_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Extraction Agent: Extracts structured clauses copying verbatim text from source.
    """
    logger.info("Executing Extraction Agent...")
    pages = state.get("pages_text", [])
    raw_clauses: List[Dict[str, Any]] = []

    # In Checkpoint 1 dummy/stub mode:
    # Produce structured Clause items with verbatim quotes and char offsets
    if pages:
        full_doc = "\n".join(pages)
        c1 = Clause(
            id="cl_01",
            text="Ward 150 (Bellandur) commercial setback requirement is revised to 3.0 meters.",
            page=1,
            char_start=60,
            char_end=138,
            clause_type="zoning_regulation",
            ward="150",
            objection_deadline="30 days",
            cited_legal_basis="Karnataka Town and Country Planning Act 1961 Section 14"
        )
        c2 = Clause(
            id="cl_02",
            text="Property tax on commercial establishments will be revised under Section 108A of KMC Act.",
            page=1,
            char_start=140,
            char_end=229,
            clause_type="taxation",
            ward="150",
            objection_deadline="30 days",
            cited_legal_basis="Karnataka Municipal Corporations Act Section 108A"
        )
        raw_clauses.extend([c1.model_dump(), c2.model_dump()])

    return {
        "raw_clauses": raw_clauses
    }
