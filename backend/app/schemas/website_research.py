from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.opportunity_models import EvidenceSource, EvidenceSignalType, OpportunityModelId
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.website_audit import (
    WebsiteAuditState,
    WebsiteCheckExecutions,
    WebsiteCheckState,
)


class WebsiteTargetStatus(str, Enum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    UNRESOLVED = "unresolved"


class VerifiedWebsiteTargetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_status: WebsiteTargetStatus
    official_website: HttpUrl | None = None
    reason: str
    source: EvidenceSource | None = None


class WebsiteCapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: WebsiteCheckState
    reason: str
    signal_type: EvidenceSignalType | None = None
    numeric_value: float | None = None
    source_identity_key: str | None = None


class SelectedWebsiteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: OpportunityModelId
    required_evidence_signals: list[EvidenceSignalType]


class GroundedWebsiteEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_status: WebsiteTargetStatus
    selected_models: list[SelectedWebsiteModel]
    evidence: list[BriefEvidence]
    unresolved_requirements: list[EvidenceSignalType]
    audit_state: WebsiteAuditState
    audit_reason: str | None = None
    check_states: WebsiteCheckExecutions = Field(default_factory=WebsiteCheckExecutions)


class WebsiteResearchHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seller_goal: str
    offering: str
    company_name: str
    location: str | None = None
    starting_state: GroundedWebsiteEvidenceResult
