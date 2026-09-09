import pytest

from app.schemas.opportunity_models import EvidenceSignalType, IndustryOverlayId
from app.services.industry_conversion_paths import analyze_conversion_paths


CASES = {
    IndustryOverlayId.RESTAURANTS_CAFES: [
        (["menu", "contact"], False), (["menu", "location"], False),
        (["menu", "reservation"], False), (["order online", "contact"], False),
        (["delivery", "location"], False), (["pickup", "reserve"], False),
        (["takeaway", "directions"], False), (["menu", "tel:"], False),
        (["menu"], True), (["reservation"], True), (["contact"], True),
        (["about"], True), ([], True), (["shop", "contact"], True),
        (["appointment", "location"], True),
    ],
    IndustryOverlayId.FITNESS_GYMS: [
        (["trial"], False), (["free pass"], False), (["guest pass"], False),
        (["membership"], False), (["join"], False), (["enrol"], False),
        (["classes"], False), (["timetable"], False), (["trainer"], False),
        (["coach"], False), (["contact"], False), (["tel:"], False),
        (["menu"], True), (["appointment"], True), ([], True),
    ],
    IndustryOverlayId.BOUTIQUES_RETAIL: [
        (["shop"], False), (["store"], False), (["products"], False),
        (["collection"], False), (["catalog"], False), (["catalogue"], False),
        (["contact"], False), (["mailto:"], False), (["wa.me"], False),
        (["instagram.com"], False), (["facebook.com"], False),
        (["tiktok.com"], False), (["menu"], True), (["appointment"], True),
        ([], True),
    ],
    IndustryOverlayId.DENTAL_SELECTED_CLINICS: [
        (["services", "appointment", "location"], False),
        (["treatments", "contact"], False),
        (["procedures", "mailto:"], False),
        (["services", "book now", "directions"], False),
        (["treatment", "schedule", "maps"], False),
        (["services", "appointment"], True),
        (["services", "location"], True),
        (["appointment", "location"], True),
        (["contact"], True), (["services"], True), (["location"], True),
        (["menu", "contact"], True), (["shop", "appointment"], True),
        (["trainer", "location"], True), ([], True),
    ],
}


@pytest.mark.parametrize(
    ("industry", "terms", "expects_finding"),
    [
        (industry, terms, expects_finding)
        for industry, cases in CASES.items()
        for terms, expects_finding in cases
    ],
)
def test_industry_conversion_path_matrix(industry, terms, expects_finding):
    links = tuple((f"https://example.com/{index}", term) for index, term in enumerate(terms))

    finding = analyze_conversion_paths(industry, links)

    assert (finding is not None) is expects_finding


@pytest.mark.parametrize(
    ("industry", "signal_type"),
    [
        (IndustryOverlayId.RESTAURANTS_CAFES, EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED),
        (IndustryOverlayId.FITNESS_GYMS, EvidenceSignalType.WEBSITE_FITNESS_ENQUIRY_PATH_NOT_OBSERVED),
        (IndustryOverlayId.BOUTIQUES_RETAIL, EvidenceSignalType.WEBSITE_RETAIL_PRODUCT_PATH_NOT_OBSERVED),
        (IndustryOverlayId.DENTAL_SELECTED_CLINICS, EvidenceSignalType.WEBSITE_CLINIC_PATIENT_PATH_INCOMPLETE),
    ],
)
def test_industry_conversion_findings_use_the_correct_signal(industry, signal_type):
    finding = analyze_conversion_paths(industry, ())

    assert finding is not None
    assert finding.signal_type is signal_type
