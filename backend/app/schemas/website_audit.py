from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.opportunity_models import EvidenceSignalType


class WebsiteAuditState(str, Enum):
    NOT_RUN = "not_run"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WebsiteAuditResult:
    state: WebsiteAuditState
    reason: str
    audited_at: datetime


class WebsiteCheckState(str, Enum):
    NOT_RUN = "not_run"
    EVIDENCE_FOUND = "evidence_found"
    ALREADY_AVAILABLE = "already_available"
    NO_GAP_OBSERVED = "no_gap_observed"
    UNAVAILABLE = "unavailable"
    NOT_PERMITTED = "not_permitted"


@dataclass(frozen=True)
class WebsiteCheckResult:
    state: WebsiteCheckState
    reason: str
    signal_type: EvidenceSignalType | None = None
    numeric_value: float | None = None
    source_identity_key: str | None = None


class WebsiteCheckExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: WebsiteCheckState = WebsiteCheckState.NOT_RUN
    reason: str | None = None
    checked_at: datetime | None = None


class WebsiteCheckExecutions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobile_performance: WebsiteCheckExecution = Field(default_factory=WebsiteCheckExecution)
    conversion_paths: WebsiteCheckExecution = Field(default_factory=WebsiteCheckExecution)
