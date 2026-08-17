from dataclasses import dataclass
from urllib.parse import urlparse

from app.integrations.search_provider import (
    CollectedSource,
    TavilySearchProvider,

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
    website: str | None
    is_confident: bool
    supporting_source_url: str | None


class CompanyWebsiteResolver:
    def __init__(self, search_provider: TavilySearchProvider) -> None:
        self.search_provider = search_provider

    def resolve(self, company_name: str) -> ResolvedCompany:
        clean_name = company_name.strip()
        if not clean_name:
            raise ValueError("Company name cannot be blank.")

        sources = self.search_provider.search(f'"{clean_name}" official website')
        candidates: list[tuple[int, str, str]] = []

        for source in sources:
            website = self._official_website_candidate(clean_name, source)
            if website is None:
                continue

            candidates.append(
                (
                    self._candidate_priority(clean_name, website),
                    website,
                    source.url,
                )
            )

        if candidates:
            _, website, supporting_source_url = min(candidates)
            return ResolvedCompany(
                company_name=clean_name,
                website=website,
                is_confident=True,
                supporting_source_url=supporting_source_url,
            )

        return ResolvedCompany(
            company_name=clean_name,
            website=None,
            is_confident=False,
            supporting_source_url=None,
        )

    @staticmethod
    def _official_website_candidate(
        company_name: str,
        source: CollectedSource,
    ) -> str | None:
        parsed_url = urlparse(source.url)
        hostname = parsed_url.hostname
        if hostname is None or CompanyWebsiteResolver._is_excluded_website_platform(hostname):
            return None

        company_key = CompanyWebsiteResolver._company_key(company_name)
        hostname_labels = hostname.removeprefix("www.").casefold().split(".")
        title = (source.title or "").casefold()

        if company_key not in hostname_labels:
            return None
        if company_name.casefold() not in title:
            return None

        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    @staticmethod
    def _candidate_priority(company_name: str, website: str) -> int:
        hostname = urlparse(website).hostname or ""
        expected_hostname = f"{CompanyWebsiteResolver._company_key(company_name)}.com"
        return 0 if hostname.removeprefix("www.") == expected_hostname else 1

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
