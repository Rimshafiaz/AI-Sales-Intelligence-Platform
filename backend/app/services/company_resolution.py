from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.integrations.search_provider import CollectedSource, TavilySearchProvider
from app.schemas.opportunity_models import EvidenceSource, IdentityState


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


class CompanyWebsiteResolver:
    def __init__(self, search_provider: TavilySearchProvider) -> None:
        self.search_provider = search_provider

    def resolve(
        self,
        company_name: str,
        location: str | None = None,
        supplied_website: str | None = None,
    ) -> ResolvedCompany:
        clean_name = company_name.strip()
        clean_location = location.strip() if location else None
        if not clean_name:
            raise ValueError("Company name cannot be blank.")

        supplied_origin = self._origin(supplied_website) if supplied_website else None
        if supplied_website and supplied_origin is None:
            raise ValueError("Website must be a valid http(s) URL.")

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

        if len(unique_matches) != 1:
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

        match = next(iter(unique_matches.values()))
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
            reason="One source-backed website matched the requested business identity.",
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

        company_key = CompanyWebsiteResolver._company_key(company_name)
        hostname_labels = hostname.removeprefix("www.").casefold().split(".")
        title = (source.title or "").casefold()
        if company_key not in hostname_labels or company_name.casefold() not in title:
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
