from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.company_discovery import CompanyDiscoveryRequest
from app.schemas.discovery_shortlist import (
    CandidateShortlistInput,
    CandidateShortlistEntry,
    DiscoveryShortlistState,
)
from app.schemas.opportunity_models import OpportunityModelSelection


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=255)
    criteria: CompanyDiscoveryRequest
    model_selection: OpportunityModelSelection

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def require_confirmed_model_selection(self) -> Self:
        if not self.model_selection.confirmed_by_user:
            raise ValueError("Confirm the Opportunity Model selection before creating a campaign.")
        return self


class CampaignRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_summary: dict[str, int] = Field(min_length=1, max_length=10)
    discovered_candidate_count: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def require_consistent_provider_summary(self) -> Self:
        if any(value < 0 for value in self.provider_summary.values()):
            raise ValueError("Provider candidate counts cannot be negative.")
        if sum(self.provider_summary.values()) < self.discovered_candidate_count:
            raise ValueError(
                "Provider counts cannot be lower than the deduplicated candidate count."
            )
        return self


class CampaignCandidateSelectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_input: CandidateShortlistInput
    shortlist_entry: CandidateShortlistEntry

    @model_validator(mode="after")
    def require_eligible_matching_candidate(self) -> Self:
        if (
            self.shortlist_entry.state
            is not DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH
        ):
            raise ValueError(
                "Only candidates eligible for deeper research can be selected."
            )
        if self.shortlist_entry.company_name != self.candidate_input.candidate.company_name:
            raise ValueError("The shortlist entry must belong to the selected candidate.")
        candidate = self.candidate_input.candidate
        if not candidate.source_provider or not candidate.source_record_id:
            raise ValueError(
                "A selected candidate needs a provider and stable provider record ID."
            )
        return self


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    goal: str | None
    criteria: dict
    model_selection: dict
    created_at: datetime
    updated_at: datetime


class CampaignRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    status: str
    criteria_snapshot: dict
    model_selection_snapshot: dict
    provider_summary: dict
    discovered_candidate_count: int
    created_at: datetime


class CampaignCandidateSelectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_run_id: UUID
    company_id: UUID
    research_request_id: UUID
    source_identity_key: str
    created_at: datetime
