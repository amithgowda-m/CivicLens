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
    affected stakeholder groups. Uses batch LLM evaluation for efficiency.
    """
    logger.info("Executing Impact Analysis Agent...")
    grounded_claims = state.get("grounded_claims", [])
    admitted = [
        item for item in grounded_claims
        if item.get("status") != VerificationStatus.REJECTED_PRUNED.value
    ]
    if not admitted:
        return {"impact_tags": []}

    batch_items = [
        {
            "claim_id": item.get("clause", {}).get("id", f"cl_{i}"),
            "text": item.get("clause", {}).get("text", "")[:250],
            "typology": item.get("clause", {}).get("typology", "other"),
            "ward": item.get("clause", {}).get("ward", "150")
        }
        for i, item in enumerate(admitted)
    ]

    batch_results: Dict[str, Dict[str, Any]] = {}
    try:
        prompt = (
            "Analyze the civic/economic impact for each of the following municipal clauses:\n"
            f"{json.dumps(batch_items, indent=2)}\n\n"
            "Return JSON: {\"impacts\": [{\"claim_id\": \"...\", \"polarity\": \"positive\" | \"negative\" | \"neutral_mixed\", \"affected_group\": \"...\", \"reasoning\": \"...\"}]}"
        )
        res_str = await llm_client.generate_text(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
        res_json = json.loads(res_str)
        for imp in res_json.get("impacts", []):
            cid = imp.get("claim_id")
            if cid:
                batch_results[cid] = imp
    except Exception as e:
        logger.warning(f"Batch LLM Impact Tagging failed ({e}), applying rule fallbacks.")

    impact_tags: List[Dict[str, Any]] = []
    for item in admitted:
        clause = item.get("clause", {})
        cid = clause.get("id", "cl_unknown")
        typology = clause.get("typology", "other")

        if cid in batch_results:
            b_imp = batch_results[cid]
            tag = ImpactTag(
                claim_id=cid,
                polarity=b_imp.get("polarity", "neutral_mixed"),
                affected_group=b_imp.get("affected_group", "General Ward Residents"),
                reasoning=b_imp.get("reasoning", "Municipal policy update affecting local ward governance.")
            )
        else:
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

