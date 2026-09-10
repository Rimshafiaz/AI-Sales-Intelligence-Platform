"""Small provider abstraction for resolving free-text locations to
coordinates. Production uses Nominatim (OpenStreetMap) — free, keyless,
deterministic. Tests mock the abstraction."""

from dataclasses import dataclass
from urllib.parse import quote

import httpx


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AI-Sales-Intelligence-Platform/1.0 (geocoding)"
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class ResolvedLocation:
    latitude: float
    longitude: float
    display_name: str


class GeocodingProvider:
    def geocode(self, query: str) -> ResolvedLocation | None:
        raise NotImplementedError


class NominatimGeocodingProvider:
    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    def geocode(self, query: str) -> ResolvedLocation | None:
        clean_query = query.strip()
        if not clean_query:
            return None
        url = (
            f"{NOMINATIM_SEARCH_URL}?q={quote(clean_query)}"
            "&format=json&limit=1"
        )
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return None

        results = payload if isinstance(payload, list) else []
        first = results[0] if results else None
        if not isinstance(first, dict):
            return None
        try:
            latitude = float(first["lat"])
            longitude = float(first["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        display_name = first.get("display_name")
        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            display_name=(
                display_name.strip()
                if isinstance(display_name, str) and display_name.strip()
                else clean_query
            ),
        )
