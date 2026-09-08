from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.opportunity_models import (
    IndustryOverlayId,
    OpportunityModelId,
    OpportunityModelSelection,
)


class OpportunityQualificationState(str, Enum):
    LIKELY = "likely"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_ELIGIBLE = "not_eligible"


class OpportunityQualificationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_selection: OpportunityModelSelection | None = None
    industry: IndustryOverlayId | None = None


class OpportunityQualificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_request_id: UUID
    opportunity_model_id: OpportunityModelId
    state: OpportunityQualificationState
    reason: str = Field(min_length=1, max_length=1_000)
    supporting_evidence_keys: list[str]
    evaluated_at: datetime
