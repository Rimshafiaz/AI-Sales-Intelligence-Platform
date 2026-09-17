from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from typing import Self
from uuid import UUID
from datetime import datetime

from app.schemas.opportunity_models import EvidenceSource, IdentityState, OpportunityModelSelection
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.website_audit import WebsiteAuditState, WebsiteCheckExecutions
from app.schemas.social_audit import SocialAuditState, SocialCheckStates


class KnownProspectResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=255)
    goal: str = Field(min_length=3, max_length=2_000)
    offering: str = Field(min_length=3, max_length=300)
    desired_outcome: str = Field(min_length=3, max_length=300)
    location: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    phone_number: str | None = Field(default=None, max_length=100)
    model_selection: OpportunityModelSelection | None = None

    @field_validator(
        "business_name", "goal", "offering", "desired_outcome", "location", "phone_number", mode="before"
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def require_confirmed_model_selection(self) -> Self:
        if self.model_selection is not None and not self.model_selection.confirmed_by_user:
            raise ValueError("Confirm the Opportunity Model selection before creating research.")
        return self


class KnownProspectConfirmationRequest(KnownProspectResearchRequest):
    model_selection: OpportunityModelSelection

    @model_validator(mode="after")
    def require_confirmed_selection(self) -> Self:
        if not self.model_selection.confirmed_by_user:
            raise ValueError("Confirm the Opportunity Model selection before creating research.")
        return self


class KnownProspectResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    identity_state: IdentityState
    source: EvidenceSource | None = None
    reason: str = Field(min_length=1, max_length=1_000)


class ResearchRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    objective: dict | None = None
    opportunity_model_selection: OpportunityModelSelection | None = None
    specialist_outputs: dict | None = None
    website_check_states: WebsiteCheckExecutions | None = None
    social_check_states: SocialCheckStates | None = None
    evidence_gate_state: EvidenceGateState
    evidence_gate_reason: str | None = None
    evidence_gated_at: datetime | None = None
    website_audit_state: WebsiteAuditState
    website_audit_reason: str | None = None
    website_audited_at: datetime | None = None
    social_audit_state: SocialAuditState
    social_audit_reason: str | None = None
    social_audited_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
