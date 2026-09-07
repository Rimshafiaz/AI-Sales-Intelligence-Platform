from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.opportunity_models import IndustryOverlayId


@dataclass(frozen=True)
class LocalDiscoveryArea:
    display_name: str
    latitude: float
    longitude: float
    radius_miles: float


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


class BusinessDiscoveryProvider(Protocol):
    def discover(
        self,
        request: LocalBusinessDiscoveryRequest,
    ) -> list[DiscoveredBusiness]: ...
