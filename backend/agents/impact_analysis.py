import logging
from typing import Dict, Any, List
import json
from backend.schemas import CivicLensState, ImpactTag, VerificationStatus
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.impact_analysis")

SYSTEM_PROMPT = """You are a citizen impact analysis agent for municipal and civic policy documents.
Given a verified municipal document clause, determine:
1. polarity: "positive", "negative", or "neutral_mixed"
   CRITICAL CIVIC BALANCE INSTRUCTIONS:
   - Procedural safeguards (e.g. mandatory public notice periods, 15-day/30-day objection submission windows, public hearing rights, citizen representation, appeal mechanisms, environmental buffer protections) safeguard residents from unilateral or arbitrary executive action; classify these procedural protections as "positive".
   - Unilateral burdens (e.g. sudden tax hikes, fee increases, reduced developable area without compensation, shortened appeal windows, retroactive penalties) are "negative" for affected taxpayers or businesses.
   - Dual-effect clauses (e.g. increased building setbacks that widen pedestrian footpaths but restrict commercial floor space) are "neutral_mixed".
2. affected_group: specific, concrete stakeholder group affected (e.g. "Ward residents submitting objections", "Adjacent residential property owners", "Small commercial shop tenants", "Pedestrian commuters"). Never use vague generic filler.
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
            raw_text = clause.get("text", "").strip()
            short_desc = (raw_text[:70] + "...") if len(raw_text) > 70 else raw_text
            c_text = raw_text.lower()

            if clause.get("objection_deadline") or any(w in c_text for w in ("objection", "suggestion", "notice", "hearing", "representation", "safeguard")):
                tag = ImpactTag(
                    claim_id=cid,
                    polarity="positive",
                    affected_group="Ward residents and concerned citizens",
                    reasoning=f"Document establishes procedural safeguards and consultation provisions for: {short_desc}"
                )
            elif typology == "land_use":
                tag = ImpactTag(
                    claim_id=cid,
                    polarity="neutral_mixed",
                    affected_group="Property owners, developers, and neighborhood residents",
                    reasoning=f"Spatial planning and zoning standard governing '{short_desc}' defines development boundaries and land use compliance."
                )
            elif typology == "tax":
                tag = ImpactTag(
                    claim_id=cid,
                    polarity="negative",
                    affected_group="Assessed property owners and commercial tenants",
                    reasoning=f"Fiscal assessment or revenue regulation regarding '{short_desc}' alters municipal compliance costs."
                )
            elif any(w in c_text for w in ("environment", "buffer", "green", "lake", "tree")):
                tag = ImpactTag(
                    claim_id=cid,
                    polarity="positive",
                    affected_group="Local community and environmental stakeholders",
                    reasoning=f"Environmental preservation standards regarding '{short_desc}' protect civic commons."
                )
            else:
                tag = ImpactTag(
                    claim_id=cid,
                    polarity="positive",
                    affected_group="General citizens and municipal administration",
                    reasoning=f"Administrative regulatory provision established: {short_desc}"
                )


        impact_tags.append(tag.model_dump())

    return {
        "impact_tags": impact_tags
    }

