from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.opportunity_models import EvidenceSignalType, OpportunityModelId
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.social_audit import SocialAuditState, SocialProfileCandidate
from app.schemas.social_enrichment import SocialEnrichmentState, SocialPlatform


class SocialIdentityState(str, Enum):
    VERIFIED = "verified"
    UNRESOLVED = "unresolved"


class SelectedSocialModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: OpportunityModelId
    required_evidence_signals: list[EvidenceSignalType]


class GroundedSocialObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    profile_url: HttpUrl
    platform: SocialPlatform
    state: SocialEnrichmentState
    display_name: str | None = None
    handle: str | None = None
    external_url: HttpUrl | None = None
    public_emails: list[str] = Field(default_factory=list)
    public_phones: list[str] = Field(default_factory=list)
    latest_public_post_at: datetime | None = None
    recent_public_post_dates: list[datetime] = Field(default_factory=list)
    detail: str | None = None


class GroundedSocialEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_state: SocialIdentityState
    selected_models: list[SelectedSocialModel]
    candidate_profiles: list[SocialProfileCandidate]
    observations: list[GroundedSocialObservation]
    evidence: list[BriefEvidence]
    unresolved_requirements: list[EvidenceSignalType]
    audit_state: SocialAuditState
    audit_reason: str | None = None
