from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator, model_validator

from app.schemas.opportunity_models import EvidenceSource


class SocialPlatform(str, Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"


class SocialEnrichmentState(str, Enum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    NEEDS_REVIEW = "needs_review"


class SocialEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_urls: list[HttpUrl] = Field(min_length=1, max_length=20)

    @field_serializer("profile_urls")
    def serialize_profile_urls(self, value: list[HttpUrl]) -> list[str]:
        return [str(url).rstrip("/") for url in value]

    @model_validator(mode="after")
    def require_unique_profile_urls(self) -> Self:
        profile_urls = [str(url).rstrip("/").casefold() for url in self.profile_urls]
        if len(profile_urls) != len(set(profile_urls)):
            raise ValueError("Each social profile URL may be requested only once.")
        return self


class SocialProfileObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_url: HttpUrl
    platform: SocialPlatform
    state: SocialEnrichmentState
    display_name: str | None = Field(default=None, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    provider_profile_id: str | None = Field(default=None, max_length=255)
    biography: str | None = Field(default=None, max_length=2_000)
    external_url: HttpUrl | None = None
    public_emails: list[str] = Field(default_factory=list, max_length=3)
    public_phones: list[str] = Field(default_factory=list, max_length=3)
    follower_count: int | None = Field(default=None, ge=0)
    post_count: int | None = Field(default=None, ge=0)
    is_private: bool | None = None
    is_verified: bool | None = None
    public_business_category: str | None = Field(default=None, max_length=255)
    latest_public_post_at: datetime | None = None
    recent_public_post_dates: list[datetime] = Field(default_factory=list, max_length=12)
    source: EvidenceSource
    detail: str | None = Field(default=None, max_length=500)

    @field_serializer("profile_url", "external_url")
    def serialize_urls(self, value: HttpUrl | None) -> str | None:
        return str(value).rstrip("/") if value is not None else None

    @field_validator(
        "display_name",
        "handle",
        "provider_profile_id",
        "biography",
        "public_business_category",
        "detail",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("public_emails", "public_phones", mode="before")
    @classmethod
    def normalize_public_contacts(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return list(
            dict.fromkeys(
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            )
        )


class SocialEnrichmentResponse(BaseModel):
    observations: list[SocialProfileObservation] = Field(max_length=20)
