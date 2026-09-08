from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceGateState(str, Enum):
    NOT_RUN = "not_run"
    READY_FOR_DEEPER_RESEARCH = "ready_for_deeper_research"
    NEEDS_REVIEW = "needs_review"


class SourceAdmissionState(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXCLUDED = "excluded"
    NEEDS_REVIEW = "needs_review"


class EvidenceGateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: EvidenceGateState
    reason: str = Field(min_length=1, max_length=1_000)
    evaluated_at: datetime
