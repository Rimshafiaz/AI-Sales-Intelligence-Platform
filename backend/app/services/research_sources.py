from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.search_provider import CollectedSource, TavilySearchProvider
from app.integrations.website_metadata import WebsiteMetadata
from app.models.research_source import ResearchSource
from app.models.user import User
from app.repositories.research_sources import (
    list_research_sources_for_user as list_research_sources_for_user_repository,
)


def collect_company_search_sources(
    company_name: str,
    search_provider: TavilySearchProvider,
) -> list[CollectedSource]:
    clean_name = company_name.strip()
    if not clean_name:
        raise ValueError("Company name cannot be blank.")

    queries = [
        f'"{clean_name}" company overview',
        f'"{clean_name}" products services',
        f'"{clean_name}" technology engineering',
        f'"{clean_name}" recent news expansion hiring funding',
    ]
    sources: list[CollectedSource] = []

    for query in queries:
        sources.extend(search_provider.search(query))

    return sources


def website_metadata_to_source(
    metadata: WebsiteMetadata,
) -> CollectedSource:
    return CollectedSource(
        url=metadata.url,
        title=metadata.title,
        excerpt=metadata.description or metadata.excerpt,
        source_type=metadata.source_type,
    )


def deduplicate_sources(
    sources: list[CollectedSource],
) -> list[CollectedSource]:
    unique_sources: dict[tuple[str, str, str, str], CollectedSource] = {}

    for source in sources:
        key = (
            _normalize_url(source.url),
            source.source_type.casefold(),
            _normalize_text(source.title),
            _normalize_text(source.excerpt),
        )

        if key not in unique_sources:
            unique_sources[key] = source

    return list(unique_sources.values())


def _normalize_url(url: str) -> str:
    parsed_url = urlsplit(url.strip())

    return urlunsplit(
        (
            parsed_url.scheme.casefold(),
            parsed_url.netloc.casefold(),
            parsed_url.path.rstrip("/") or "/",
            parsed_url.query,
            "",
        )
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def list_research_sources_for_user(
    db: Session,
    request_id: UUID,
    current_user: User,
    limit: int,
) -> list[ResearchSource]:
    return list_research_sources_for_user_repository(
        db=db,
        research_request_id=request_id,
        user_id=current_user.id,
        limit=limit,
    )
