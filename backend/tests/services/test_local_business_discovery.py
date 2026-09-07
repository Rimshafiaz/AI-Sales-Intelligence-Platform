from datetime import UTC, datetime

import pytest

from app.integrations.business_discovery import (
    DiscoveredBusiness,
    LocalBusinessDiscoveryRequest,
)
from app.schemas.company_discovery import CompanyDiscoveryRequest
from app.schemas.opportunity_models import IndustryOverlayId
from app.services.local_business_discovery import (
    LocalBusinessDiscoveryError,
    discover_local_businesses,
    resolve_area,
    resolve_industry,
)


class RecordingProvider:
    def __init__(self, businesses: list[DiscoveredBusiness]):
        self.businesses = businesses
        self.requests: list[LocalBusinessDiscoveryRequest] = []

    def discover(self, request: LocalBusinessDiscoveryRequest) -> list[DiscoveredBusiness]:
        self.requests.append(request)
        return self.businesses


def criteria(**overrides: object) -> CompanyDiscoveryRequest:
    values: dict[str, object] = {
        "offering": "Website redesign",
        "desired_outcome": "Find businesses worth researching.",
        "business_category": "Gyms",
        "location": "Lahore",
    }
    values.update(overrides)
    return CompanyDiscoveryRequest(**values)


def business() -> DiscoveredBusiness:
    return DiscoveredBusiness(
        provider="open_places",
        provider_record_id="overture:fitlab",
        name="FitLab Gym",
        category="gym",
        categories=("gym",),
        category_hierarchy=("sports", "fitness", "gym"),
        formatted_address="Gulberg, Lahore, PK",
        latitude=31.5,
        longitude=74.3,
        website="https://fitlab.example",
        phone_number="+92 300 1234567",
        business_status="operational",
        source_data_release="2026-08-19.0",
        retrieved_at=datetime(2026, 9, 7, tzinfo=UTC),
    )


class TestLocalBusinessDiscovery:
    def test_maps_industry_and_lahore_pilot_area_to_provider_request(self):
        provider = RecordingProvider([business()])

        response = discover_local_businesses(criteria(), provider)

        assert provider.requests[0].industry is IndustryOverlayId.FITNESS_GYMS
        assert provider.requests[0].area.latitude == 31.5204
        assert provider.requests[0].area.longitude == 74.3587
        assert provider.requests[0].area.radius_miles == 15
        assert provider.requests[0].max_results == 50
        candidate = response.candidates[0]
        assert candidate.company_name == "FitLab Gym"
        assert candidate.source_provider == "open_places"
        assert candidate.source_record_id == "overture:fitlab"
        assert candidate.source_data_release == "2026-08-19.0"
        assert candidate.website_verification_state == "listed_unverified"
        assert candidate.fit_score is None
        assert "not been qualified" in candidate.match_explanation

    def test_caller_coordinates_enable_an_unconfigured_location(self):
        area = resolve_area(
            criteria(location="Karachi", latitude=24.8607, longitude=67.0011)
        )

        assert area.display_name == "Karachi"
        assert area.latitude == 24.8607
        assert area.longitude == 67.0011

    def test_unconfigured_location_requires_explicit_coordinates(self):
        with pytest.raises(LocalBusinessDiscoveryError, match="latitude and longitude"):
            resolve_area(criteria(location="Karachi"))

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Beauty salons", IndustryOverlayId.BEAUTY_WELLNESS),
            ("Restaurants", IndustryOverlayId.RESTAURANTS_CAFES),
            ("Fitness studios", IndustryOverlayId.FITNESS_GYMS),
            ("Fashion boutiques", IndustryOverlayId.BOUTIQUES_RETAIL),
            ("Dentists", IndustryOverlayId.DENTAL_SELECTED_CLINICS),
        ],
    )
    def test_maps_only_supported_industry_families(
        self,
        value: str,
        expected: IndustryOverlayId,
    ):
        assert resolve_industry(value) is expected

    def test_rejects_an_unvalidated_industry_family(self):
        with pytest.raises(LocalBusinessDiscoveryError, match="currently supports"):
            resolve_industry("Law firms")

    def test_does_not_assume_every_clinic_is_a_dental_clinic(self):
        with pytest.raises(LocalBusinessDiscoveryError, match="currently supports"):
            resolve_industry("Skin clinics")

    def test_request_rejects_partial_coordinates(self):
        with pytest.raises(ValueError, match="both latitude and longitude"):
            criteria(latitude=31.5204)
