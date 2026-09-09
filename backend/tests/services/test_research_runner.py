from app.services.research_runner import _resolution_location


def test_prefers_campaign_geography_over_provider_formatted_address():
    location = _resolution_location(
        {},
        {"location": "Lahore"},
        {"formatted_address": "Tehsil Lahore Cantonment, PK"},
    )

    assert location == "Lahore"


def test_prefers_explicit_research_location_over_campaign_geography():
    location = _resolution_location(
        {"location": "Gulberg, Lahore"},
        {"location": "Lahore"},
        {"formatted_address": "Tehsil Lahore Cantonment, PK"},
    )

    assert location == "Gulberg, Lahore"
