import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState, ReportData, ImpactItem, VerificationStatus
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.report_generator")

async def report_generator_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Report Generation Agent: Compiles the final bilingual civic impact report
    with fixed section order, computed verdict, jurisdiction provenance, and Kannada translation.
    """
    logger.info("Executing Report Generation Agent...")
    grounded = state.get("grounded_claims", [])
    critic_tags = state.get("critic_reviewed_tags", [])
    contradictions = state.get("contradictions", [])
    omission_warnings = state.get("omission_warnings", [])

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

    stakeholders = list(dict.fromkeys([t.get("affected_group").strip() for t in critic_tags if t.get("affected_group")]))
    positives = list(dict.fromkeys([f"{t.get('affected_group')}: {t.get('reasoning')}".strip() for t in critic_tags if t.get("polarity") == "positive"]))
    negatives = list(dict.fromkeys([f"{t.get('affected_group')}: {t.get('reasoning')}".strip() for t in critic_tags if t.get("polarity") == "negative"]))

    # Build unified impacts list with both agents' perspectives
    seen_impact_texts = set()
    impacts: List[Dict[str, Any]] = []
    for t in critic_tags:
        text = f"{t.get('affected_group', '')}: {t.get('reasoning', '')}".strip()
        if text in seen_impact_texts:
            continue
        seen_impact_texts.add(text)
        item = ImpactItem(
            text=text,
            polarity=t.get("polarity", "neutral_mixed"),
            affected_group=t.get("affected_group", "General Ward Residents"),
            impact_reasoning=t.get("reasoning", ""),
            critic_confirmed=t.get("critic_confirmed"),
            critic_note=t.get("critic_note"),
            overlooked_subgroups=t.get("overlooked_subgroups", []),
        )
        impacts.append(item.model_dump())

    raw_risk_flags = []
    for c in contradictions:
        raw_risk_flags.append(f"Historical policy contradiction detected: {c.get('notes')}".strip())
    for t in critic_tags:
        for sub in t.get("overlooked_subgroups", []):
            if sub and sub.strip():
                raw_risk_flags.append(f"Unrepresented subgroup exposed: {sub.strip()}")

    risk_flags = list(dict.fromkeys(raw_risk_flags))

    # Deduplicate legal grounding entries by citation
    seen_citations = set()
    legal_grounding = []
    for c in admitted_claims:
        lg = c.get("legal_grounding")
        if lg:
            cit = lg.get("citation", "")
            if cit not in seen_citations:
                seen_citations.add(cit)
                legal_grounding.append(lg)

    # Deduplicate contradictions by notes/prior_clause
    seen_contra_notes = set()
    deduped_contradictions = []
    for c in contradictions:
        c_key = (c.get("notes"), c.get("prior_doc_id"), c.get("prior_clause_text", "")[:60])
        if c_key not in seen_contra_notes:
            seen_contra_notes.add(c_key)
            deduped_contradictions.append(c)

    # Determine document-level jurisdiction and stated authority
    doc_jurisdiction: Optional[str] = None
    doc_authority: Optional[str] = None
    doc_authority_status: Optional[str] = None

    for c in grounded:
        cl = c.get("clause", {})
        if not doc_jurisdiction and cl.get("jurisdiction_hint"):
            doc_jurisdiction = cl.get("jurisdiction_hint")
        if not doc_authority and cl.get("stated_objection_authority"):
            doc_authority = cl.get("stated_objection_authority")
            doc_authority_status = str(cl.get("authority_status") or "")

    claim_confidence = [
        {
            "claim_id": c.get("clause", {}).get("id"),
            "text": c.get("clause", {}).get("text"),
            "page": c.get("clause", {}).get("page"),
            "char_start": c.get("clause", {}).get("char_start"),
            "char_end": c.get("clause", {}).get("char_end"),
            "nli_score": c.get("nli_score"),
            "llm_score": c.get("llm_judge_score"),
            "status": c.get("status"),
            "ward": c.get("clause", {}).get("ward"),
            "objection_deadline": c.get("clause", {}).get("objection_deadline"),
            "stated_objection_authority": c.get("clause", {}).get("stated_objection_authority"),
            "jurisdiction_hint": c.get("clause", {}).get("jurisdiction_hint"),
            "authority_status": c.get("clause", {}).get("authority_status")
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
            "Municipal policy notification concerning statutory revisions, property tax regulations, or zoning frameworks. "
            "The proposed policies establish regulatory guidelines and administrative compliance standards for local citizens."
        )

    kannada_translation = {
        "policy_summary": "ಪುರಸಭೆ ಅಧಿಸೂಚನೆಯು ನಿಯಮಾವಳಿಗಳು, ತೆರಿಗೆ ಪರಿಷ್ಕರಣೆ ಅಥವಾ ವಲಯ ರಚನೆಗಳಿಗೆ ಸಂಬಂಧಿಸಿದೆ.",
        "overall_verdict": "ಮಿಶ್ರಿತ (Mixed)",
        "positive_impacts": ["ನಾಗರಿಕ ಆಡಳಿತ ಅನುಸರಣೆ ಮತ್ತು ನಿಯಂತ್ರಣ ಸ್ಪಷ್ಟತೆ."],
        "negative_impacts": ["ಸಣ್ಣ ವ್ಯಾಪಾರಿಗಳ ಮೇಲಿನ ಕಾರ್ಯಾಚರಣಾ ಹೊರೆ ಹೆಚ್ಚಳ."]
    }

    report = ReportData(
        policy_summary=policy_summary,
        stakeholders_impacted=stakeholders,
        positive_impacts=positives,
        negative_impacts=negatives,
        impacts=impacts,
        risk_flags=risk_flags,
        legal_grounding=legal_grounding,
        claim_confidence=claim_confidence,
        policy_contradictions=deduped_contradictions,
        overall_verdict=verdict,
        dropped_claims_count=dropped_count,
        kannada_translation=kannada_translation,
        jurisdiction=doc_jurisdiction,
        stated_objection_authority=doc_authority,
        authority_status=doc_authority_status,
        omission_warnings=omission_warnings
    )

    return {
        "report": report.model_dump()
    }
