from typing import Self

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


class BriefFindingsOutput(BaseModel):
    findings: list[AgentBriefFinding] = Field(default_factory=list, max_length=4)
    caveats: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("caveats")
    @classmethod
    def validate_caveats(cls, values: list[str]) -> list[str]:
        return _normalize_text_items(values, "caveats")


class BriefStrategyOutput(BaseModel):
    pitch_angle: AgentPitchAngle | None = None
    outreach_drafts: list[AgentGroundedOutreachDraft] = Field(default_factory=list, max_length=2)
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
