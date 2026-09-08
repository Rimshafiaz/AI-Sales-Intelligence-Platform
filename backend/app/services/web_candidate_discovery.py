from hashlib import sha256
from urllib.parse import urlparse, urlunparse

from app.integrations.business_discovery import (
    DiscoveredBusiness,
    DiscoverySourceType,
)
from app.integrations.serper import SerperSearchProvider
from app.schemas.company_discovery import CompanyDiscoveryRequest


MAX_WEB_QUERIES = 2
MAX_SOCIAL_QUERIES = 3
RESULTS_PER_QUERY = 10
DIRECTORY_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "pinterest.com",
    "tiktok.com",
    "google.com",
    "yelp.com",
    "tripadvisor.com",
    "yellowpages.com",
}
SOCIAL_DOMAINS = {"instagram.com", "facebook.com", "tiktok.com"}


def discover_web_and_social_candidates(
    criteria: CompanyDiscoveryRequest,
    provider: SerperSearchProvider,
) -> list[DiscoveredBusiness]:
    candidates: list[DiscoveredBusiness] = []
    for query in build_web_queries(criteria):
        for result in provider.search(query, max_results=RESULTS_PER_QUERY):
            candidate = web_result_to_candidate(result)
            if candidate is not None:
                candidates.append(candidate)
    for query in build_social_queries(criteria):
        for result in provider.search(query, max_results=RESULTS_PER_QUERY):
            candidate = social_result_to_candidate(result)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def build_web_queries(criteria: CompanyDiscoveryRequest) -> tuple[str, ...]:
    terms = f"{criteria.industry} {criteria.region}".strip()
    return (
        f"{terms} official website",
        f"{terms} online store",
    )[:MAX_WEB_QUERIES]


def build_social_queries(criteria: CompanyDiscoveryRequest) -> tuple[str, ...]:
    terms = f"{criteria.industry} {criteria.region}".strip()
    return tuple(
        f"site:{domain} {terms}"
        for domain in sorted(SOCIAL_DOMAINS)
    )[:MAX_SOCIAL_QUERIES]


def web_result_to_candidate(result) -> DiscoveredBusiness | None:
    domain = normalized_domain(result.url)
    if domain is None or domain in DIRECTORY_DOMAINS:
        return None
    return DiscoveredBusiness(
        provider="serper",
        provider_record_id=source_record_id(result.url),
        name=result.title,
        category=None,
        categories=(),
        category_hierarchy=(),
        formatted_address=None,
        latitude=None,
        longitude=None,
        website=canonical_site_url(result.url),
        phone_number=None,
        business_status=None,
        source_data_release=None,
        retrieved_at=result.retrieved_at,
        source_type=DiscoverySourceType.WEB_SEARCH,
        source_url=result.url,
    )


def social_result_to_candidate(result) -> DiscoveredBusiness | None:
    profile_url = canonical_social_profile_url(result.url)
    if profile_url is None:
        return None
    return DiscoveredBusiness(
        provider="serper",
        provider_record_id=source_record_id(profile_url),
        name=result.title,
        category=None,
        categories=(),
        category_hierarchy=(),
        formatted_address=None,
        latitude=None,
        longitude=None,
        website=None,
        phone_number=None,
        business_status=None,
        source_data_release=None,
        retrieved_at=result.retrieved_at,
        source_type=DiscoverySourceType.SOCIAL_SEARCH,
        source_url=profile_url,
        social_profile_url=profile_url,
    )


def normalized_domain(url: str) -> str | None:
    hostname = urlparse(url).hostname
    if hostname is None:
        return None
    return hostname.casefold().removeprefix("www.")


def canonical_site_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def canonical_social_profile_url(url: str) -> str | None:
    parsed = urlparse(url)
    domain = normalized_domain(url)
    if domain not in SOCIAL_DOMAINS:
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) != 1:
        return None
    handle = segments[0]
    if domain == "instagram.com" and handle.casefold() in {
        "accounts", "direct", "explore", "p", "reel", "reels", "stories",
    }:
        return None
    if domain == "facebook.com" and handle.casefold() in {
        "events", "groups", "marketplace", "photo", "share", "watch",
    }:
        return None
    if domain == "tiktok.com" and not handle.startswith("@"):
        return None
    return urlunparse((parsed.scheme, parsed.netloc, f"/{handle}", "", "", ""))


def source_record_id(url: str) -> str:
    return f"serper:{sha256(url.encode()).hexdigest()}"
