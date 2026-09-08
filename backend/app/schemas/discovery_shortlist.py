from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    DiscoveredCompanyCandidate,
)
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSource,
    EvidenceSignalType,
    OpportunityModelId,
    OpportunityModelSelection,
)
from app.schemas.social_enrichment import SocialProfileObservation


class DiscoveryShortlistState(str, Enum):
    EXCLUDED = "excluded"
    NEEDS_IDENTITY_REVIEW = "needs_identity_review"
    NEEDS_EVIDENCE = "needs_evidence"
    ELIGIBLE_FOR_DEEPER_RESEARCH = "eligible_for_deeper_research"


class NextEvidenceAction(str, Enum):
    NO_ACTION = "no_action"
    VERIFY_BUSINESS_IDENTITY = "verify_business_identity"
    VERIFY_OFFICIAL_WEBSITE = "verify_official_website"
    AUDIT_MOBILE_PERFORMANCE = "audit_mobile_performance"
    INSPECT_BOOKING_CONTACT_PATH = "inspect_booking_contact_path"
    INSPECT_RESTAURANT_RESERVATION_PATH = "inspect_restaurant_reservation_path"
    COLLECT_SOCIAL_PROFILE_OBSERVATIONS = "collect_social_profile_observations"
    VERIFY_OFFICIAL_SOCIAL_PROFILE = "verify_official_social_profile"
    CONFIRM_BUSINESS_ACTIVITY = "confirm_business_activity"
    CONFIRM_SOCIAL_HISTORY = "confirm_social_history"
    MEASURE_SOCIAL_DORMANCY = "measure_social_dormancy"


class CandidateShortlistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: DiscoveredCompanyCandidate
    evidence_signals: list[EvidenceSignal] = Field(default_factory=list, max_length=20)
    social_observations: list[SocialProfileObservation] = Field(
        default_factory=list,
        max_length=5,
    )


class DiscoveryShortlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: CompanyDiscoveryRequest
    model_selection: OpportunityModelSelection
    candidates: list[CandidateShortlistInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_user_confirmed_model_selection(self) -> Self:
        if not self.model_selection.confirmed_by_user:
            raise ValueError("Confirm the Opportunity Model selection before shortlisting.")
        return self


class DiscoveryOpportunityPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: CompanyDiscoveryRequest
    model_selection: OpportunityModelSelection
    candidates: list[DiscoveredCompanyCandidate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_user_confirmed_model_selection(self) -> Self:
        if not self.model_selection.confirmed_by_user:
            raise ValueError("Confirm the Opportunity Model selection before preparing the queue.")
        return self


class OpportunityModelShortlistEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: OpportunityModelId
    state: DiscoveryShortlistState
    observed_signal_types: list[EvidenceSignalType] = Field(default_factory=list)
    missing_signal_types: list[EvidenceSignalType] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=1_000)
    next_evidence_action: NextEvidenceAction


class CandidateShortlistEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(ge=0)
    company_name: str = Field(min_length=1, max_length=255)
    state: DiscoveryShortlistState
    model_evaluations: list[OpportunityModelShortlistEvaluation] = Field(
        min_length=1,
        max_length=3,
    )
    next_evidence_action: NextEvidenceAction


class DiscoveryShortlistResponse(BaseModel):
    candidates: list[CandidateShortlistEntry] = Field(max_length=100)


class DiscoveryOpportunityReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: OpportunityModelId
    signal_type: EvidenceSignalType
    supporting_value: str = Field(min_length=1, max_length=1_000)
    source: EvidenceSource
    captured_at: datetime


class DiscoveryOpportunityQueueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(ge=0)
    company_name: str = Field(min_length=1, max_length=255)
    reasons: list[DiscoveryOpportunityReason] = Field(min_length=1, max_length=3)


class DiscoveryOpportunityQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[DiscoveryOpportunityQueueEntry] = Field(max_length=100)
    needs_verification_count: int = Field(ge=0)
    not_surfaced_count: int = Field(ge=0)


class PreparedDiscoveryOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_entry: DiscoveryOpportunityQueueEntry
    candidate_input: CandidateShortlistInput
    shortlist_entry: CandidateShortlistEntry


class DiscoveryOpportunityPreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[PreparedDiscoveryOpportunity] = Field(max_length=100)
    needs_verification_count: int = Field(ge=0)
    not_surfaced_count: int = Field(ge=0)
