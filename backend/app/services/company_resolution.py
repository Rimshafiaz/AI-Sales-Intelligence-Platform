from dataclasses import dataclass
from datetime import UTC, datetime
import re
from urllib.parse import urlparse

from app.integrations.search_provider import CollectedSource, TavilySearchProvider
from app.integrations.website_metadata import WebsiteIdentityPage, WebsiteMetadataCollector
from app.schemas.opportunity_models import EvidenceSource, IdentityState
from app.services.identity_resolution import (
    domain_matches_name,
    domain_stem,
    significant_tokens,
)


EXCLUDED_WEBSITE_PLATFORMS = {
    "crunchbase.com",
    "facebook.com",
    "github.com",
    "linkedin.com",
    "wikipedia.org",
    "x.com",
    "youtube.com",
}


@dataclass(frozen=True)
class ResolvedCompany:
    company_name: str
    location: str | None
    website: str | None
    identity_state: IdentityState
    source: EvidenceSource | None
    reason: str

    @property
    def is_confident(self) -> bool:
        return self.identity_state is IdentityState.VERIFIED

    @property
    def supporting_source_url(self) -> str | None:
        return str(self.source.source_url) if self.source and self.source.source_url else None


@dataclass(frozen=True)
class ResolutionMatch:
    website: str
    location_supported: bool
    source: EvidenceSource
    reason: str


class CompanyWebsiteResolver:
    def __init__(
        self,
        search_provider: TavilySearchProvider,
        website_collector: WebsiteMetadataCollector | None = None,
    ) -> None:
        self.search_provider = search_provider
        self.website_collector = website_collector or WebsiteMetadataCollector()

    def resolve(
        self,
        company_name: str,
        location: str | None = None,
        supplied_website: str | None = None,
        phone_number: str | None = None,
    ) -> ResolvedCompany:
        clean_name = company_name.strip()
        clean_location = location.strip() if location else None
        if not clean_name:
            raise ValueError("Company name cannot be blank.")

        supplied_origin = self._origin(supplied_website) if supplied_website else None
        if supplied_website and supplied_origin is None:
            raise ValueError("Website must be a valid http(s) URL.")

        website_match = self._website_identity_match(
            clean_name,
            clean_location,
            phone_number,
            supplied_origin,
        )
        if website_match is not None:
            return ResolvedCompany(
                company_name=clean_name,
                location=clean_location,
                website=website_match.website,
                identity_state=IdentityState.VERIFIED,
                source=website_match.source,
                reason=website_match.reason,
            )

        query = " ".join(
            part
            for part in (f'"{clean_name}"', clean_location, "official website")
            if part
        )
        matches = [
            match
            for source in self.search_provider.search(query)
            if (match := self._match_source(clean_name, clean_location, source)) is not None
            and (supplied_origin is None or match.website == supplied_origin)
        ]
        unique_matches = {match.website: match for match in matches}

        # Directories and aggregators can corroborate identity, but only a
        # domain that represents the business name itself can be the official
        # website. When exactly one such domain exists, it wins; ambiguity
        # between name-representative domains still needs review.
        name_tokens = significant_tokens(clean_name)
        representative_matches = {
            website: match
            for website, match in unique_matches.items()
            if domain_matches_name(domain_stem(website), name_tokens)
        }
        candidates = representative_matches or unique_matches

        if len(candidates) != 1:
            return ResolvedCompany(
                company_name=clean_name,
                location=clean_location,
                website=supplied_origin,
                identity_state=IdentityState.NEEDS_REVIEW,
                source=None,
                reason=(
                    "No single source-backed official website could be matched to this "
                    "business identity."
                ),
            )

        match = next(iter(candidates.values()))
        if clean_location and not match.location_supported:
            return ResolvedCompany(
                company_name=clean_name,
                location=clean_location,
                website=match.website,
                identity_state=IdentityState.NEEDS_REVIEW,
                source=match.source,
                reason=(
                    "The website matches the business name, but the supplied location "
                    "is not supported by the search evidence."
                ),
            )

        return ResolvedCompany(
            company_name=clean_name,
            location=clean_location,
            website=match.website,
            identity_state=IdentityState.VERIFIED,
            source=match.source,
            reason=match.reason,
        )

    @staticmethod
    def _match_source(
        company_name: str,
        location: str | None,
        source: CollectedSource,
    ) -> ResolutionMatch | None:
        website = CompanyWebsiteResolver._official_website_candidate(company_name, source)
        if website is None:
            return None
        source_text = " ".join(part for part in (source.title, source.excerpt) if part)
        location_supported = not location or location.casefold() in source_text.casefold()
        return ResolutionMatch(
            website=website,
            location_supported=location_supported,
            source=EvidenceSource(
                provider="tavily",
                source_url=source.url,
                retrieved_at=datetime.now(UTC),
            ),
            reason="One search source-backed website matched the requested business identity.",
        )

    def _website_identity_match(
        self,
        company_name: str,
        location: str | None,
        phone_number: str | None,
        supplied_origin: str | None,
    ) -> ResolutionMatch | None:
        if supplied_origin is None:
            return None
        for page in self.website_collector.collect_identity_pages(supplied_origin):
            if not CompanyWebsiteResolver._identity_page_supports_identity(
                page,
                company_name,
                location,
                phone_number,
            ):
                continue
            website = CompanyWebsiteResolver._origin(page.url)
            if website is None:
                continue
            return ResolutionMatch(
                website=website,
                location_supported=True,
                source=EvidenceSource(
                    provider="official_website",
                    source_url=page.url,
                    retrieved_at=datetime.now(UTC),
                ),
                reason=(
                    "A traceable page on the supplied website names the business and "
                    "matches its provided location or phone number."
                ),
            )
        return None

    @staticmethod
    def _identity_page_supports_identity(
        page: WebsiteIdentityPage,
        company_name: str,
        location: str | None,
        phone_number: str | None,
    ) -> bool:
        text = page.identity_text
        text_lower = text.casefold()
        name_tokens = significant_tokens(company_name)
        shared_name_tokens = sum(
            1
            for token in name_tokens
            if token and re.search(rf"\b{re.escape(token)}\b", text_lower)
        )
        if shared_name_tokens < 2:
            return False
        location_supported = bool(
            location
            and CompanyWebsiteResolver._company_key(location)
            in CompanyWebsiteResolver._company_key(text)
        )
        phone_supported = CompanyWebsiteResolver._phone_numbers_match(phone_number, text)
        return location_supported or phone_supported

    @staticmethod
    def _phone_numbers_match(phone_number: str | None, text: str) -> bool:
        if not phone_number:
            return False
        expected = "".join(character for character in phone_number if character.isdigit())
        observed_numbers = [
            "".join(character for character in match if character.isdigit())
            for match in re.findall(r"\+?\d[\d\s().-]{7,}\d", text)
        ]
        if len(expected) < 9:
            return False
        return any(
            len(observed) >= 9
            and (expected == observed or expected[-9:] == observed[-9:])
            for observed in observed_numbers
        )

    @staticmethod
    def _official_website_candidate(
        company_name: str,
        source: CollectedSource,
    ) -> str | None:
        website = CompanyWebsiteResolver._origin(source.url)
        if website is None:
            return None
        hostname = urlparse(website).hostname
        if hostname is None or CompanyWebsiteResolver._is_excluded_website_platform(hostname):
            return None

        name_tokens = significant_tokens(company_name)
        stem = domain_stem(source.url)
        title = (source.title or "").casefold()
        shared_title_tokens = sum(
            1
            for token in name_tokens
            if token and re.search(rf"\b{re.escape(token)}\b", title)
        )
        if not domain_matches_name(stem, name_tokens) and shared_title_tokens < 2:
            return None
        return website

    @staticmethod
    def _origin(value: str) -> str | None:
        parsed_url = urlparse(value)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return None
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    @staticmethod
    def _company_key(company_name: str) -> str:
        return "".join(character for character in company_name.casefold() if character.isalnum())

    @staticmethod
    def _is_excluded_website_platform(hostname: str) -> bool:
        normalized_hostname = hostname.casefold().removeprefix("www.")
        return any(
            normalized_hostname == domain or normalized_hostname.endswith(f".{domain}")
            for domain in EXCLUDED_WEBSITE_PLATFORMS
        )
