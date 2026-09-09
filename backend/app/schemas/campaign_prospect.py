from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.campaign_prospect import CampaignProspectNextAction, CampaignProspectState
from app.schemas.discovery_shortlist import CandidateShortlistInput, CandidateShortlistEntry, DiscoveryShortlistState


class CampaignProspectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_run_id: UUID
    candidate_input: CandidateShortlistInput
    shortlist_entry: CandidateShortlistEntry

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        candidate = self.candidate_input.candidate
        if self.shortlist_entry.company_name != candidate.company_name:
            raise ValueError("The shortlist entry must belong to the selected candidate.")
        if self.shortlist_entry.state is DiscoveryShortlistState.EXCLUDED:
            raise ValueError("Excluded candidates cannot be saved as campaign prospects.")
        if not candidate.source_provider or not candidate.source_record_id:
            raise ValueError("A saved prospect needs a provider and stable provider record ID.")
        return self


class CampaignProspectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_state: CampaignProspectState


class CampaignProspectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    campaign_run_id: UUID
    source_identity_key: str
    candidate_index: int
    candidate_snapshot: dict
    shortlist_snapshot: dict
    evidence_snapshot: list
    workflow_state: CampaignProspectState
    next_action: CampaignProspectNextAction
    created_at: datetime
    updated_at: datetime
