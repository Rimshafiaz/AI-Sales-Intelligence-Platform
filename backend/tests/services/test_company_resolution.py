from app.integrations.search_provider import CollectedSource
from app.schemas.opportunity_models import IdentityState
from app.services.company_resolution import CompanyWebsiteResolver


class FakeSearchProvider:
    def __init__(self, sources: list[CollectedSource]):
        self.sources = sources
        self.queries: list[str] = []

    def search(self, query: str) -> list[CollectedSource]:
        self.queries.append(query)
        return self.sources


def source(url: str, title: str, excerpt: str | None = None) -> CollectedSource:
    return CollectedSource(url=url, title=title, excerpt=excerpt)


class TestCompanyWebsiteResolver:
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

        resolved = CompanyWebsiteResolver(provider).resolve(
            "Glow Salon",
            "Lahore",
            "https://glowsalon.com",
        )

        assert resolved.identity_state is IdentityState.NEEDS_REVIEW
        assert resolved.website == "https://glowsalon.com"
