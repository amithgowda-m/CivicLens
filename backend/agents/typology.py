import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, TypologyCategory

logger = logging.getLogger("civiclens.agent.typology")

async def typology_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Typology Classifier: Tags each clause with an official civic typology:
    land_use, tax, infrastructure, environmental, budget, or other.
    """
    logger.info("Executing Typology Classifier Agent...")
    raw_clauses = state.get("raw_clauses", [])
    classified: List[Dict[str, Any]] = []

    for clause in raw_clauses:
        c_copy = dict(clause)
        text_lower = c_copy.get("text", "").lower()
        if "tax" in text_lower or "cess" in text_lower or "fee" in text_lower:
            c_copy["typology"] = TypologyCategory.TAX.value
        elif "setback" in text_lower or "zoning" in text_lower or "land" in text_lower:
            c_copy["typology"] = TypologyCategory.LAND_USE.value
        elif "road" in text_lower or "drainage" in text_lower or "water" in text_lower:
            c_copy["typology"] = TypologyCategory.INFRASTRUCTURE.value
        elif "green" in text_lower or "waste" in text_lower or "pollution" in text_lower:
            c_copy["typology"] = TypologyCategory.ENVIRONMENTAL.value
        elif "budget" in text_lower or "allocation" in text_lower:
            c_copy["typology"] = TypologyCategory.BUDGET.value
        else:
            c_copy["typology"] = TypologyCategory.OTHER.value
        classified.append(c_copy)

    return {
        "classified_clauses": classified
    }
