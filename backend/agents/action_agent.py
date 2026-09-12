import logging
from typing import Dict, Any, List, Optional
from backend.schemas import ActionArtifact, ReportData, VerificationStatus
from backend.llm_client import llm_client
from backend.jurisdiction import resolve_addressee, load_registry

logger = logging.getLogger("civiclens.agent.action")


def _build_compliance_guide_prompt(
    report: ReportData,
    authority: str,
    jurisdiction_name: str
) -> str:
    """Constructs prompt for LLM to draft a citizen compliance & rights guide for enacted regulations/master plans."""
    doc_title = report.document_title or "Municipal Planning & Zonal Regulation"
    admitted = [
        c for c in report.claim_confidence
        if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
    ]
    claim_items = []
    for c in admitted[:8]:
        text = c.get("text") or c.get("clause_text", "")
        page = c.get("page", "?")
        if text:
            claim_items.append(f'- (Page {page}) "{text[:250]}"')
    claims_block = "\n".join(claim_items) if claim_items else "- (Refer to document regulations)"

    legal_refs = [
        f"Section {g.matched_statute_section} of {g.statute_name}"
        for g in report.legal_grounding if g.matched_statute_section and g.statute_name
    ]
    legal_refs_str = ", ".join(legal_refs) if legal_refs else "Applicable municipal planning framework"

    prompt = f"""You are a senior civic legal advisor in {jurisdiction_name}.

Draft a comprehensive "Citizen Compliance & Rights Guide" based on the following verified enacted municipal regulation.
This is an officially enacted statutory document (currently in force), NOT a draft proposal inviting objections.

=== DOCUMENT DETAILS ===
Title: {doc_title}
Legal Status: Enacted Law / Gazetted Master Plan
Enforcing Authority: {authority}
Statutory Basis: {legal_refs_str}

=== VERIFIED OPERATIVE CLAUSES (from document) ===
{claims_block}

=== INSTRUCTIONS FOR GUIDE ===
Draft a clear, practical, citizen-facing guide with the following sections:
1. REGULATORY OVERVIEW: What this regulation governs and its legal binding nature.
2. CITIZEN RIGHTS & COMPLIANCE RULES: Plain-language breakdown of key standards, definitions, and building/zoning rules based on the verified clauses above.
3. PRE-EXISTING USES & SAFEGUARDS: Protections for existing lawful structures and non-conforming uses.
4. PERMITTING & APPROVAL PROCESS: How citizens, architects, and plot owners apply for clearances with {authority}.
5. APPEALS & GRIEVANCE REDRESSAL: Legal rights of appeal against arbitrary enforcement or denial of permissions.

Tone: Authoritative, practical, and protective of citizen rights.
Do NOT mention any objection submission deadline, as this regulation is already enacted and binding.
Output ONLY the guide text, formatted with clear markdown headings."""

    return prompt


def _build_objection_prompt(
    report: ReportData,
    recipient: str,
    jurisdiction_name: str,
    selected_grievances: Optional[List[str]] = None,
    deadline: Optional[str] = None
) -> str:
    """Constructs prompt for LLM to draft a formal objection letter for draft proposals."""
    grievance_list = selected_grievances if selected_grievances else report.negative_impacts
    negative_points = "\n".join(f"- {p}" for p in grievance_list) or "- General administrative concerns."
    risk_points = "\n".join(f"- {r}" for r in report.risk_flags) or "- No explicit risk flags."

    legal_refs = [
        f"Section {g.matched_statute_section} of {g.statute_name}"
        for g in report.legal_grounding if g.matched_statute_section and g.statute_name
    ]
    legal_refs_str = ", ".join(legal_refs) if legal_refs else f"applicable {jurisdiction_name} municipal statutes"

    stakeholders = ", ".join(report.stakeholders_impacted) if report.stakeholders_impacted else "affected citizens"

    admitted_claims = [
        c for c in report.claim_confidence
        if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
    ]
    claim_texts = []
    for c in admitted_claims[:5]:
        text = c.get("text") or c.get("clause_text", "")
        page = c.get("page", "?")
        if text:
            claim_texts.append(f'- (Page {page}) "{text[:200]}"')
    claims_block = "\n".join(claim_texts) if claim_texts else "- (See source notice)"

    deadline_str = f"Deadline: {deadline}" if deadline else "Submission period: Prescribed public consultation window"

    prompt = f"""You are a legal drafting assistant for civic advocacy in {jurisdiction_name}.

Draft a formal objection letter to municipal authorities based on the following verified analysis of a draft municipal document.
The letter must cite the exact legal statutes, reference specific source claims, and articulate remedies requested.

=== REPORT SUMMARY ===
Document: {report.document_title or 'Draft Municipal Notice'}
Overall Verdict: {report.overall_verdict.upper()}
Policy Summary: {report.policy_summary}

=== AFFECTED STAKEHOLDERS ===
{stakeholders}

=== SPECIFIC OBJECTIONS / IMPACTS ===
{negative_points}

=== RISK FLAGS ===
{risk_points}

=== VERIFIED SOURCE CLAIMS ===
{claims_block}

=== LEGAL CITATIONS ===
{legal_refs_str}

=== DRAFT INSTRUCTIONS ===
- Address To: {recipient}
- Format: Formal representation / objection petition
- Body: 4-5 paragraphs covering notice reference, specific legal and procedural objections, impact on affected groups, requested relief/modifications, and request for personal hearing.
- {deadline_str}
- Closing: Signed as "Aggrieved Citizens and Resident Representatives"

Output ONLY the petition text."""

    return prompt


def _build_awareness_prompt(report: ReportData, jurisdiction_name: str) -> str:
    """Constructs prompt for LLM to draft a positive community awareness bulletin."""
    positive_points = "\n".join(f"- {p}" for p in report.positive_impacts) or "- Positive municipal development."
    stakeholders = ", ".join(report.stakeholders_impacted) if report.stakeholders_impacted else "community members"

    return f"""You are a civic communications officer in {jurisdiction_name}.

Draft a clear, engaging community awareness bulletin based on the verified civic policy below.

Document: {report.document_title or 'Municipal Notification'}
Summary: {report.policy_summary}
Key Benefits:
{positive_points}
Affected Community: {stakeholders}

Format as an informative community newsletter entry (3-4 paragraphs) with a call to action.
Output ONLY the bulletin text."""


async def generate_action_artifact(report: ReportData, selected_grievances: Optional[List[str]] = None) -> ActionArtifact:
    """
    Action Agent: Generates context-appropriate civic artifacts:
    - For Enacted Regulations / Master Plans -> Citizen Compliance & Rights Guide
    - For Draft Proposals / Objections -> Formal Objection Petition
    - For Positive Notices -> Community Awareness Bulletin
    """
    logger.info(f"Generating action artifact for doc category: {report.document_category}, verdict: {report.overall_verdict}")

    # Extract any explicit deadline from verified claims
    extracted_deadline: Optional[str] = None
    for c in report.claim_confidence:
        d = c.get("objection_deadline")
        if d and str(d).strip().lower() not in ("none", "null", ""):
            extracted_deadline = str(d).strip()
            break

    # Resolve recipient authority
    ward = next((c.get("ward") for c in report.claim_confidence if c.get("ward")), None)
    registry = load_registry()
    jurisdiction_slug = report.jurisdiction or "_default"
    j_conf = registry.get(jurisdiction_slug, registry["_default"])
    jurisdiction_name = j_conf.get("name", "Local Municipal Authority")

    if report.stated_objection_authority and report.authority_status == VerificationStatus.ADMITTED.value:
        recipient = report.stated_objection_authority
    else:
        recipient = resolve_addressee(jurisdiction_slug, ward=ward)

    cited_ids = [
        c.get("id", c.get("claim_id", ""))
        for c in report.claim_confidence
        if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
    ][:6]

    # Determine recommended action based on document legal status and category
    is_enacted = report.document_category == "enacted_regulation_master_plan" or report.document_legal_status == "gazetted_enacted_law"

    if is_enacted:
        action_type = "compliance_guide"
        prompt = _build_compliance_guide_prompt(report, authority=recipient, jurisdiction_name=jurisdiction_name)
        system = f"You are a municipal legal expert and civic compliance advisor in {jurisdiction_name}."
        target_deadline = "Enacted Statutory Regulation (In Force)"
    elif report.overall_verdict in ("negative", "mixed"):
        action_type = "objection_letter"
        prompt = _build_objection_prompt(
            report,
            recipient=recipient,
            jurisdiction_name=jurisdiction_name,
            selected_grievances=selected_grievances,
            deadline=extracted_deadline
        )
        system = f"You are a civic legal advocate drafting formal representations for {jurisdiction_name}."
        target_deadline = extracted_deadline
    else:
        action_type = "awareness_summary"
        prompt = _build_awareness_prompt(report, jurisdiction_name=jurisdiction_name)
        system = f"You are a civic communications officer in {jurisdiction_name}."
        target_deadline = None

    try:
        content = await llm_client.generate_text(
            prompt=prompt,
            system_prompt=system,
            json_mode=False
        )
        if not content or not content.strip():
            raise ValueError("LLM generated empty response")
        if action_type == "objection_letter" and "FORMAL OBJECTION" not in content.upper():
            content = f"FORMAL OBJECTION PETITION\n\n{content}"
        elif action_type == "awareness_summary" and "COMMUNITY CIVIC BULLETIN" not in content.upper():
            content = f"COMMUNITY CIVIC BULLETIN\n\n{content}"
        elif action_type == "compliance_guide" and "CITIZEN COMPLIANCE" not in content.upper():
            content = f"# CITIZEN COMPLIANCE & RIGHTS GUIDE\n\n{content}"
        logger.info(f"LLM generated {action_type} successfully ({len(content)} chars)")

    except Exception as e:
        logger.warning(f"LLM generation failed for action agent: {e}, using verified clause fallback")
        admitted = [
            c for c in report.claim_confidence
            if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
        ]
        doc_title = report.document_title or "Municipal Planning Document"

        if action_type == "compliance_guide":
            clauses_summary = "\n".join(
                f"- Page {c.get('page', '?')}: {c.get('text', '')[:180]}"
                for c in admitted[:6]
            )
            content = (
                f"# CITIZEN COMPLIANCE & RIGHTS GUIDE\n\n"
                f"**Document**: {doc_title}\n"
                f"**Status**: Enacted Statutory Law (Currently in Force)\n"
                f"**Implementing Authority**: {recipient}\n\n"
                f"## 1. Key Operative Provisions\n"
                f"The following standards have been verified directly from the gazetted document:\n\n"
                f"{clauses_summary}\n\n"
                f"## 2. Citizen Rights & Protections\n"
                f"- Existing lawful buildings and uses established prior to this notification remain protected.\n"
                f"- Property owners are entitled to written inspection notices prior to any enforcement action.\n"
                f"- Any adverse order may be appealed to the designated appellate authority under the governing municipal statute.\n"
            )
        elif action_type == "objection_letter":
            neg_items = "\n".join(f"- {p}" for p in report.negative_impacts[:4]) or "- Adverse civic impact on local residents."
            deadline_line = f"\nSubmission Deadline: {target_deadline}\n" if target_deadline else ""
            content = (
                f"FORMAL OBJECTION PETITION\n\n"
                f"To: {recipient}\n"
                f"Subject: Formal Representation & Objections regarding {doc_title}\n\n"
                f"Respected Authority,\n\n"
                f"We write with reference to the published notice for {doc_title}. "
                f"Our verified analysis of the operative clauses raises the following critical concerns:\n\n"
                f"{neg_items}\n\n"
                f"We formally request a public consultation meeting and personal hearing to review these objections."
                f"{deadline_line}\n"
                f"Sincerely,\nAggrieved Citizens and Resident Representatives"
            )
        else:
            pos_items = "\n".join(f"- {p}" for p in report.positive_impacts[:4]) or "- Policy improvements noted."
            content = (
                f"COMMUNITY CIVIC BULLETIN\n\n"
                f"**{doc_title}**\n\n"
                f"Summary: {report.policy_summary}\n\n"
                f"Key Highlights:\n{pos_items}\n\n"
                f"For further details, consult the public notice published by {recipient}."
            )

    return ActionArtifact(
        action_type=action_type,
        content=content.strip(),
        target_deadline=target_deadline,
        recipient_authority=recipient,
        cited_clauses=cited_ids if cited_ids else ["See report for source references"]
    )

