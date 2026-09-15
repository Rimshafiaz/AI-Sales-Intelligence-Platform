from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, model_validator

from app.schemas.opportunity_models import EvidenceSignalType
from app.schemas.social_enrichment import SocialPlatform, SocialProfileObservation


class SocialAuditState(str, Enum):
    NOT_RUN = "not_run"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SocialAuditResult:
    state: SocialAuditState
    reason: str
    audited_at: datetime


class SocialCandidateDiscoveryState(str, Enum):
    CANDIDATES_AVAILABLE = "candidates_available"
    NO_CANDIDATES = "no_candidates"
    UNAVAILABLE = "unavailable"
    NOT_PERMITTED = "not_permitted"


class SocialProfileCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_url: HttpUrl
    platform: SocialPlatform
    handle: str
    source: Literal["campaign", "bounded_search", "manual_compatibility"]


class SocialCandidateDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: SocialCandidateDiscoveryState
    candidates: list[SocialProfileCandidate] = Field(default_factory=list, max_length=3)
    reason: str


class SocialEnrichmentResultState(str, Enum):
    OBSERVATIONS_AVAILABLE = "observations_available"
    ALREADY_AVAILABLE = "already_available"
    UNAVAILABLE = "unavailable"
    NO_CANDIDATES = "no_candidates"
    NOT_PERMITTED = "not_permitted"


class SocialCandidateEnrichmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: SocialEnrichmentResultState
    observations: list[SocialProfileObservation] = Field(default_factory=list, max_length=20)
    reason: str


class SocialVerificationState(str, Enum):
    EVIDENCE_FOUND = "evidence_found"
    ALREADY_AVAILABLE = "already_available"
    NO_OFFICIAL_PROFILE_VERIFIED = "no_official_profile_verified"
    INSUFFICIENT_ACTIVITY_HISTORY = "insufficient_activity_history"
    DORMANCY_UNMEASURABLE = "dormancy_unmeasurable"
    UNAVAILABLE = "unavailable"
    NOT_PERMITTED = "not_permitted"


class SocialVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: SocialVerificationState
    reason: str
    verified_profile_count: int = Field(default=0, ge=0)
    evidence_signals: list[EvidenceSignalType] = Field(default_factory=list)


class SocialAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_urls: list[HttpUrl] = Field(default_factory=list, max_length=3)

    @field_serializer("profile_urls")
    def serialize_profile_urls(self, value: list[HttpUrl]) -> list[str]:
        return [str(url).rstrip("/") for url in value]

    @model_validator(mode="after")
    def require_unique_profile_urls(self):
        urls = [str(url).rstrip("/").casefold() for url in self.profile_urls]
        if len(urls) != len(set(urls)):
            raise ValueError("Each social profile URL may be requested only once.")
        return self
