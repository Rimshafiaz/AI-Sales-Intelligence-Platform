from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from app.schemas.opportunity_models import IndustryOverlayId


@dataclass(frozen=True)
class LocalDiscoveryArea:
    display_name: str
    latitude: float
    longitude: float
    radius_miles: float


class DiscoverySourceType(str, Enum):
    LOCAL_PLACES = "local_places"
    WEB_SEARCH = "web_search"
    SOCIAL_SEARCH = "social_search"


@dataclass(frozen=True)
class LocalBusinessDiscoveryRequest:
    industry: IndustryOverlayId
    area: LocalDiscoveryArea
    max_results: int


@dataclass(frozen=True)
class DiscoveredBusiness:
    provider: str
    provider_record_id: str
    name: str
    category: str | None
    categories: tuple[str, ...]
    category_hierarchy: tuple[str, ...]
    formatted_address: str | None
    latitude: float | None
    longitude: float | None
    website: str | None
    phone_number: str | None
    business_status: str | None
    source_data_release: str | None
    retrieved_at: datetime
    source_type: DiscoverySourceType
    source_url: str | None = None
    social_profile_url: str | None = None


class BusinessDiscoveryProvider(Protocol):
    def discover(
        self,
        request: LocalBusinessDiscoveryRequest,
    ) -> list[DiscoveredBusiness]: ...
