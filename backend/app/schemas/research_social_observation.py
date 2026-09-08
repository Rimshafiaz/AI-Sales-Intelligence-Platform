from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.social_enrichment import SocialEnrichmentState, SocialPlatform


class ResearchSocialObservationResponse(BaseModel):
    id: UUID
    research_request_id: UUID
    platform: SocialPlatform
    profile_url: str
    state: SocialEnrichmentState
    detail: str | None = None
    display_name: str | None = None
    handle: str | None = None
    external_url: str | None = None
    is_private: bool | None = None
    latest_public_post_at: datetime | None = None
    recent_public_post_dates: list[datetime]
    source_provider: str
    source_record_id: str | None = None
    source_url: str
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)
