from enum import Enum
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

class TypologyCategory(str, Enum):
    LAND_USE = "land_use"
    TAX = "tax"
    INFRASTRUCTURE = "infrastructure"
    ENVIRONMENTAL = "environmental"
    BUDGET = "budget"
    OTHER = "other"

class VerificationStatus(str, Enum):
    ADMITTED = "ADMITTED"
    PENDING_AUDIT = "PENDING_AUDIT"
    REJECTED_PRUNED = "REJECTED_PRUNED"

class GroundingStatus(str, Enum):
    MATCHED = "matched"
    CONTRADICTORY = "contradictory"
    NOT_FOUND = "not_found"
    CORPUS_UNAVAILABLE = "corpus_unavailable"

class Clause(BaseModel):
    id: str
    text: str = Field(description="Verbatim text from source document, never paraphrased")
    page: int
    char_start: int
    char_end: int
    clause_type: Optional[str] = "general"
    ward: Optional[str] = None
    objection_deadline: Optional[str] = None
    cited_legal_basis: Optional[str] = None
    typology: Optional[TypologyCategory] = None
    stated_objection_authority: Optional[str] = None
    jurisdiction_hint: Optional[str] = None
    authority_status: Optional[VerificationStatus] = None
    extraction_source: List[str] = Field(default_factory=lambda: ["regex"])

class VerifiedClaim(BaseModel):
    clause: Clause
    nli_score: float = Field(default=0.0, description="NLI cross-encoder score")
    llm_judge_score: float = Field(default=0.0, description="LLM judge score")
    llm_judge_verdict: Literal["yes", "no", "partial"] = "partial"
    llm_judge_reasoning: str = ""
    judge_source: Optional[str] = "llm_judge"
    status: VerificationStatus = VerificationStatus.PENDING_AUDIT
    human_audited: bool = False
    audit_decision: Optional[Literal["APPROVE", "REJECT"]] = None
    audit_notes: Optional[str] = None

class LegalGroundingResult(BaseModel):
    citation: str
    grounded: Optional[bool] = None
    grounding_status: GroundingStatus
    matched_statute_section: Optional[str] = None
    statute_name: Optional[str] = None
    statute_excerpt: Optional[str] = None
    notes: Optional[str] = None
    jurisdiction: Optional[str] = None

class ImpactTag(BaseModel):
    claim_id: str
    polarity: Literal["positive", "negative", "neutral_mixed"]
    affected_group: str
    reasoning: str
    critic_confirmed: Optional[bool] = None
    critic_note: Optional[str] = None
    overlooked_subgroups: List[str] = Field(default_factory=list)
    requires_audit: bool = False

class ContradictionRecord(BaseModel):
    claim_id: str
    ward: Optional[str] = None
    prior_doc_id: Optional[str] = None
    prior_clause_text: Optional[str] = None
    similarity_score: float = 0.0
    contradiction_flag: bool = False
    notes: Optional[str] = None

class ImpactItem(BaseModel):
    """Unified impact entry carrying both Impact Analysis Agent and Critic Agent perspectives."""
    text: str = Field(description="The impact description shown to the user")
    polarity: Literal["positive", "negative", "neutral_mixed"] = Field(description="Agent's polarity assessment")
    affected_group: str = Field(description="Specific stakeholder group affected")
    impact_reasoning: str = Field(description="Impact Analysis Agent's reasoning")
    critic_confirmed: Optional[bool] = None
    critic_note: Optional[str] = None
    overlooked_subgroups: List[str] = Field(default_factory=list)

class ReportData(BaseModel):
    policy_summary: str
    stakeholders_impacted: List[str] = Field(default_factory=list)
    positive_impacts: List[str] = Field(default_factory=list)
    negative_impacts: List[str] = Field(default_factory=list)
    impacts: List[ImpactItem] = Field(default_factory=list, description="Unified impacts with dual-agent perspectives")
    risk_flags: List[str] = Field(default_factory=list)
    legal_grounding: List[LegalGroundingResult] = Field(default_factory=list)
    claim_confidence: List[Dict[str, Any]] = Field(default_factory=list)
    policy_contradictions: List[ContradictionRecord] = Field(default_factory=list)
    overall_verdict: Literal["positive", "negative", "mixed"]
    dropped_claims_count: int = 0
    jurisdiction: Optional[str] = None
    stated_objection_authority: Optional[str] = None
    authority_status: Optional[str] = None
    omission_warnings: List[str] = Field(default_factory=list)

class ActionArtifact(BaseModel):
    action_type: Literal["objection_letter", "awareness_summary"]
    content: str
    target_deadline: Optional[str] = None
    recipient_authority: Optional[str] = None
    cited_clauses: List[str] = Field(default_factory=list)

class ExecutionPlan(BaseModel):
    document_id: str
    page_count: int
    execution_mode: Literal["sequential", "parallel_fan_out"] = "sequential"
    detected_proposals: List[str] = Field(default_factory=list)
    reasoning: str = ""

# LangGraph State
class CivicLensState(TypedDict, total=False):
    document_id: str
    filename: str
    raw_bytes: Optional[bytes]
    pages_text: List[str]
    ocr_available: bool
    plan: Optional[Dict[str, Any]]
    execution_mode: str
    proposal_chunks: List[Dict[str, Any]]
    proposal_merged: Optional[bool]
    raw_clauses: List[Dict[str, Any]]
    classified_clauses: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    verified_claims: List[Dict[str, Any]]
    audit_pending: bool
    grounded_claims: List[Dict[str, Any]]
    impact_tags: List[Dict[str, Any]]
    critic_reviewed_tags: List[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    error: Optional[str]
