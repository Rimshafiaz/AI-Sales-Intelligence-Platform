from datetime import date
from typing import Literal, Self
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
    model_validator,
)



def _required_text(value: str, field_name: str) -> str:
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{field_name} cannot be blank.")

    return normalized_value


class SourceCitation(BaseModel):
    source_url: HttpUrl
    supporting_excerpt: str | None = Field(default=None, max_length=500)

    @field_serializer("source_url")
    def serialize_source_url(self, value: HttpUrl) -> str:
        return str(value).rstrip("/")

    @field_validator("supporting_excerpt")
    @classmethod
    def normalize_supporting_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class EvidenceBackedFinding(BaseModel):
    statement: str = Field(max_length=1_000)
    citations: list[SourceCitation] = Field(min_length=1, max_length=5)
    is_inference: bool
    rationale: str = Field(max_length=1_000)

    @field_validator("statement", "rationale")
    @classmethod
    def validate_required_text(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "Text")
        return _required_text(value, field_name)


class InferenceBackedFinding(EvidenceBackedFinding):
    @model_validator(mode="after")
    def require_inference_label(self) -> Self:
        if not self.is_inference:
            raise ValueError("This finding must be explicitly labeled as an inference.")

        return self


class CompanyProfile(BaseModel):
    company_summary: EvidenceBackedFinding
    company_description: EvidenceBackedFinding | None = None
    industry: EvidenceBackedFinding | None = None
    headquarters: EvidenceBackedFinding | None = None
    employee_count: EvidenceBackedFinding | None = None
    company_size: EvidenceBackedFinding | None = None
    website_metadata: EvidenceBackedFinding | None = None
    products_and_services: list[EvidenceBackedFinding] = Field(
        default_factory=list,
        max_length=10,
    )
    funding_information: list[EvidenceBackedFinding] = Field(
        default_factory=list,
        max_length=10,
    )

    @field_validator("products_and_services", "funding_information", mode="before")
    @classmethod
    def normalize_optional_finding_lists(cls, value: object) -> object:
        return [] if value is None else value


class TechnologyFinding(BaseModel):
    technology: EvidenceBackedFinding
    implication: InferenceBackedFinding | None = None


class BusinessSignal(BaseModel):
    signal_type: Literal["news", "hiring", "expansion", "funding", "announcement"]
    finding: EvidenceBackedFinding
    occurred_at: date | None = None


class OpportunityAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    reasons: list[InferenceBackedFinding] = Field(min_length=1, max_length=5)


class ContactRecommendation(BaseModel):
    recommendation: Literal["prioritize", "consider", "do_not_prioritize"]
    rationale: InferenceBackedFinding


class ReportConfidence(BaseModel):
    score: int = Field(ge=0, le=100)
    rationale: str = Field(max_length=1_000)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        return _required_text(value, "rationale")

class PainPointHypothesis(BaseModel):
    hypothesis: InferenceBackedFinding
    confidence: Literal["low", "medium", "high"]


class SalesStrategy(BaseModel):
    recommended_strategy: InferenceBackedFinding
    recommended_sales_angle: InferenceBackedFinding
    suggested_value_proposition: InferenceBackedFinding


class DecisionMakerHypothesis(BaseModel):
    suggested_role: str = Field(max_length=255)
    rationale: InferenceBackedFinding

    @field_validator("suggested_role")
    @classmethod
    def validate_suggested_role(cls, value: str) -> str:
        return _required_text(value, "suggested_role")


class PersonalizedOutreach(BaseModel):
    cold_email: str = Field(max_length=5_000)
    linkedin_message: str = Field(max_length=2_000)
    personalization_rationale: InferenceBackedFinding

    @field_validator("cold_email", "linkedin_message")
    @classmethod
    def validate_outreach_text(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "Outreach text")
        return _required_text(value, field_name)


class SalesIntelligenceReport(BaseModel):
    executive_summary: EvidenceBackedFinding
    company_profile: CompanyProfile
    technologies: list[TechnologyFinding] = Field(default_factory=list, max_length=10)
    business_signals: list[BusinessSignal] = Field(default_factory=list, max_length=10)
    opportunity_assessment: OpportunityAssessment
    contact_recommendation: ContactRecommendation
    confidence: ReportConfidence
    pain_points: list[PainPointHypothesis] = Field(default_factory=list, max_length=5)
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
        return [_required_text(value, "caveat") for value in values]
