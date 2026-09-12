import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState, ReportData, ImpactItem, VerificationStatus
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.report_generator")

CANONICAL_STAKEHOLDER_TAXONOMY = [
    ("Residential Property Owners & Tenants", ["resident", "residential", "plot owner", "homeowner", "tenant", "housing", "apartment", "neighborhood"]),
    ("Commercial Businesses & Shopkeepers", ["commercial", "shop", "retail", "business", "merchant", "vendor", "enterprise", "trade"]),
    ("Real Estate & Infrastructure Developers", ["developer", "builder", "construction", "real estate", "contractor", "infrastructure"]),
    ("Pedestrians, Commuters & Transit Users", ["pedestrian", "commuter", "transit", "walkway", "traffic", "cyclist", "motorist"]),
    ("Civic Authorities & Ward Committees", ["ward committee", "municipal", "corporation", "authority", "bda", "bbmp", "council", "officer"]),
    ("Vulnerable & Informal Demographics", ["low-income", "slum", "informal", "street vendor", "senior", "differently abled", "daily wage"]),
    ("Environmental & Community Groups", ["environment", "lake", "green cover", "buffer", "tree", "civic group", "citizen", "public interest"])
]

def synthesize_stakeholder_groups(raw_groups: List[str]) -> List[str]:
    """
    Synthesizes and clusters raw stakeholder descriptions into 5-7 clean canonical stakeholder groups.
    Prevents repetitive fragmentation (e.g. 20+ variations of developers or shopkeepers).
    """
    canonical_selected = set()
    unmatched = []

    for raw in raw_groups:
        r_low = raw.lower()
        matched = False
        for canon_name, keywords in CANONICAL_STAKEHOLDER_TAXONOMY:
            if any(kw in r_low for kw in keywords):
                canonical_selected.add(canon_name)
                matched = True
                break
        if not matched and len(raw.strip()) > 3:
            unmatched.append(raw.strip())

    ordered_groups = [canon for canon, _ in CANONICAL_STAKEHOLDER_TAXONOMY if canon in canonical_selected]
    for u in unmatched:
        if len(ordered_groups) >= 7:
            break
        if u not in ordered_groups:
            ordered_groups.append(u)

    if not ordered_groups:
        ordered_groups = ["General Ward Residents", "Commercial Property Owners", "Municipal Administration"]

    return ordered_groups[:7]

async def report_generator_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Report Generation Agent: Compiles the final civic impact report with fixed section order,
    computed verdict, consolidated contradiction intelligence, and jurisdiction provenance.
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

    raw_stakeholders = [t.get("affected_group").strip() for t in critic_tags if t.get("affected_group")]
    stakeholders = synthesize_stakeholder_groups(raw_stakeholders)

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

    # Thematic aggregation of contradictions by prior_doc_id
    grouped_contradictions: Dict[str, List[Dict[str, Any]]] = {}
    for c in contradictions:
        pid = c.get("prior_doc_id") or "historical_archive"
        grouped_contradictions.setdefault(pid, []).append(c)

    deduped_contradictions: List[Dict[str, Any]] = []
    for pid, group in grouped_contradictions.items():
        sample_clause = group[0].get("prior_clause_text", "").strip()
        count = len(group)
        ward_info = f" in Ward {group[0].get('ward')}" if group[0].get("ward") else ""
        short_sample = (sample_clause[:90] + "...") if len(sample_clause) > 90 else sample_clause
        aggregated_note = (
            f"Historical policy variance detected against document {pid[:8]}{ward_info} "
            f"across {count} related clause{'s' if count > 1 else ''} (e.g. \"{short_sample}\")."
        )
        deduped_contradictions.append({
            "claim_id": group[0].get("claim_id", ""),
            "ward": group[0].get("ward"),
            "prior_doc_id": pid,
            "prior_clause_text": sample_clause,
            "similarity_score": max((g.get("similarity_score") or 0.0) for g in group),
            "contradiction_flag": True,
            "notes": aggregated_note,
        })

    raw_risk_flags = []
    for c in deduped_contradictions:
        raw_risk_flags.append(c.get("notes", "").strip())
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
            if cit and cit not in seen_citations:
                seen_citations.add(cit)
                legal_grounding.append(lg)

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
    doc_title = state.get("document_title") or "Municipal Civic Document"
    try:
        summary_prompt = f"Synthesize a 2-3 sentence plain-language executive policy summary for citizens regarding {doc_title} based ONLY on these verified clauses:\n{claims_text}"
        policy_summary = await llm_client.generate_text(summary_prompt, system_prompt="You are a clear civic document summarizer for local citizens. Write in plain, objective language.")
    except Exception as e:
        logger.warning(f"LLM Policy Summary generation failed ({e}), summarizing strictly from verified clauses.")
        top_clauses = [
            c.get("clause", {}).get("text", "").strip()
            for c in admitted_claims[:3]
            if c.get("clause", {}).get("text")
        ]
        if top_clauses:
            joined = "; ".join(top_clauses)
            policy_summary = f"{doc_title}: Verified provisions specify that {joined}."
        else:
            policy_summary = f"{doc_title}: Administrative and regulatory provisions verified from document text."

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
        jurisdiction=doc_jurisdiction,
        stated_objection_authority=doc_authority,
        authority_status=doc_authority_status,
        omission_warnings=omission_warnings,
        document_title=state.get("document_title"),
        document_category=state.get("document_category", "general_civic_document"),
        document_legal_status=state.get("document_legal_status", "public_record"),
        action_type_recommended=state.get("action_type_recommended", "citizen_compliance_guide")
    )

    return {
        "report": report.model_dump()
    }

