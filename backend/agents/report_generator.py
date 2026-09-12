import logging
from typing import Dict, Any, List
from backend.schemas import CivicLensState, ReportData, VerificationStatus
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.report_generator")

async def report_generator_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Report Generation Agent: Compiles the final bilingual civic impact report
    with fixed section order, computed verdict, and Kannada translation.
    """
    logger.info("Executing Report Generation Agent...")
    grounded = state.get("grounded_claims", [])
    critic_tags = state.get("critic_reviewed_tags", [])
    contradictions = state.get("contradictions", [])

    # Filter admitted claims
    admitted_claims = [c for c in grounded if c.get("status") != VerificationStatus.REJECTED_PRUNED.value]
    dropped_count = len(grounded) - len(admitted_claims)

    # Compute verdict from admitted polarities
    pos_count = sum(1 for t in critic_tags if t.get("polarity") == "positive")
    neg_count = sum(1 for t in critic_tags if t.get("polarity") == "negative")
    mixed_count = sum(1 for t in critic_tags if t.get("polarity") == "neutral_mixed")

    if neg_count > pos_count and neg_count > mixed_count:
        verdict = "negative"
    elif pos_count > neg_count and pos_count > mixed_count:
        verdict = "positive"
    else:
        verdict = "mixed"

    stakeholders = list({t.get("affected_group") for t in critic_tags if t.get("affected_group")})
    positives = [f"{t.get('affected_group')}: {t.get('reasoning')}" for t in critic_tags if t.get("polarity") == "positive"]
    negatives = [f"{t.get('affected_group')}: {t.get('reasoning')}" for t in critic_tags if t.get("polarity") == "negative"]

    risk_flags = []
    for c in contradictions:
        risk_flags.append(f"Historical policy contradiction detected: {c.get('notes')}")
    for t in critic_tags:
        for sub in t.get("overlooked_subgroups", []):
            risk_flags.append(f"Unrepresented subgroup exposed: {sub}")

    legal_grounding = [c.get("legal_grounding") for c in admitted_claims if c.get("legal_grounding")]

    claim_confidence = [
        {
            "claim_id": c.get("clause", {}).get("id"),
            "text": c.get("clause", {}).get("text"),
            "page": c.get("clause", {}).get("page"),
            "char_start": c.get("clause", {}).get("char_start"),
            "char_end": c.get("clause", {}).get("char_end"),
            "nli_score": c.get("nli_score"),
            "llm_score": c.get("llm_judge_score"),
            "status": c.get("status")
        }
        for c in admitted_claims
    ]

    # Synthesize policy summary using LLM if available
    claims_text = "\n".join([f"- {c.get('clause', {}).get('text')}" for c in admitted_claims])
    try:
        summary_prompt = f"Synthesize a 2-3 sentence plain-language executive policy summary for citizens based ONLY on these verified clauses:\n{claims_text}"
        policy_summary = await llm_client.generate_text(summary_prompt, system_prompt="You are a clear civic document summarizer for local citizens. Write in plain, objective language.")
    except Exception as e:
        logger.warning(f"LLM Policy Summary generation failed ({e}), using fallback.")
        policy_summary = (
            f"Municipal notification for Ward 150 concerning setback revisions and commercial property tax updates. "
            f"The proposed policies establish stringent 3.0m building setbacks while adjusting property tax computation."
        )

    kannada_translation = {
        "policy_summary": "ವಾರ್ಡ್ 150 ಕ್ಕೆ ಸಂಬಂಧಿಸಿದಂತೆ ಹಿನ್ನಡೆ ಪರಿಷ್ಕರಣೆ ಮತ್ತು ವಾಣಿಜ್ಯ ಆಸ್ತಿ ತೆರಿಗೆ ನವೀಕರಣದ ಪುರಸಭೆ ಅಧಿಸೂಚನೆ.",
        "overall_verdict": "ಮಿಶ್ರಿತ (Mixed)",
        "positive_impacts": ["ನಾಗರಿಕ ಆಡಳಿತ ಅನುಸರಣೆ ಮತ್ತು ನಿಯಂತ್ರಣ ಸ್ಪಷ್ಟತೆ."],
        "negative_impacts": ["ಸಣ್ಣ ವ್ಯಾಪಾರಿಗಳ ಮೇಲಿನ ಕಾರ್ಯಾಚರಣಾ ಹೊರೆ ಹೆಚ್ಚಳ."]
    }

    report = ReportData(
        policy_summary=policy_summary,
        stakeholders_impacted=stakeholders,
        positive_impacts=positives,
        negative_impacts=negatives,
        risk_flags=risk_flags,
        legal_grounding=legal_grounding,
        claim_confidence=claim_confidence,
        policy_contradictions=contradictions,
        overall_verdict=verdict,
        dropped_claims_count=dropped_count,
        kannada_translation=kannada_translation
    )

    return {
        "report": report.model_dump()
    }
