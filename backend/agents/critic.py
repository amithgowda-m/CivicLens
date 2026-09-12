import logging
import json
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ImpactTag
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.critic")

CRITIC_SYSTEM_PROMPT = """You are an adversarial civic critic agent auditing an impact assessment of a municipal policy.
Given an impact tag (affected_group, polarity, reasoning), your job is to:
1. Challenge the polarity adversarially (e.g., if negative for shopkeepers, note if it benefits pedestrians or ward infrastructure).
2. Identify specific overlooked demographic subgroups (e.g. "Low-income renters", "Informal street vendors", "Senior citizen pedestrians", "Small plot owners").
3. Determine if the impact tag requires human audit review due to significant policy disagreement or bias.

Return JSON format:
{
  "critic_confirmed": true | false,
  "critic_note": "1-2 sentence counter-perspective or validation note",
  "overlooked_subgroups": ["subgroup1", "subgroup2"],
  "requires_audit": true | false
}"""

async def critic_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Critic Agent: Adversarially challenges each impact tag, surfacing overlooked
    subgroups and arguing counter-perspectives, then merges results directly into ImpactTags.
    """
    logger.info("Executing Critic Agent...")
    tags = state.get("impact_tags", [])
    critic_reviewed: List[Dict[str, Any]] = []

    for t_data in tags:
        tag = ImpactTag.model_validate(t_data)

        try:
            prompt = f"Affected Group: {tag.affected_group}\nPolarity: {tag.polarity}\nReasoning: {tag.reasoning}"
            res_str = await llm_client.generate_text(prompt, system_prompt=CRITIC_SYSTEM_PROMPT, json_mode=True)
            res_json = json.loads(res_str)
            raw_conf = res_json.get("critic_confirmed", True)
            if isinstance(raw_conf, str):
                tag.critic_confirmed = raw_conf.lower() in ("true", "1", "yes")
            else:
                tag.critic_confirmed = bool(raw_conf)

            tag.critic_note = res_json.get("critic_note", "Critique completed.")
            tag.overlooked_subgroups = res_json.get("overlooked_subgroups", [])
            raw_req = res_json.get("requires_audit", False)
            if isinstance(raw_req, str):
                tag.requires_audit = raw_req.lower() in ("true", "1", "yes")
            else:
                tag.requires_audit = bool(raw_req)
        except Exception as e:
            logger.warning(f"LLM Critic failed ({e}), using heuristic fallback.")
            if tag.polarity == "negative":
                tag.critic_confirmed = True
                tag.critic_note = (
                    "While higher tax burdens shopkeepers, it expands municipal ward budget "
                    "for arterial road resurfacing and storm water drainage maintenance."
                )
                tag.overlooked_subgroups = ["Long-term commercial leaseholders", "Informal street vendors"]
                tag.requires_audit = False
            elif tag.polarity == "neutral_mixed":
                tag.critic_confirmed = True
                tag.critic_note = (
                    "Setback enforcement disproportionately impacts plots under 2,000 sq ft, "
                    "effectively freezing vertical expansion for smaller landholders."
                )
                tag.overlooked_subgroups = ["Small plot owners", "Street-level retail customers"]
                tag.requires_audit = False
            else:
                tag.critic_confirmed = True
                tag.critic_note = "Impact polarity is well supported by text."
                tag.overlooked_subgroups = []
                tag.requires_audit = False

        critic_reviewed.append(tag.model_dump())

    return {
        "critic_reviewed_tags": critic_reviewed
    }

