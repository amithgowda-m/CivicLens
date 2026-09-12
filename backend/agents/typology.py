import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, TypologyCategory

logger = logging.getLogger("civiclens.agent.typology")

def classify_clause_typology(text: str) -> TypologyCategory:
    """Classifies a clause text into standard civic typologies."""
    t = text.lower()
    if any(k in t for k in ["tax", "cess", "rate", "valuation", "assessment", "penalty", "betterment", "fee", "duty"]):
        return TypologyCategory.TAX
    elif any(k in t for k in ["setback", "zoning", "land use", "far", "floor area", "building height", "plot", "coverage", "commercial"]):
        return TypologyCategory.LAND_USE
    elif any(k in t for k in ["road", "drainage", "water", "sewer", "stormwater", "pipeline", "street", "pavement", "culvert", "metro"]):
        return TypologyCategory.INFRASTRUCTURE
    elif any(k in t for k in ["green", "waste", "pollution", "tree", "lake", "buffer", "park", "segregation", "garbage", "emission"]):
        return TypologyCategory.ENVIRONMENTAL
    elif any(k in t for k in ["budget", "allocation", "grant", "expenditure", "fund", "crore", "lakh"]):
        return TypologyCategory.BUDGET
    else:
        return TypologyCategory.OTHER

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
        cat = classify_clause_typology(c_copy.get("text", ""))
        c_copy["typology"] = cat.value
        classified.append(c_copy)

    return {
        "classified_clauses": classified
    }
