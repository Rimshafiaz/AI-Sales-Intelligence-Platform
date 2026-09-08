from datetime import UTC, datetime

from app.integrations.business_discovery import DiscoveredBusiness, DiscoverySourceType
from app.integrations.serper import SerperSearchResult
from app.schemas.company_discovery import CompanyDiscoveryRequest
from app.services.candidate_pool import merge_candidate_pool
from app.services.web_candidate_discovery import (
    build_social_queries,
    canonical_social_profile_url,
    social_result_to_candidate,
    web_result_to_candidate,
)


def criteria():
    return CompanyDiscoveryRequest(offering="Website redesign", desired_outcome="Find candidates.", business_category="Boutiques", location="Lahore")


def result(title: str, url: str):
    return SerperSearchResult(title=title, url=url, snippet=None, retrieved_at=datetime(2026, 9, 7, tzinfo=UTC))


def local_business(website: str = "https://glow.example"):
    return DiscoveredBusiness(provider="open_places", provider_record_id="overture:glow", name="Glow Boutique", category="clothing_store", categories=("clothing_store",), category_hierarchy=(), formatted_address="Lahore, PK", latitude=31.52, longitude=74.35, website=website, phone_number=None, business_status="operational", source_data_release=None, retrieved_at=datetime(2026, 9, 7, tzinfo=UTC), source_type=DiscoverySourceType.LOCAL_PLACES)


class TestWebCandidateDiscovery:
    def test_rejects_directories_and_keeps_possible_websites_unverified(self):
        assert web_result_to_candidate(result("Directory", "https://yelp.com/biz/x")) is None
        candidate = web_result_to_candidate(result("Glow Boutique", "https://www.glow.example/catalog"))
        assert candidate is not None
        assert candidate.website == "https://www.glow.example/"
        assert candidate.source_type is DiscoverySourceType.WEB_SEARCH

    def test_social_profile_filter_rejects_content_urls_and_normalizes_profiles(self):
        assert canonical_social_profile_url("https://www.instagram.com/p/post/") is None
        assert canonical_social_profile_url("https://www.tiktok.com/brand") is None
        candidate = social_result_to_candidate(result("Glow Boutique", "https://www.instagram.com/glowboutique/?x=1"))
        assert candidate is not None
        assert candidate.social_profile_url == "https://www.instagram.com/glowboutique"
        assert candidate.website is None

    def test_social_query_scope_is_bounded_to_approved_platforms(self):
        assert build_social_queries(criteria()) == (
            "site:facebook.com Boutiques Lahore",
            "site:instagram.com Boutiques Lahore",
            "site:tiktok.com Boutiques Lahore",
        )

    def test_exact_domain_merges_physical_and_web_candidates(self):
        web = web_result_to_candidate(result("Glow Boutique official", "https://glow.example/about"))
        response = merge_candidate_pool(criteria(), [local_business(), web])

        assert len(response.candidates) == 1
        candidate = response.candidates[0]
        assert candidate.discovery_source_types == ["local_places", "web_search"]
        assert candidate.identity_state == "needs_review"
        assert candidate.website_verification_state == "listed_unverified"

    def test_similar_names_without_an_exact_identifier_remain_separate(self):
        social = social_result_to_candidate(result("Glow Boutique", "https://www.instagram.com/glowboutique/"))
        response = merge_candidate_pool(criteria(), [local_business(), social])

        assert len(response.candidates) == 2
