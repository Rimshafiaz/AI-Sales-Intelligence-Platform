from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, model_validator


class SocialAuditState(str, Enum):
    NOT_RUN = "not_run"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SocialAuditResult:
    state: SocialAuditState
    reason: str
    audited_at: datetime


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
