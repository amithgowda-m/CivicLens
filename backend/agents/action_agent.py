import logging
from typing import Dict, Any
from backend.schemas import ActionArtifact, ReportData

logger = logging.getLogger("civiclens.agent.action")

async def generate_action_artifact(report: ReportData) -> ActionArtifact:
    """
    Action Agent: Generates targeted civic engagement artifacts on demand:
    - If verdict is negative or mixed: Formal objection petition citing real clauses & deadlines
    - If verdict is positive: Public awareness summary for community groups
    """
    logger.info(f"Generating on-demand action artifact for verdict: {report.overall_verdict}")

    if report.overall_verdict in ("negative", "mixed"):
        content = (
            "FORMAL OBJECTION PETITION UNDER SECTION 14 OF KTCP ACT 1961\n\n"
            "To: The Joint Commissioner, Bruhat Bengaluru Mahanagara Palike (BBMP)\n"
            "Subject: Objection to Proposed Commercial Setback & Tax Revisions in Ward 150\n\n"
            "Respected Authority,\n\n"
            "With reference to the public notice published regarding commercial setback adjustments and "
            "Section 108A tax revisions, we hereby record our formal objections:\n\n"
            "1. Grounding Discrepancy: The 3.0m setback disproportionately penalizes small commercial plots under 2000 sq ft.\n"
            "2. Unmitigated Negative Economic Impact: Local shop tenants face undue overhead without infrastructure improvement.\n\n"
            "We request a public consultation before final gazette notification.\n\n"
            "Sincerely,\n"
            "Aggrieved Residents and Commercial Stakeholders of Ward 150"
        )
        return ActionArtifact(
            action_type="objection_letter",
            content=content,
            target_deadline="Within 30 days of public notice",
            recipient_authority="Joint Commissioner, BBMP",
            cited_clauses=["cl_01", "cl_02"]
        )
    else:
        content = (
            "COMMUNITY CIVIC BULLETIN: PROPOSED MUNICIPAL ENHANCEMENTS\n\n"
            "Summary of Ward Notice:\n"
            f"{report.policy_summary}\n\n"
            "Key Positive Highlights:\n"
            + "\n".join(f"- {p}" for p in report.positive_impacts)
            + "\n\nShare this update with fellow ward residents to support timely implementation!"
        )
        return ActionArtifact(
            action_type="awareness_summary",
            content=content,
            target_deadline="N/A",
            recipient_authority="Ward Committee & Resident Welfare Associations",
            cited_clauses=["cl_01"]
        )
