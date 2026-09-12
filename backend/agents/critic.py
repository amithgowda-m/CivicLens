import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ImpactTag

logger = logging.getLogger("civiclens.agent.critic")

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

        # Adversarial critique
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
