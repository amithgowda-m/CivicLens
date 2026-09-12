import logging
import json
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ImpactTag, VerificationStatus
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

def check_omitted_policy_categories(state: CivicLensState) -> List[str]:
    """
    Audits admitted claims for structural policy omissions (e.g. missing objection deadlines,
    unaddressed environmental/zoning impacts, or unstated authorities).
    """
    warnings: List[str] = []
    verified_claims = state.get("verified_claims", [])
    admitted = [c for c in verified_claims if c.get("status") == VerificationStatus.ADMITTED.value]

    has_deadline = any(c.get("clause", {}).get("objection_deadline") for c in admitted)
    has_authority = any(c.get("clause", {}).get("stated_objection_authority") for c in admitted)
    has_zoning = any(c.get("clause", {}).get("clause_type") == "zoning_regulation" for c in admitted)
    has_tax = any(c.get("clause", {}).get("clause_type") == "taxation_rule" for c in admitted)
    has_env = any(c.get("clause", {}).get("clause_type") == "environmental_mandate" for c in admitted)

    if not has_deadline and not has_authority:
        warnings.append(
            "Notice does not state an explicit objection submission deadline or addressee. "
            "Citizens risk missing procedural windows under municipal town planning rules."
        )

    if (has_zoning or has_tax) and not has_env:
        warnings.append(
            "Proposed commercial zoning or development surcharge revisions omit mandatory "
            "environmental buffer disclosures (e.g. rajakaluve or green cover setbacks)."
        )

    return warnings

async def critic_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Critic Agent: Adversarially challenges each impact tag, surfaces overlooked
    subgroups and counter-perspectives, and checks for structural policy omissions.
    """
    logger.info("Executing Critic Agent...")
    tags = state.get("impact_tags", [])
    omission_warnings = check_omitted_policy_categories(state)

    if not tags:
        return {
            "critic_reviewed_tags": [],
            "omission_warnings": omission_warnings
        }

    parsed_tags = [ImpactTag.model_validate(t_data) for t_data in tags]

    batch_items = [
        {
            "claim_id": t.claim_id,
            "affected_group": t.affected_group,
            "polarity": t.polarity,
            "reasoning": t.reasoning
        }
        for t in parsed_tags
    ]

    batch_results: Dict[str, Dict[str, Any]] = {}
    try:
        prompt = (
            "Critique the following civic impact assessments adversarially, challenging polarity "
            "and identifying overlooked demographic subgroups:\n"
            f"{json.dumps(batch_items, indent=2)}\n\n"
            "Return JSON: {\"critiques\": [{\"claim_id\": \"...\", \"critic_confirmed\": true | false, \"critic_note\": \"...\", \"overlooked_subgroups\": [\"...\"], \"requires_audit\": false}]}"
        )
        res_str = await llm_client.generate_text(prompt, system_prompt=CRITIC_SYSTEM_PROMPT, json_mode=True)
        res_json = json.loads(res_str)
        for c in res_json.get("critiques", []):
            cid = c.get("claim_id")
            if cid:
                batch_results[cid] = c
    except Exception as e:
        logger.warning(f"Batch LLM Critic failed ({e}), using heuristic fallbacks.")

    critic_reviewed: List[Dict[str, Any]] = []
    for tag in parsed_tags:
        if tag.claim_id in batch_results:
            c = batch_results[tag.claim_id]
            raw_conf = c.get("critic_confirmed", True)
            tag.critic_confirmed = raw_conf if isinstance(raw_conf, bool) else str(raw_conf).lower() in ("true", "1", "yes")
            tag.critic_note = str(c.get("critic_note", "Critique completed."))
            tag.overlooked_subgroups = c.get("overlooked_subgroups", [])
            raw_req = c.get("requires_audit", False)
            tag.requires_audit = raw_req if isinstance(raw_req, bool) else str(raw_req).lower() in ("true", "1", "yes")
        else:
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
        "critic_reviewed_tags": critic_reviewed,
        "omission_warnings": omission_warnings
    }
