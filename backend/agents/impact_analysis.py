import logging
from typing import Dict, Any, List
import json
from backend.schemas import CivicLensState, ImpactTag, VerificationStatus
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.impact_analysis")

SYSTEM_PROMPT = """You are a citizen impact analysis agent for municipal document claims.
Given a verified municipal document clause, determine:
1. polarity: "positive", "negative", or "neutral_mixed"
2. affected_group: specific, concrete stakeholder group affected (e.g. "Adjacent residential property owners", "Small commercial shop tenants", "Pedestrian commuters", "Ward 150 residents"). Never use vague generic filler.
3. reasoning: 1-2 sentence concrete explanation of the civic or economic impact.

Return JSON format:
{
  "polarity": "positive" | "negative" | "neutral_mixed",
  "affected_group": "string",
  "reasoning": "string"
}"""

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
        # Only process admitted / non-rejected claims
        if item.get("status") == VerificationStatus.REJECTED_PRUNED.value:
            continue

        clause = item.get("clause", {})
        cid = clause.get("id", "cl_unknown")
        text = clause.get("text", "")
        typology = clause.get("typology", "other")
        ward = clause.get("ward", "150")

        # Call LLM for impact tag
        try:
            prompt = f"Clause Text: {text}\nClause Typology: {typology}\nAffected Ward: {ward}"
            res_str = await llm_client.generate_text(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
            res_json = json.loads(res_str)
            tag = ImpactTag(
                claim_id=cid,
                polarity=res_json.get("polarity", "neutral_mixed"),
                affected_group=res_json.get("affected_group", "General Ward Residents"),
                reasoning=res_json.get("reasoning", "Municipal policy update affecting local ward governance.")
            )
        except Exception as e:
            logger.warning(f"LLM Impact Tagging failed ({e}), applying fallback rules.")
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

