from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.schemas.research_request import (
    KnownProspectResearchRequest,
    KnownProspectResolutionResponse,
    ResearchRequestResponse,
    ResearchRequestStartRequest,
)
from app.schemas.research_source import ResearchSourceResponse
from app.services.research_runner import run_research
from app.services.research_requests import (
    KnownProspectResolutionError,
    confirm_known_prospect,
    create_research_request_for_company,
    get_research_request_for_user,
    resolve_known_prospect,
)
from app.services.research_sources import list_research_sources_for_user
from app.core.config import settings
from app.integrations.search_provider import SearchProviderError, create_tavily_search_provider
from app.services.company_resolution import CompanyWebsiteResolver, ResolvedCompany


router = APIRouter(tags=["Research Requests"])


@router.post(
    "/known-prospects/resolve",
    response_model=KnownProspectResolutionResponse,
    summary="Resolve a known prospect before creating research",
    responses={422: {"description": "Invalid target or ambiguous identity"}},
)
def resolve_known_prospect_endpoint(
    payload: KnownProspectResearchRequest,
    _current_user: User = Depends(get_current_user),
):
    try:
        resolver = CompanyWebsiteResolver(
            create_tavily_search_provider(settings.tavily_api_key)
        )
        resolution: ResolvedCompany = resolve_known_prospect(resolver, payload)
        return KnownProspectResolutionResponse(
            business_name=resolution.company_name,
            location=resolution.location,
            website=resolution.website,
            identity_state=resolution.identity_state,
            source=resolution.source,
            reason=resolution.reason,
        )
    except (SearchProviderError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.post(
    "/known-prospects/confirm",
    response_model=ResearchRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm a resolved known prospect for evidence review",
    responses={422: {"description": "Business identity needs review"}},
)
def confirm_known_prospect_endpoint(
    payload: KnownProspectResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        resolver = CompanyWebsiteResolver(
            create_tavily_search_provider(settings.tavily_api_key)
        )
        resolution = resolve_known_prospect(resolver, payload)
        return confirm_known_prospect(db, current_user, payload, resolution)
    except (SearchProviderError, KnownProspectResolutionError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.post(
    "/companies/{company_id}/research-requests",
    response_model=ResearchRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a research request for a company",
    responses={
        404: {"description": "Company unknown or owned by another user"},
    },
)
async def create_research_request_endpoint(
    company_id: UUID,
    background_tasks: BackgroundTasks,
    payload: ResearchRequestStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = create_research_request_for_company(
        db=db,
        company_id=company_id,
        current_user=current_user,
        goal=payload.goal,
        objective=payload.objective.model_dump(mode="json") if payload.objective else None,
        offering=payload.offering,
        region=payload.region,
        website=str(payload.website) if payload.website else None,
    )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
    )
    background_tasks.add_task(
        run_research,
        research_request.id,
    )

    return research_request


@router.get(
    "/research-requests/{request_id}",
    response_model=ResearchRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Show a research request's lifecycle status",
    responses={404: {"description": "Request unknown or owned by another user"}},
)
async def get_research_request_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )

    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )

    return research_request


@router.post(
    "/research-requests/{request_id}/evidence-gate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Collect and filter evidence for a pending research request",
    responses={
        404: {"description": "Request unknown or owned by another user"},
        409: {"description": "Request is already being reviewed or has finished"},
    },
)
def start_evidence_gate_endpoint(
    request_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )
    if research_request.status is not ResearchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence review has already started or finished.",
        )

    background_tasks.add_task(run_research, research_request.id)
    return {"status": "evidence_review_started"}


@router.get(
    "/research-requests/{request_id}/sources",
    response_model=list[ResearchSourceResponse],
    status_code=status.HTTP_200_OK,
    summary="List the collected evidence sources for a request",
    responses={404: {"description": "Request unknown or owned by another user"}},
)
async def list_research_sources_endpoint(
    request_id: UUID,
    limit: int = Query(default=25, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )

    return list_research_sources_for_user(
        db=db,
        request_id=request_id,
        current_user=current_user,
        limit=limit,
    )
