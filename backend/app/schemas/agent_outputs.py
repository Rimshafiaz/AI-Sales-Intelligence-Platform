from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.sales_intelligence_report import (
    BusinessSignal,
    CompanyProfile,
    ContactRecommendation,
    DecisionMakerHypothesis,
    EvidenceBackedFinding,
    OpportunityAssessment,
    PainPointHypothesis,
    PersonalizedOutreach,
    ReportConfidence,
    SalesStrategy,
    TechnologyFinding,
)
from app.schemas.prospect_evidence_brief import (
    BriefFinding,
    GroundedOutreachDraft,
    OutreachGrounding,
    PitchAngle,
)


def _normalize_text_items(values: list[str], field_name: str) -> list[str]:
    normalized_values = [value.strip() for value in values]
    if any(not value for value in normalized_values):
        raise ValueError(f"{field_name} cannot contain blank text.")

    return normalized_values


class ResearchAgentOutput(BaseModel):
    company_profile: CompanyProfile


class TechnologyAgentOutput(BaseModel):
    technologies: list[TechnologyFinding] = Field(default_factory=list, max_length=10)


class NewsAgentOutput(BaseModel):
    business_signals: list[BusinessSignal] = Field(default_factory=list, max_length=10)


class PainPointAgentOutput(BaseModel):
    pain_points: list[PainPointHypothesis] = Field(default_factory=list, max_length=5)


class StrategyAgentOutput(BaseModel):
    executive_summary: EvidenceBackedFinding
    opportunity_assessment: OpportunityAssessment
    contact_recommendation: ContactRecommendation
    confidence: ReportConfidence
    strategy: SalesStrategy
    suggested_decision_makers: list[DecisionMakerHypothesis] = Field(
        default_factory=list,
        max_length=5,
    )
    personalized_outreach: PersonalizedOutreach
    caveats: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("caveats")
    @classmethod
    def validate_caveats(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "caveats")


class ReviewerOutput(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("issues")
    @classmethod
    def validate_issues(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "issues")

    @model_validator(mode="after")
    def require_issues_when_not_approved(self) -> Self:
        if not self.approved and not self.issues:
            raise ValueError("Reviewer must provide at least one issue when rejecting a report.")

        return self


class AgentBriefFinding(BriefFinding):
    model_config = ConfigDict(extra="ignore")


class AgentPitchAngle(PitchAngle):
    model_config = ConfigDict(extra="ignore")


class AgentOutreachGrounding(OutreachGrounding):
    model_config = ConfigDict(extra="ignore")


class AgentGroundedOutreachDraft(GroundedOutreachDraft):
    model_config = ConfigDict(extra="ignore")

    grounding: list[AgentOutreachGrounding] = Field(min_length=1, max_length=5)


class WebsiteResearchOutput(BaseModel):
    website_status: Literal["verified", "not_verified", "unresolved"]
    findings: list[AgentBriefFinding] = Field(default_factory=list, max_length=4)
    evidence_gaps: list[str] = Field(default_factory=list, max_length=5)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("evidence_gaps", "caveats")
    @classmethod
    def validate_text_items(cls, values: list[str], info) -> list[str]:
        return _normalize_text_items(values, info.field_name)


class SocialResearchOutput(BaseModel):
    presence_status: Literal[
        "verified",
        "partially_verified",
        "none_verified",
        "unresolved",
    ]
    findings: list[AgentBriefFinding] = Field(default_factory=list, max_length=4)
    evidence_gaps: list[str] = Field(default_factory=list, max_length=5)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("evidence_gaps", "caveats")
    @classmethod
    def validate_text_items(cls, values: list[str], info) -> list[str]:
        return _normalize_text_items(values, info.field_name)


class OpportunityOutreachOutput(BaseModel):
    opportunity_summary: AgentBriefFinding
    pitch_angle: AgentPitchAngle
    personalization_basis: list[AgentBriefFinding] = Field(min_length=1, max_length=5)
    forbidden_claims: list[str] = Field(default_factory=list, max_length=10)
    outreach_drafts: list[AgentGroundedOutreachDraft] = Field(default_factory=list, max_length=6)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("forbidden_claims", "caveats")
    @classmethod
    def validate_text_items(cls, values: list[str], info) -> list[str]:
        return _normalize_text_items(values, info.field_name)


BriefReviewIssueType = Literal[
    "unsupported_claim",
    "qualification_contradiction",
    "generic_outreach",
    "weak_personalization",
    "duplicate_insight",
    "overstated_evidence",
    "unsupported_channel",
    "irrelevant_finding",
]


class BriefReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: BriefReviewIssueType
    reason: str = Field(min_length=3, max_length=1_000)
    field: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("reason", "field")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Review issue text cannot be blank.")
        return normalized


class BriefReviewOutput(BaseModel):
    approved: bool
    issues: list[BriefReviewIssue] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def require_issues_when_rejected(self) -> Self:
        if not self.approved and not self.issues:
            raise ValueError("Reviewer must provide issues when rejecting a Prospect Evidence Brief.")
        return self


class BriefFindingsOutput(BaseModel):
    findings: list[AgentBriefFinding] = Field(default_factory=list, max_length=4)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("caveats")
    @classmethod
    def validate_caveats(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "caveats")


class BriefStrategyOutput(BaseModel):
    pitch_angle: AgentPitchAngle | None = None
    outreach_drafts: list[AgentGroundedOutreachDraft] = Field(default_factory=list, max_length=6)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("caveats")
    @classmethod
    def validate_caveats(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "caveats")


class BriefReviewerOutput(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("issues")
    @classmethod
    def validate_issues(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "issues")

    @model_validator(mode="after")
    def require_issues_when_rejected(self) -> Self:
        if not self.approved and not self.issues:
            raise ValueError("Reviewer must provide issues when rejecting a Prospect Evidence Brief.")
        return self
