import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ImpactTag, VerificationStatus

logger = logging.getLogger("civiclens.agent.impact_analysis")

async def impact_analysis_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Impact Analysis Agent: Evaluates verified and grounded claims, determining
    concrete civic impact polarity (positive/negative/neutral_mixed) and specific
    affected stakeholder groups.
    """
    logger.info("Executing Impact Analysis Agent...")
    grounded_claims = state.get("grounded_claims", [])
    impact_tags: List[Dict[str, Any]] = []

    for item in grounded_claims:
        # Only process admitted claims
        if item.get("status") == VerificationStatus.REJECTED_PRUNED.value:
            continue

        clause = item.get("clause", {})
        cid = clause.get("id", "cl_unknown")
        text = clause.get("text", "")
        typology = clause.get("typology", "other")

        # Stub heuristic/LLM tagging
        if typology == "land_use":
            tag = ImpactTag(
                claim_id=cid,
                polarity="neutral_mixed",
                affected_group="Commercial property developers and pedestrian commuters",
                reasoning="Increased setback improves pedestrian walkway width but reduces developable commercial floor area."
            )
        elif typology == "tax":
            tag = ImpactTag(
                claim_id=cid,
                polarity="negative",
                affected_group="Small commercial business owners and shop tenants",
                reasoning="Immediate increase in operational overhead without guaranteed improvement in local municipal services."
            )
        else:
            tag = ImpactTag(
                claim_id=cid,
                polarity="positive",
                affected_group="General ward residents",
                reasoning="Enhanced civic administrative compliance and regulatory clarity."
            )

        impact_tags.append(tag.model_dump())

    return {
        "impact_tags": impact_tags
    }
