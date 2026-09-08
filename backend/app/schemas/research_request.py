from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from typing import Self
from uuid import UUID
from datetime import datetime

from app.schemas.company_discovery import (
    SUPPORTED_GOAL_TYPES,
    UNSUPPORTED_GOAL_MESSAGE,
    DiscoveryObjective,
)
from app.schemas.opportunity_models import EvidenceSource, IdentityState
from app.schemas.evidence_gate import EvidenceGateState


class KnownProspectResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=255)
    goal: str = Field(min_length=3, max_length=2_000)
    offering: str = Field(min_length=3, max_length=300)
    desired_outcome: str = Field(min_length=3, max_length=300)
    location: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None

    @field_validator(
        "business_name", "goal", "offering", "desired_outcome", "location", mode="before"
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class KnownProspectResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    identity_state: IdentityState
    source: EvidenceSource | None = None
    reason: str = Field(min_length=1, max_length=1_000)


class ResearchRequestStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=3, max_length=2_000)
    offering: str | None = Field(default=None, min_length=3, max_length=300)
    region: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    objective: DiscoveryObjective | None = None

    @field_validator("goal", "offering", "region", "website", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def require_supported_research_scope(self) -> Self:
        if self.objective is not None:
            if self.objective.goal_type not in SUPPORTED_GOAL_TYPES:
                raise ValueError(UNSUPPORTED_GOAL_MESSAGE)
            self.offering = self.offering or self.objective.offering

        if not self.offering:
            raise ValueError("Describe what you are offering so the research can be scoped.")

        return self


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
    evidence_gate_state: EvidenceGateState
    evidence_gate_reason: str | None = None
    evidence_gated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
