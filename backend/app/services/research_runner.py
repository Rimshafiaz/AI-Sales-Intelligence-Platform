from uuid import UUID

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.search_provider import create_tavily_search_provider
from app.integrations.website_metadata import WebsiteMetadataCollector
from app.repositories.companies import get_company_by_id, update_company_website
from app.repositories.research_requests import (
    get_research_request_by_id,
    mark_research_request_complete,
    mark_research_request_failed,
    mark_research_request_running,
)
from app.repositories.research_sources import create_research_sources
from app.services.company_resolution import CompanyWebsiteResolver
from app.services.research_sources import (
    collect_company_search_sources,
    deduplicate_sources,
    website_metadata_to_source,
)


def run_research(request_id: UUID) -> None:
    db = SessionLocal()

    try:
        running_request = mark_research_request_running(
            db=db,
            request_id=request_id,
        )
        if running_request is None:
            return

        research_request = get_research_request_by_id(
            db=db,
            request_id=request_id,
        )
        if research_request is None:
            return

        company = get_company_by_id(
            db=db,
            company_id=research_request.company_id,
            user_id=research_request.user_id,
        )
        if company is None:
            raise RuntimeError("Company for research request was not found.")

        search_provider = create_tavily_search_provider(settings.tavily_api_key)
        website = company.website

        if website is None:
            resolver = CompanyWebsiteResolver(search_provider)
            resolved_company = resolver.resolve(company.name)

            if resolved_company.is_confident and resolved_company.website:
                updated_company = update_company_website(
                    db=db,
                    company_id=company.id,
                    website=resolved_company.website,
                )
                if updated_company is None:
                    raise RuntimeError("Company website could not be saved.")

                website = updated_company.website

        website_source = None
        if website is not None:
            metadata = WebsiteMetadataCollector().collect(website)
            if metadata is not None:
                website_source = website_metadata_to_source(metadata)

        sources = collect_company_search_sources(
            company.name,
            search_provider,
        )
        if website_source is not None:
            sources.insert(0, website_source)

        unique_sources = deduplicate_sources(sources)
        if not unique_sources:
            raise RuntimeError("No unique research sources were collected.")

        create_research_sources(
            db=db,
            research_request_id=research_request.id,
            sources=unique_sources,
        )
        mark_research_request_complete(db, request_id)

    except Exception:
        db.rollback()
        mark_research_request_failed(
            db,
            request_id,
            "Research source collection failed.",
        )
    finally:
        db.close()
