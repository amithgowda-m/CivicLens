import logging
from typing import Dict, Any, List, Optional
from backend.schemas import ActionArtifact, ReportData, VerificationStatus
from backend.llm_client import llm_client
from backend.jurisdiction import resolve_addressee, load_registry

logger = logging.getLogger("civiclens.agent.action")


def _build_objection_prompt(
    report: ReportData,
    recipient: str,
    jurisdiction_name: str,
    selected_grievances: Optional[List[str]] = None
) -> str:
    """Constructs a detailed prompt for LLM to draft a formal objection letter from real report data."""

    grievance_list = selected_grievances if selected_grievances else report.negative_impacts
    negative_points = "\n".join(f"- {p}" for p in grievance_list) or "- General concerns raised."
    risk_points = "\n".join(f"- {r}" for r in report.risk_flags) or "- No explicit risk flags."

    # Gather legal groundings (statute citations)
    legal_refs = []
    for g in report.legal_grounding:
        if g.matched_statute_section:
            legal_refs.append(f"Section {g.matched_statute_section} of {g.statute_name or 'applicable statute'}")
    legal_refs_str = ", ".join(legal_refs) if legal_refs else f"applicable {jurisdiction_name} municipal statutes"

    # Gather affected stakeholders
    stakeholders = ", ".join(report.stakeholders_impacted) if report.stakeholders_impacted else "affected citizens"

    # Gather high-confidence admitted claims for grounding the letter
    admitted_claims = [
        c for c in report.claim_confidence
        if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
    ]
    claim_texts = []
    for c in admitted_claims[:5]:
        text = c.get("text") or c.get("clause_text", "")
        page = c.get("page", "?")
        if text:
            claim_texts.append(f'- (Page {page}) "{text[:200]}..."' if len(text) > 200 else f'- (Page {page}) "{text}"')
    claims_block = "\n".join(claim_texts) if claim_texts else "- (See attached document for source clauses)"

    # Extract deadline if available from any clause
    deadline = "Within 30 days of public notice publication"
    for c in report.claim_confidence:
        d = c.get("objection_deadline")
        if d:
            deadline = d
            break

    # Ward/locality
    ward_info = ""
    for c in report.claim_confidence:
        w = c.get("ward")
        if w:
            ward_info = f" (Ward: {w})"
            break

    prompt = f"""You are a legal drafting assistant for civic advocacy in {jurisdiction_name}.

Draft a formal objection letter to municipal authorities based on the following verified analysis of a municipal document.
The letter must be professional, cite the exact legal statutes provided, reference the specific source document claims,
and clearly state the citizen objections and remedies requested.

=== REPORT SUMMARY ===
Overall Verdict: {report.overall_verdict.upper()}
Policy Summary: {report.policy_summary}

=== AFFECTED STAKEHOLDERS ===
{stakeholders}{ward_info}

=== NEGATIVE IMPACTS IDENTIFIED ===
{negative_points}

=== RISK FLAGS ===
{risk_points}

=== VERIFIED SOURCE CLAIMS (verbatim from document) ===
{claims_block}

=== LEGAL BASIS ===
Citations: {legal_refs_str}
Dropped/unverified claims count: {report.dropped_claims_count}

=== DRAFT INSTRUCTIONS ===
- Address: {recipient}
- Subject line: Specific to the policy identified
- Format: Formal government letter format
- Body: 4-5 paragraphs covering: (1) Reference to the notice, (2) Specific objections with legal citations, (3) Impact on affected groups, (4) Remedy/relief requested, (5) Request for public consultation
- Deadline reference: {deadline}
- Closing: Signed as "Aggrieved Citizens and Residents Welfare Association"
- Do NOT use placeholder text like [Name] or [Date] — write it as a ready-to-use draft

Output ONLY the letter text, no preamble or explanation."""

    return prompt


def _build_awareness_prompt(report: ReportData, jurisdiction_name: str) -> str:
    """Constructs a prompt for LLM to draft a positive community awareness bulletin."""

    positive_points = "\n".join(f"- {p}" for p in report.positive_impacts) or "- Positive municipal development."
    stakeholders = ", ".join(report.stakeholders_impacted) if report.stakeholders_impacted else "community members"

    prompt = f"""You are a civic communications officer for a Resident Welfare Association in {jurisdiction_name}.

Draft a clear, engaging community awareness bulletin based on the following verified analysis of a municipal policy.
The bulletin should be easy for ordinary citizens to understand and encourage participation.

=== POLICY SUMMARY ===
{report.policy_summary}

=== POSITIVE IMPACTS ===
{positive_points}

=== AFFECTED COMMUNITY ===
{stakeholders}

=== INSTRUCTIONS ===
- Format: Community bulletin / newsletter entry
- Tone: Informative, positive, accessible (no legal jargon)
- Include: What the policy does, who benefits, how residents can engage or support it
- Length: 3-4 short paragraphs
- End with a call to action for residents

Output ONLY the bulletin text, no preamble or explanation."""

    return prompt


async def generate_action_artifact(report: ReportData, selected_grievances: Optional[List[str]] = None) -> ActionArtifact:
    """
    Action Agent: Dynamically generates civic engagement artifacts using the LLM
    and the actual verified claims, legal groundings, and impact data from the report.

    Addressee resolution:
    - If document text states an objection authority AND authority_status == ADMITTED: uses stated authority
    - Else: falls back to resolve_addressee(jurisdiction, ward) from the external registry. Zero hardcoding!
    """
    logger.info(f"Generating dynamic action artifact for verdict: {report.overall_verdict}")
    is_objection = report.overall_verdict in ("negative", "mixed")

    # Determine cited clause IDs from the report
    cited_ids = [
        c.get("id", c.get("claim_id", ""))
        for c in report.claim_confidence
        if c.get("status") == "ADMITTED" or c.get("verification_status") == "ADMITTED"
    ][:6]

    # Extract ward
    ward = next((c.get("ward") for c in report.claim_confidence if c.get("ward")), None)

    # Resolve jurisdiction details from registry
    registry = load_registry()
    jurisdiction_slug = report.jurisdiction or "_default"
    j_conf = registry.get(jurisdiction_slug, registry["_default"])
    jurisdiction_name = j_conf.get("name", "Local Municipal Jurisdiction")

    # 1. Document-first authority if ADMITTED; 2. Registry fallback
    if report.stated_objection_authority and report.authority_status == VerificationStatus.ADMITTED.value:
        recipient = report.stated_objection_authority
    else:
        recipient = resolve_addressee(jurisdiction_slug, ward=ward)

    # Extract deadline
    deadline = "Within 30 days of public notice publication"
    for c in report.claim_confidence:
        d = c.get("objection_deadline")
        if d:
            deadline = d
            break

    # Build prompt and call LLM
    if is_objection:
        prompt = _build_objection_prompt(
            report,
            recipient=recipient,
            jurisdiction_name=jurisdiction_name,
            selected_grievances=selected_grievances
        )
        action_type = "objection_letter"
        system = (
            f"You are an expert civic legal drafting assistant specializing in municipal administrative law for {jurisdiction_name}. "
            "Write formal, professional objection letters for citizen advocacy."
        )
    else:
        prompt = _build_awareness_prompt(report, jurisdiction_name=jurisdiction_name)
        action_type = "awareness_summary"
        system = (
            f"You are a civic communications officer in {jurisdiction_name} writing accessible community bulletins "
            "about positive municipal policies for ordinary citizens."
        )

    try:
        content = await llm_client.generate_text(
            prompt=prompt,
            system_prompt=system,
            json_mode=False
        )
        if not content or not content.strip():
            raise ValueError("LLM generated empty response")
        if is_objection and "FORMAL OBJECTION" not in content:
            content = f"FORMAL OBJECTION PETITION\n\n{content}"
        elif not is_objection and "COMMUNITY CIVIC BULLETIN" not in content:
            content = f"COMMUNITY CIVIC BULLETIN\n\n{content}"
        logger.info(f"LLM generated {action_type} successfully ({len(content)} chars)")
    except Exception as e:
        logger.warning(f"LLM generation failed for action agent: {e}, using structured fallback")
        if is_objection:
            neg = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(report.negative_impacts[:4]))
            content = (
                f"FORMAL OBJECTION PETITION\n\n"
                f"To: {recipient}\n"
                f"Subject: Formal Objection to Proposed Municipal Policy\n\n"
                f"Respected Authority,\n\n"
                f"We write with reference to the recently published municipal notice under {jurisdiction_name} jurisdiction. "
                f"Our verified analysis identifies the following concerns:\n\n"
                f"{neg}\n\n"
                f"We respectfully request a public consultation hearing before final notification.\n\n"
                f"Deadline for response: {deadline}\n\n"
                f"Sincerely,\nAggrieved Citizens and Residents Welfare Association"
            )
        else:
            pos = "\n".join(f"  - {p}" for p in report.positive_impacts[:4])
            content = (
                f"COMMUNITY CIVIC BULLETIN\n\n"
                f"Summary: {report.policy_summary}\n\n"
                f"Key Benefits:\n{pos}\n\n"
                f"Share this with your fellow residents!"
            )

    return ActionArtifact(
        action_type=action_type,
        content=content.strip(),
        target_deadline=deadline,
        recipient_authority=recipient,
        cited_clauses=cited_ids if cited_ids else ["See report for source references"]
    )
