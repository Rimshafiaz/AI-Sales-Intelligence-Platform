from dataclasses import dataclass
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from time import sleep
from urllib.parse import urlparse

import httpx

from app.integrations.business_discovery import (
    DiscoveredBusiness,
    LocalBusinessDiscoveryRequest,
)
from app.schemas.opportunity_models import IndustryOverlayId


OPEN_PLACES_SEARCH_URL = "https://api.openplacesapi.com/v1/places"
OPEN_PLACES_CATEGORIES: dict[IndustryOverlayId, str] = {
    IndustryOverlayId.BEAUTY_WELLNESS: "beauty_salon",
    IndustryOverlayId.RESTAURANTS_CAFES: "restaurant",
    IndustryOverlayId.FITNESS_GYMS: "gym",
    IndustryOverlayId.BOUTIQUES_RETAIL: "clothing_store",
    IndustryOverlayId.DENTAL_SELECTED_CLINICS: "dental_clinic",
}
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRY_ATTEMPTS = 2
MAX_RESULTS = 100
MAX_PAGE_SIZE = 50


class OpenPlacesProviderError(Exception):
    pass


@dataclass(frozen=True)
class OpenPlacesPage:
    results: tuple[DiscoveredBusiness, ...]
    next_offset: int | None


class OpenPlacesProvider:
    def __init__(
        self,
        api_key: str,
        client: object | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Open Places API key cannot be blank.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1.")

        self.api_key = api_key
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts

    def discover(
        self,
        request: LocalBusinessDiscoveryRequest,
    ) -> list[DiscoveredBusiness]:
        if not 1 <= request.max_results <= MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}.")

        category = OPEN_PLACES_CATEGORIES[request.industry]
        candidates: list[DiscoveredBusiness] = []
        seen_place_ids: set[str] = set()
        seen_offsets: set[int] = {0}
        offset = 0

        while len(candidates) < request.max_results:
            page_size = min(MAX_PAGE_SIZE, request.max_results - len(candidates))
            page = self._search_category(
                category=category,
                request=request,
                limit=page_size,
                offset=offset,
            )

            for candidate in page.results:
                if candidate.provider_record_id in seen_place_ids:
                    continue
                seen_place_ids.add(candidate.provider_record_id)
                candidates.append(candidate)
                if len(candidates) == request.max_results:
                    return candidates

            if page.next_offset is None or page.next_offset in seen_offsets:
                return candidates
            seen_offsets.add(page.next_offset)
            offset = page.next_offset

        return candidates

    def _search_category(
        self,
        category: str,
        request: LocalBusinessDiscoveryRequest,
        limit: int,
        offset: int,
    ) -> OpenPlacesPage:
        params = {
            "category": category,
            "lat": request.area.latitude,
            "lon": request.area.longitude,
            "radius_mi": request.area.radius_miles,
            "limit": limit,
            "offset": offset,
        }
        data = self._get(params)
        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            raw_results = []
        meta = data.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        data_release = self._clean_text(meta.get("data_release"))
        next_offset = self._offset(meta.get("next_offset"))
        retrieved_at = datetime.now(UTC)
        results: list[DiscoveredBusiness] = []
        for raw_result in raw_results:
            if not self._matches_category(raw_result, category):
                continue
            candidate = self._normalize_candidate(
                raw_result,
                data_release=data_release,
                retrieved_at=retrieved_at,
            )
            if candidate is None or not self._is_within_area(candidate, request):
                continue
            results.append(candidate)
        return OpenPlacesPage(results=tuple(results), next_offset=next_offset)

    def _get(self, params: dict[str, object]) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(self.retry_attempts):
            try:
                if self.client is None:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.get(
                            OPEN_PLACES_SEARCH_URL,
                            headers=headers,
                            params=params,
                        )
                else:
                    response = self.client.get(
                        OPEN_PLACES_SEARCH_URL,
                        headers=headers,
                        params=params,
                        timeout=self.timeout_seconds,
                    )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise OpenPlacesProviderError(
                        "Open Places returned an invalid response."
                    )
                return data
            except OpenPlacesProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt == self.retry_attempts - 1:
                    raise OpenPlacesProviderError(
                        "Open Places request timed out. Please try again."
                    ) from error
                sleep(0.25)
            except httpx.HTTPStatusError as error:
                status_code = error.response.status_code
                if status_code == 402:
                    raise OpenPlacesProviderError(
                        "Open Places quota is exhausted. Please try again later."
                    ) from error
                if status_code == 429:
                    raise OpenPlacesProviderError(
                        "Open Places rate limit was reached. Please try again later."
                    ) from error
                raise OpenPlacesProviderError(
                    "Open Places request failed. Check provider configuration and try again."
                ) from error
            except (httpx.HTTPError, ValueError, TypeError) as error:
                raise OpenPlacesProviderError(
                    "Open Places request failed. Check provider configuration and try again."
                ) from error

        raise OpenPlacesProviderError("Open Places request failed. Please try again.")

    @staticmethod
    def _normalize_candidate(
        raw_result: object,
        data_release: str | None,
        retrieved_at: datetime,
    ) -> DiscoveredBusiness | None:
        if not isinstance(raw_result, dict):
            return None

        place_id = OpenPlacesProvider._clean_text(raw_result.get("place_id"))
        name = OpenPlacesProvider._clean_text(raw_result.get("name"))
        if place_id is None or name is None:
            return None

        raw_categories = raw_result.get("categories")
        categories = (
            tuple(
                item.strip()
                for item in raw_categories
                if isinstance(item, str) and item.strip()
            )
            if isinstance(raw_categories, list)
            else ()
        )
        raw_hierarchy = raw_result.get("category_hierarchy")
        category_hierarchy = (
            tuple(
                item.strip()
                for item in raw_hierarchy
                if isinstance(item, str) and item.strip()
            )
            if isinstance(raw_hierarchy, list)
            else ()
        )
        return DiscoveredBusiness(
            provider="open_places",
            provider_record_id=place_id,
            name=name,
            category=OpenPlacesProvider._clean_text(raw_result.get("category")),
            categories=categories,
            category_hierarchy=category_hierarchy,
            formatted_address=OpenPlacesProvider._format_address(
                raw_result.get("address")
            ),
            latitude=OpenPlacesProvider._number(raw_result.get("lat")),
            longitude=OpenPlacesProvider._number(raw_result.get("lon")),
            website=OpenPlacesProvider._http_url(raw_result.get("website")),
            phone_number=OpenPlacesProvider._clean_text(raw_result.get("phone")),
            business_status=OpenPlacesProvider._clean_text(
                raw_result.get("operating_status")
            ),
            source_data_release=data_release,
            retrieved_at=retrieved_at,
        )

    @staticmethod
    def _matches_category(raw_result: object, expected_category: str) -> bool:
        if not isinstance(raw_result, dict):
            return False
        category_values = [
            raw_result.get("category"),
            *(raw_result.get("categories") or []),
            *(raw_result.get("category_hierarchy") or []),
        ]
        return expected_category in category_values

    @staticmethod
    def _is_within_area(
        candidate: DiscoveredBusiness,
        request: LocalBusinessDiscoveryRequest,
    ) -> bool:
        if candidate.latitude is None or candidate.longitude is None:
            return False
        return (
            OpenPlacesProvider._distance_miles(
                request.area.latitude,
                request.area.longitude,
                candidate.latitude,
                candidate.longitude,
            )
            <= request.area.radius_miles
        )

    @staticmethod
    def _distance_miles(
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> float:
        latitude_delta = radians(destination_latitude - origin_latitude)
        longitude_delta = radians(destination_longitude - origin_longitude)
        origin_latitude_radians = radians(origin_latitude)
        destination_latitude_radians = radians(destination_latitude)
        haversine = (
            sin(latitude_delta / 2) ** 2
            + cos(origin_latitude_radians)
            * cos(destination_latitude_radians)
            * sin(longitude_delta / 2) ** 2
        )
        return 3958.7613 * 2 * asin(sqrt(haversine))

    @staticmethod
    def _format_address(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        parts = [
            OpenPlacesProvider._clean_text(value.get(key))
            for key in (
                "house_number",
                "road",
                "neighbourhood",
                "locality",
                "region",
                "postcode",
                "country_code",
            )
        ]
        clean_parts = list(dict.fromkeys(part for part in parts if part))
        return ", ".join(clean_parts) or None

    @staticmethod
    def _offset(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    @staticmethod
    def _number(value: object) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _clean_text(value: object) -> str | None:
        return value.strip() or None if isinstance(value, str) else None

    @staticmethod
    def _http_url(value: object) -> str | None:
        clean_value = OpenPlacesProvider._clean_text(value)
        if clean_value is None:
            return None
        parsed_url = urlparse(clean_value)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return None
        return clean_value


def create_open_places_provider(api_key: str | None) -> OpenPlacesProvider:
    if api_key is None or not api_key.strip():
        raise OpenPlacesProviderError(
            "Open Places is not configured. Set OPEN_PLACES_API_KEY."
        )
    return OpenPlacesProvider(api_key)
