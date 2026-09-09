from uuid import UUID

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.search_provider import create_tavily_search_provider
from app.integrations.website_metadata import WebsiteMetadataCollector
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun
from app.repositories.companies import get_company_by_id, update_company_website
from app.repositories.research_requests import (
    get_research_request_by_id,
    mark_research_request_complete,
    mark_research_request_failed,
    mark_research_request_running,
    save_evidence_gate_result,
)
from app.repositories.research_sources import create_research_sources
from app.services.company_resolution import CompanyWebsiteResolver
from app.services.evidence_gate import review_sources, target_from_research_request
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
        selection = (
            db.get(
                CampaignCandidateSelection,
                research_request.campaign_candidate_selection_id,
            )
            if research_request.campaign_candidate_selection_id is not None
            else None
        )
        campaign_run = (
            db.get(CampaignRun, selection.campaign_run_id)
            if selection is not None
            else None
        )
        website = company.website
        resolved_company = None

        if selection is not None or website is None:
            candidate = selection.candidate_snapshot if selection is not None else {}
            objective = research_request.objective or {}
            resolver = CompanyWebsiteResolver(search_provider)
            resolved_company = resolver.resolve(
                company.name,
                location=_resolution_location(
                    objective,
                    campaign_run.criteria_snapshot if campaign_run is not None else None,
                    candidate,
                ),
                supplied_website=website,
                phone_number=candidate.get("phone_number"),
            )

            if resolved_company.is_confident and resolved_company.website:
                if website is None:
                    updated_company = update_company_website(
                        db=db,
                        company_id=company.id,
                        website=resolved_company.website,
                    )
                    if updated_company is None:
                        raise RuntimeError("Company website could not be saved.")
                website = resolved_company.website

        if resolved_company is not None and resolved_company.is_confident:
            objective = dict(research_request.objective or {})
            objective["resolved_target"] = {
                "business_name": resolved_company.company_name,
                "website": resolved_company.website,
                "identity_state": resolved_company.identity_state.value,
                "source": (
                    resolved_company.source.model_dump(mode="json")
                    if resolved_company.source is not None
                    else None
                ),
            }
            research_request.objective = objective
            db.commit()
            db.refresh(research_request)

        website_source = None
        if website is not None:
            metadata = WebsiteMetadataCollector().collect(website)
            if metadata is not None:
                website_source = website_metadata_to_source(metadata)

        target = target_from_research_request(research_request, company, selection)
        sources = collect_company_search_sources(company.name, search_provider, target.location)
        if website_source is not None:
            sources.insert(0, website_source)

        unique_sources = deduplicate_sources(sources)
        admissions, gate_result = review_sources(target, unique_sources)

        create_research_sources(
            db=db,
            research_request_id=research_request.id,
            sources=admissions,
        )
        save_evidence_gate_result(db, request_id, gate_result)
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


def _resolution_location(
    objective: dict,
    campaign_criteria: dict | None,
    candidate: dict,
) -> str | None:
    return (
        objective.get("location")
        or (campaign_criteria or {}).get("location")
        or candidate.get("formatted_address")
    )
