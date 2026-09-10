from app.services.identity_resolution import (
    IdentityStatus,
    domain_conflicts_with_name,
    identity_name_score,
    normalize_company_name,
    resolve_source_identity,
)


def resolve(
    name: str = "Al-Ghani Dental and Medical Centre",
    location: str | None = "Lahore",
    phone: str | None = None,
    url: str = "https://alghanimedical.com",
    title: str = "Al Ghani Medical - Dentist, Physiotherapist & Aesthetician in Lahore",
    excerpt: str = "",
):
    return resolve_source_identity(
        candidate_name=name,
        candidate_location=location,
        candidate_phone=phone,
        source_url=url,
        source_name=title,
        source_text=excerpt,
    )


def test_the_al_ghani_official_site_is_confirmed():
    resolution = resolve()
    assert resolution.status is IdentityStatus.CONFIRMED
    assert resolution.domain_match is True
    assert resolution.name_score >= 60


def test_spelling_variant_centre_center_matches():
    score = identity_name_score("ABC Dental Centre", "ABC Dental Center")
    assert score >= 95


def test_short_trading_name_matches_with_domain_and_location():
    resolution = resolve(
        name="Smith & Sons Medical Clinic",
        location="Lahore",
        url="https://smithandsonsmedical.com",
        title="Smith and Sons Medical - Lahore",
    )
    assert resolution.status in {IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE}
    assert resolution.domain_match is True


def test_brand_root_with_extra_entity_word_is_not_confirmed():
    resolution = resolve(
        name="Al Ghani Medical",
        url="https://alghanistore.com",
        title="Al Ghani Medical Store",
        location=None,
    )
    assert resolution.status is not IdentityStatus.CONFIRMED
    assert resolution.extra_entity_word == "store"


def test_brand_root_domain_conflict_is_detected():
    assert domain_conflicts_with_name("alghanistore", ["al", "ghani", "medical"]) == "store"
    assert domain_conflicts_with_name("alghanimedical", ["al", "ghani", "medical"]) is None


def test_location_conflict_never_confirms():
    resolution = resolve(
        name="Al Ghani Medical",
        location="Lahore",
        url="https://alghanimedical.com",
        title="Al Ghani Medical - best dental care in Karachi",
    )
    assert resolution.status is not IdentityStatus.CONFIRMED
    assert resolution.location_match is False
    assert resolution.status is IdentityStatus.AMBIGUOUS


def test_exact_contact_match_confirms_different_name():
    resolution = resolve(
        name="Dr Sahib Dental Care",
        location=None,
        phone="+92 300 1234567",
        url="https://some-directory.pk/listing",
        title="Dental clinic in Lahore - book now",
        excerpt="Dr Sahib Dental Care, 12 Main Blvd. Call 0300-1234567 today.",
    )
    assert resolution.contact_match is True
    assert resolution.status is IdentityStatus.CONFIRMED


def test_completely_different_business_is_rejected():
    resolution = resolve(
        name="Al Ghani Dental and Medical Centre",
        url="https://glow-salon-lahore.com",
        title="Glow Beauty Salon Lahore",
        excerpt="Hair and beauty services.",
    )
    assert resolution.status is IdentityStatus.REJECTED


def test_normalization_handles_ampersands_and_punctuation():
    assert (
        normalize_company_name("Al-Ghani Dental & Medical Centre, Ltd.")
        == "al ghani dental and medical center"
    )
