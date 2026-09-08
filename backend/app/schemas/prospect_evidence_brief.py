from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator, model_validator

from app.schemas.opportunity_models import EvidenceSignalType, EvidenceSource, EvidenceType, OpportunityModelId
from app.schemas.opportunity_qualification import OpportunityQualificationState


class BriefEvidenceQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    NEEDS_REVIEW = "needs_review"


class BriefClaimKind(str, Enum):
    OBSERVED = "observed"
    DERIVED_METRIC = "derived_metric"
    INFERENCE = "inference"


class ContactPathType(str, Enum):
    WEBSITE = "website"
    PHONE = "phone"
    EMAIL = "email"
    SOCIAL_PROFILE = "social_profile"
    CONTACT_FORM = "contact_form"


class ContactEvidenceState(str, Enum):
    VERIFIED = "verified"
    OBSERVED = "observed"


class OutreachChannel(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"


class BriefObjective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=3, max_length=2_000)
    offering: str = Field(min_length=3, max_length=300)
    desired_outcome: str = Field(min_length=3, max_length=300)

    @field_validator("goal", "offering", "desired_outcome")
    @classmethod
    def require_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Objective text cannot be blank.")
        return normalized


class BriefProspect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=200)
    official_website: HttpUrl | None = None
    identity_verified: bool

    @field_serializer("official_website")
    def serialize_website(self, value: HttpUrl | None) -> str | None:
        return str(value).rstrip("/") if value else None


class BriefSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=3, max_length=500)
    provider: str = Field(min_length=2, max_length=100)
    source_url: HttpUrl
    retrieved_at: datetime
    title: str | None = Field(default=None, max_length=500)
    excerpt: str | None = Field(default=None, max_length=1_000)

    @field_serializer("source_url")
    def serialize_source_url(self, value: HttpUrl) -> str:
        return str(value).rstrip("/")


class BriefEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=3, max_length=500)
    signal_type: EvidenceSignalType
    evidence_type: EvidenceType
    supporting_value: str = Field(min_length=1, max_length=1_000)
    numeric_value: float | None = None
    source: EvidenceSource
    captured_at: datetime


class BriefQualification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_model_id: OpportunityModelId
    state: OpportunityQualificationState
    reason: str = Field(min_length=1, max_length=1_000)
    supporting_evidence_keys: list[str] = Field(default_factory=list, max_length=10)
    evaluated_at: datetime


class BriefFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=3, max_length=1_000)
    claim_kind: BriefClaimKind
    evidence_keys: list[str] = Field(min_length=1, max_length=5)

    @field_validator("statement")
    @classmethod
    def require_statement(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Finding statement cannot be blank.")
        return normalized


class BriefContactPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_type: ContactPathType
    value: str = Field(min_length=3, max_length=2_048)
    state: ContactEvidenceState
    source_keys: list[str] = Field(min_length=1, max_length=3)


class PitchAngle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=3, max_length=1_000)
    offering: str = Field(min_length=3, max_length=300)
    evidence_keys: list[str] = Field(min_length=1, max_length=5)


class OutreachGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=3, max_length=500)
    evidence_keys: list[str] = Field(min_length=1, max_length=5)


class GroundedOutreachDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: OutreachChannel
    message: str = Field(min_length=3, max_length=5_000)
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    offering: str = Field(min_length=3, max_length=300)
    grounding: list[OutreachGrounding] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def require_email_subject_only_for_email(self):
        if self.channel is OutreachChannel.EMAIL and self.subject is None:
            raise ValueError("An email outreach draft requires a subject.")
        if self.channel is not OutreachChannel.EMAIL and self.subject is not None:
            raise ValueError("Only an email outreach draft may include a subject.")
        return self


class ProspectEvidenceBriefContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    qualifications: list[BriefQualification] = Field(min_length=1, max_length=3)
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)
    sources: list[BriefSource] = Field(default_factory=list, max_length=15)
    contacts: list[BriefContactPath] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def require_traceable_qualification_and_contacts(self):
        evidence_keys = {item.key for item in self.evidence}
        source_keys = evidence_keys | {item.key for item in self.sources}
        for qualification in self.qualifications:
            if not set(qualification.supporting_evidence_keys) <= evidence_keys:
                raise ValueError("Qualification references evidence outside the brief context.")
        for contact in self.contacts:
            if not set(contact.source_keys) <= source_keys:
                raise ValueError("Contact path references data outside the brief context.")
        return self


class BusinessContextHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    sources: list[BriefSource] = Field(default_factory=list, max_length=15)


class DigitalPresenceHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)


class PublicTractionHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    sources: list[BriefSource] = Field(default_factory=list, max_length=15)
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)


class OpportunityDiagnosisHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    qualifications: list[BriefQualification] = Field(min_length=1, max_length=3)
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)


class StrategyOutreachHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    qualifications: list[BriefQualification] = Field(min_length=1, max_length=3)
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)
    contacts: list[BriefContactPath] = Field(default_factory=list, max_length=10)


class EvidenceQualityReviewHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ProspectEvidenceBriefContext


class ProspectEvidenceBriefHandoffs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_context: BusinessContextHandoff
    digital_presence: DigitalPresenceHandoff
    public_traction: PublicTractionHandoff
    opportunity_diagnosis: OpportunityDiagnosisHandoff
    strategy_outreach: StrategyOutreachHandoff
    evidence_quality_review: EvidenceQualityReviewHandoff


class ProspectEvidenceBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    verdict: BriefQualification
    evidence_quality: BriefEvidenceQuality
    findings: list[BriefFinding] = Field(default_factory=list, max_length=12)
    contacts: list[BriefContactPath] = Field(default_factory=list, max_length=10)
    pitch_angle: PitchAngle | None = None
    outreach_drafts: list[GroundedOutreachDraft] = Field(default_factory=list, max_length=2)
    caveats: list[str] = Field(default_factory=list, max_length=10)
    evidence: list[BriefEvidence] = Field(min_length=1, max_length=30)
    sources: list[BriefSource] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def require_grounded_goal_specific_content(self):
        evidence_keys = {item.key for item in self.evidence}
        source_keys = evidence_keys | {item.key for item in self.sources}
        if not self.prospect.identity_verified:
            raise ValueError("A Prospect Evidence Brief requires a verified business identity.")
        if not set(self.verdict.supporting_evidence_keys) <= evidence_keys:
            raise ValueError("Verdict references evidence outside the brief.")
        for finding in self.findings:
            if not set(finding.evidence_keys) <= evidence_keys:
                raise ValueError("Finding references evidence outside the brief.")
        for contact in self.contacts:
            if not set(contact.source_keys) <= source_keys:
                raise ValueError("Contact path references data outside the brief.")
        if self.pitch_angle is not None:
            if self.pitch_angle.offering != self.objective.offering:
                raise ValueError("Pitch angle must use the user's stated offering.")
            if not set(self.pitch_angle.evidence_keys) <= evidence_keys:
                raise ValueError("Pitch angle references evidence outside the brief.")
        if self.verdict.state is not OpportunityQualificationState.LIKELY:
            if self.pitch_angle is not None or self.outreach_drafts:
                raise ValueError("Only a likely qualification may include a pitch angle or outreach.")
        for draft in self.outreach_drafts:
            if draft.offering != self.objective.offering:
                raise ValueError("Outreach must use the user's stated offering.")
            for grounding in draft.grounding:
                if not set(grounding.evidence_keys) <= evidence_keys:
                    raise ValueError("Outreach references evidence outside the brief.")
        return self
