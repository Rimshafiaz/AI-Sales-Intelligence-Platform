from app.integrations.search_provider import CollectedSource
from app.integrations.website_metadata import WebsiteIdentityPage
from app.schemas.opportunity_models import IdentityState
from app.services.company_resolution import CompanyWebsiteResolver


class FakeSearchProvider:
    def __init__(self, sources: list[CollectedSource]):
        self.sources = sources
        self.queries: list[str] = []

    def search(self, query: str) -> list[CollectedSource]:
        self.queries.append(query)
        return self.sources


class FakeWebsiteCollector:
    def __init__(self, pages: tuple[WebsiteIdentityPage, ...] = ()):
        self.pages = pages
        self.urls: list[str] = []

    def collect_identity_pages(self, website: str) -> tuple[WebsiteIdentityPage, ...]:
        self.urls.append(website)
        return self.pages


def identity_page(
    url: str = "https://glowsalon.com/",
    text: str = "Glow Salon in Lahore.",
) -> WebsiteIdentityPage:
    return WebsiteIdentityPage(
        url=url,
        title=None,
        description=None,
        identity_text=text,
        identity_links=(),
    )


def source(url: str, title: str, excerpt: str | None = None) -> CollectedSource:
    return CollectedSource(url=url, title=title, excerpt=excerpt)


class TestCompanyWebsiteResolver:
    def test_accepts_acronym_domain_only_with_full_name_location_corroboration(self):
        provider = FakeSearchProvider(
            [
                source(
                    "https://aadic.pk/",
                    "AADIC",
                    "General dentistry and implantology services.",
                ),
                source(
                    "https://www.instagram.com/aadic.pk",
                    "Aesthetics & Dental Implantology Centre (@aadic.pk)",
                    "Karachi clinic. Website: www.aadic.pk. Call 0300 2685875.",
                ),
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve(
            "Aesthetics & Dental Implantology Centre",
            "Karachi",
            phone_number="0300 2685875",
        )

        assert resolved.identity_state is IdentityState.VERIFIED
        assert resolved.website == "https://aadic.pk"
        assert "acronym" in resolved.reason

    def test_does_not_accept_unrelated_acronym_domain_without_corroboration(self):
        provider = FakeSearchProvider(
            [
                source("https://aadic.pk/", "AADIC", "Dental services."),
                source(
                    "https://facebook.com/aadic.pk",
                    "Aesthetics & Dental Implantology Centre",
                    "Karachi dental clinic.",
                ),
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve(
            "Aesthetics & Dental Implantology Centre",
            "Karachi",
        )

        assert resolved.website is None

    def test_acronym_domain_corroboration_rejects_conflicting_location_or_contact(self):
        sources = [
            source("https://aadic.pk/", "AADIC", "Dental services."),
            source(
                "https://www.instagram.com/aadic.pk",
                "Aesthetics & Dental Implantology Centre (@aadic.pk)",
                "Lahore clinic. Website: www.aadic.pk. Call 0300 9999999.",
            ),
        ]

        resolved = CompanyWebsiteResolver(FakeSearchProvider(sources)).resolve(
            "Aesthetics & Dental Implantology Centre",
            "Karachi",
            phone_number="0300 2685875",
        )

        assert resolved.website is None

    def test_confirms_business_identity_without_declaring_a_website(self):
        provider = FakeSearchProvider(
            [
                source(
                    "https://facebook.com/glowsalonlahore",
                    "Glow Salon Lahore",
                    "Glow Salon in Lahore. Call +92 300 1234567.",
                )
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve(
            "Glow Salon",
            "Lahore",
            phone_number="+92 300 1234567",
        )

        assert resolved.identity_state is IdentityState.VERIFIED
        assert resolved.website is None
        assert resolved.source is not None
        assert "no official website was verified" in resolved.reason.lower()

    def test_probable_identity_source_does_not_become_verified(self):
        provider = FakeSearchProvider(
            [
                source(
                    "https://facebook.com/glowsalonlahore",
                    "Glow Salon Lahore",
                    "Beauty services in Lahore.",
                )
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve("Glow Salon", "Lahore")

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
        assert resolved.website is None

    def test_verifies_one_name_and_location_supported_website(self):
        provider = FakeSearchProvider(
            [
                source(
                    "https://glowsalon.com/services",
                    "Glow Salon | Lahore appointments",
                    "Glow Salon in Lahore offers hair and beauty services.",
                )
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve("Glow Salon", "Lahore")

        assert resolved.identity_state is IdentityState.VERIFIED
        assert resolved.website == "https://glowsalon.com"
        assert resolved.source is not None
        assert provider.queries == ['"Glow Salon" Lahore official website']

    def test_requires_review_when_location_is_not_supported_by_the_source(self):
        provider = FakeSearchProvider(
            [source("https://glowsalon.com", "Glow Salon | Appointments")]
        )

        resolved = CompanyWebsiteResolver(provider).resolve("Glow Salon", "Lahore")

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
        assert resolved.website == "https://glowsalon.com"

    def test_requires_review_when_two_official_domains_match_the_same_name(self):
        provider = FakeSearchProvider(
            [
                source("https://glowsalon.com", "Glow Salon Lahore"),
                source("https://glowsalon.pk", "Glow Salon Lahore"),
            ]
        )

        resolved = CompanyWebsiteResolver(provider).resolve("Glow Salon", "Lahore")

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
        assert resolved.website is None

    def test_user_supplied_website_still_needs_matching_source_evidence(self):
        provider = FakeSearchProvider(
            [source("https://other.example", "Glow Salon Lahore")]
        )
        collector = FakeWebsiteCollector()

        resolved = CompanyWebsiteResolver(provider, collector).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com",
        )

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
        assert resolved.website is None

    def test_verifies_supplied_website_with_business_and_location_on_the_site(self):
        collector = FakeWebsiteCollector(
            (identity_page(text="Glow Salon appointments in Lahore."),)
        )

        resolved = CompanyWebsiteResolver(
            FakeSearchProvider([]),
            collector,
        ).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com/services",
        )

        assert resolved.identity_state is IdentityState.VERIFIED
        assert resolved.website == "https://glowsalon.com"
        assert resolved.source is not None
        assert resolved.source.provider == "official_website"
        assert collector.urls == ["https://glowsalon.com"]

    def test_verifies_supplied_website_with_business_and_matching_phone(self):
        collector = FakeWebsiteCollector(
            (identity_page(text="Glow Salon. Call 03001234567 to book."),)
        )

        resolved = CompanyWebsiteResolver(
            FakeSearchProvider([]),
            collector,
        ).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com",
            "+923001234567",
        )

        assert resolved.identity_state is IdentityState.VERIFIED

    def test_does_not_join_unrelated_page_digits_into_a_phone_match(self):
        assert not CompanyWebsiteResolver._phone_numbers_match(
            "+923001234567",
            "Call 0300123 for support or 4567 for bookings.",
        )

    def test_verifies_from_a_traceable_same_site_contact_page(self):
        collector = FakeWebsiteCollector(
            (
                identity_page(text="Welcome to Glow Salon."),
                identity_page(
                    url="https://glowsalon.com/contact",
                    text="Glow Salon Lahore. Call 03001234567.",
                ),
            )
        )

        resolved = CompanyWebsiteResolver(
            FakeSearchProvider([]),
            collector,
        ).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com",
            "+923001234567",
        )

        assert resolved.identity_state is IdentityState.VERIFIED
        assert resolved.source is not None
        assert str(resolved.source.source_url) == "https://glowsalon.com/contact"

    def test_keeps_name_only_website_match_in_review(self):
        collector = FakeWebsiteCollector(
            (identity_page(text="Glow Salon appointments and services."),)
        )

        resolved = CompanyWebsiteResolver(
            FakeSearchProvider([]),
            collector,
        ).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com",
        )

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
