from datetime import UTC

import httpx
import pytest

from app.integrations.business_discovery import (
    LocalBusinessDiscoveryRequest,
    LocalDiscoveryArea,
)
from app.integrations.open_places import (
    OPEN_PLACES_SEARCH_URL,
    OpenPlacesProvider,
    OpenPlacesProviderError,
    create_open_places_provider,
)
from app.schemas.opportunity_models import IndustryOverlayId


class FakeResponse:
    def __init__(self, data: object, error: Exception | None = None):
        self.data = data
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.data


class FakeClient:
    def __init__(self, responses: list[FakeResponse | Exception]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def request(max_results: int = 50) -> LocalBusinessDiscoveryRequest:
    return LocalBusinessDiscoveryRequest(
        industry=IndustryOverlayId.FITNESS_GYMS,
        area=LocalDiscoveryArea(
            display_name="Lahore",
            latitude=31.5204,
            longitude=74.3587,
            radius_miles=15,
        ),
        max_results=max_results,
    )


def place(
    place_id: str = "overture:place-1",
    name: str = "FitLab Gym",
    website: str | None = "https://fitlab.example",
):
    result = {
        "place_id": place_id,
        "name": name,
        "lat": 31.5101,
        "lon": 74.3442,
        "category": "gym",
        "categories": ["gym", "fitness_centre"],
        "category_hierarchy": ["sports", "fitness", "gym"],
        "address": {
            "road": "Main Boulevard",
            "locality": "Lahore",
            "country_code": "PK",
        },
        "phone": "+92 300 1234567",
        "confidence": 0.92,
        "operating_status": "operational",
    }
    if website is not None:
        result["website"] = website
    return result


def response(
    results: list[object],
    next_offset: int | None = None,
):
    return {
        "results": results,
        "meta": {
            "data_release": "2026-08-19.0",
            "next_offset": next_offset,
        },
    }


def status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", OPEN_PLACES_SEARCH_URL)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


class TestOpenPlacesProvider:
    def test_missing_key_rejected(self):
        with pytest.raises(OpenPlacesProviderError):
            create_open_places_provider("  ")

    def test_normalizes_a_category_page_with_source_provenance(self):
        client = FakeClient([FakeResponse(response([place()]))])
        provider = OpenPlacesProvider(api_key="secret-key", client=client)

        places = provider.discover(request())

        assert len(places) == 1
        candidate = places[0]
        assert candidate.provider == "open_places"
        assert candidate.provider_record_id == "overture:place-1"
        assert candidate.name == "FitLab Gym"
        assert candidate.formatted_address == "Main Boulevard, Lahore, PK"
        assert candidate.website == "https://fitlab.example"
        assert candidate.source_data_release == "2026-08-19.0"
        assert candidate.retrieved_at.tzinfo is UTC
        assert client.calls == [
            {
                "url": OPEN_PLACES_SEARCH_URL,
                "headers": {"Authorization": "Bearer secret-key"},
                "params": {
                    "category": "gym",
                    "lat": 31.5204,
                    "lon": 74.3587,
                    "radius_mi": 15,
                    "limit": 50,
                    "offset": 0,
                },
                "timeout": 10.0,
            }
        ]

    def test_deduplicates_stable_place_ids_across_pages(self):
        client = FakeClient(
            [
                FakeResponse(
                    response(
                        [place("overture:one"), place("overture:two", "Gym Two")],
                        next_offset=50,
                    )
                ),
                FakeResponse(
                    response(
                        [
                            place("overture:two", "Gym Two"),
                            place("overture:three", "Gym Three"),
                        ]
                    )
                ),
            ]
        )
        provider = OpenPlacesProvider(api_key="key", client=client)

        places = provider.discover(request(max_results=3))

        assert [candidate.provider_record_id for candidate in places] == [
            "overture:one",
            "overture:two",
            "overture:three",
        ]
        assert client.calls[1]["params"]["offset"] == 50
        assert client.calls[1]["params"]["limit"] == 1

    def test_stops_when_provider_repeats_an_offset(self):
        client = FakeClient(
            [
                FakeResponse(response([place("overture:one")], next_offset=50)),
                FakeResponse(response([place("overture:two")], next_offset=50)),
            ]
        )
        provider = OpenPlacesProvider(api_key="key", client=client)

        places = provider.discover(request(max_results=3))

        assert [candidate.provider_record_id for candidate in places] == [
            "overture:one",
            "overture:two",
        ]
        assert len(client.calls) == 2

    def test_drops_malformed_records_and_invalid_websites(self):
        invalid_website = place("overture:two", website="not-a-url")
        client = FakeClient(
            [FakeResponse(response([{"place_id": "missing-name"}, invalid_website]))]
        )
        provider = OpenPlacesProvider(api_key="key", client=client)

        places = provider.discover(request())

        assert [candidate.provider_record_id for candidate in places] == ["overture:two"]
        assert places[0].website is None

    def test_drops_wrong_category_and_out_of_radius_records(self):
        wrong_category = place("overture:wrong-category")
        wrong_category["category"] = "restaurant"
        wrong_category["categories"] = ["restaurant"]
        wrong_category["category_hierarchy"] = ["food_and_drink", "restaurant"]
        out_of_radius = place("overture:out-of-radius")
        out_of_radius["lat"] = 33.6844
        out_of_radius["lon"] = 73.0479
        client = FakeClient(
            [
                FakeResponse(
                    response(
                        [
                            wrong_category,
                            out_of_radius,
                            place("overture:accepted"),
                        ]
                    )
                )
            ]
        )
        provider = OpenPlacesProvider(api_key="key", client=client)

        places = provider.discover(request())

        assert [candidate.provider_record_id for candidate in places] == [
            "overture:accepted"
        ]

    def test_timeout_retries_then_fails(self):
        client = FakeClient(
            [httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")]
        )
        provider = OpenPlacesProvider(api_key="key", client=client, retry_attempts=2)

        with pytest.raises(OpenPlacesProviderError, match="timed out"):
            provider.discover(request())
        assert len(client.calls) == 2

    def test_quota_and_rate_limit_have_honest_errors(self):
        for status_code, expected_message in [
            (402, "quota is exhausted"),
            (429, "rate limit was reached"),
        ]:
            provider = OpenPlacesProvider(
                api_key="key",
                client=FakeClient([FakeResponse({}, status_error(status_code))]),
            )
            with pytest.raises(OpenPlacesProviderError, match=expected_message):
                provider.discover(request())

    def test_invalid_response_shape_is_an_honest_provider_error(self):
        provider = OpenPlacesProvider(
            api_key="key",
            client=FakeClient([FakeResponse([place()])]),
        )

        with pytest.raises(OpenPlacesProviderError, match="invalid response"):
            provider.discover(request())
