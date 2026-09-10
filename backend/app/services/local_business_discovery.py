from app.integrations.business_discovery import (
    BusinessDiscoveryProvider,
    DiscoveredBusiness,
    LocalBusinessDiscoveryRequest,
    LocalDiscoveryArea,
)
from app.integrations.geocoding import GeocodingProvider, NominatimGeocodingProvider
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    DiscoveredCompanyCandidate,
)
from app.schemas.opportunity_models import IndustryOverlayId


class LocalBusinessDiscoveryError(Exception):
    pass


INDUSTRY_ALIASES: dict[IndustryOverlayId, tuple[str, ...]] = {
    IndustryOverlayId.BEAUTY_WELLNESS: (
        "beauty",
        "salon",
        "salons",
        "spa",
        "wellness",
    ),
    IndustryOverlayId.RESTAURANTS_CAFES: (
        "restaurant",
        "restaurants",
        "cafe",
        "cafes",
    ),
    IndustryOverlayId.FITNESS_GYMS: (
        "gym",
        "gyms",
        "fitness",
    ),
    IndustryOverlayId.BOUTIQUES_RETAIL: (
        "boutique",
        "boutiques",
        "retail",
        "clothing",
        "fashion",
    ),
    IndustryOverlayId.DENTAL_SELECTED_CLINICS: (
        "dental",
        "dentist",
        "dentists",
    ),
}


def discover_local_businesses(
    criteria: CompanyDiscoveryRequest,
    provider: BusinessDiscoveryProvider,
) -> CompanyDiscoveryResponse:
    businesses = collect_local_businesses(criteria, provider)
    return CompanyDiscoveryResponse(
        candidates=[
            business_to_candidate(criteria, business)
            for business in businesses
        ]
    )


def collect_local_businesses(
    criteria: CompanyDiscoveryRequest,
    provider: BusinessDiscoveryProvider,
    geocoding_provider: GeocodingProvider | None = None,
) -> list[DiscoveredBusiness]:
    request = LocalBusinessDiscoveryRequest(
        industry=resolve_industry(criteria.industry),
        area=resolve_area(criteria, geocoding_provider),
        max_results=criteria.max_results,
    )
    return provider.discover(request)


def resolve_industry(value: str) -> IndustryOverlayId:
    normalized = value.casefold().strip()
    for industry, aliases in INDUSTRY_ALIASES.items():
        if normalized in aliases or any(alias in normalized for alias in aliases):
            return industry
    raise LocalBusinessDiscoveryError(
        "Local discovery currently supports Beauty & wellness, Restaurants & cafes, "
        "Fitness & gyms, Boutiques & retail, and Dental & selected clinics."
    )


def resolve_area(
    criteria: CompanyDiscoveryRequest,
    geocoding_provider: GeocodingProvider | None = None,
) -> LocalDiscoveryArea:
    if criteria.latitude is not None and criteria.longitude is not None:
        return LocalDiscoveryArea(
            display_name=criteria.location,
            latitude=criteria.latitude,
            longitude=criteria.longitude,
            radius_miles=criteria.radius_miles,
        )

    provider = geocoding_provider or NominatimGeocodingProvider()
    location_text = criteria.location or ""
    resolved = provider.geocode(location_text)
    if resolved is None:
        raise LocalBusinessDiscoveryError(
            f"Could not resolve location '{location_text}'. Try a city and "
            "country, e.g. Karachi, Pakistan."
        )
    return LocalDiscoveryArea(
        display_name=resolved.display_name,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        radius_miles=criteria.radius_miles,
    )


def business_to_candidate(
    criteria: CompanyDiscoveryRequest,
    business: DiscoveredBusiness,
) -> DiscoveredCompanyCandidate:
    return DiscoveredCompanyCandidate(
        company_name=business.name,
        website=business.website,
        industry=business.category or criteria.industry,
        short_description=business.formatted_address,
        match_explanation=(
            "Open Places returned this physical business listing for the requested "
            "category and location. It has not been qualified as an opportunity yet."
        ),
        source_provider=business.provider,
        source_record_id=business.provider_record_id,
        source_retrieved_at=business.retrieved_at,
        source_data_release=business.source_data_release,
        formatted_address=business.formatted_address,
        business_status=business.business_status,
        phone_number=business.phone_number,
        website_verification_state=(
            "listed_unverified" if business.website is not None else None
        ),
    )
