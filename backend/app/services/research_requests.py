import uuid
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from uuid import UUID
from app.repositories.research_requests import (
    create_research_request,
    get_research_request_for_user as get_research_request_for_user_repository,
)
from app.repositories.companies import get_company_by_id
from app.models.research_request import ResearchRequest
from app.models.research_request import ResearchStatus
from app.models.company import Company
from app.models.user import User
from app.schemas.opportunity_models import IdentityState
from app.schemas.research_request import KnownProspectResearchRequest
from app.services.company_resolution import CompanyWebsiteResolver, ResolvedCompany


class KnownProspectResolutionError(ValueError):
    pass


def create_research_request_for_company(
    db: Session,
    company_id: UUID,
    current_user: User,
    goal: str | None = None,
    objective: dict | None = None,
    offering: str | None = None,
    region: str | None = None,
    website: str | None = None,
) -> ResearchRequest | None:
    company=get_company_by_id(db=db,company_id=company_id,user_id=current_user.id)
    if not company:
        return None
    snapshot: dict | None = None
    base = {
        key: value
        for key, value in {
            "goal": goal,
            "offering": offering,
            "region": region,
            "website": website,
        }.items()
        if value
    }
    if objective is not None:
        snapshot = {**base, **dict(objective)}
    elif base:
        snapshot = base
    request=create_research_request(
        db=db,
        company_id=company_id,
        user_id=current_user.id,
        objective=snapshot,
    )
    return request


def get_research_request_for_user(
    db: Session,
    request_id: UUID,
    current_user: User,
) -> ResearchRequest | None:
    return get_research_request_for_user_repository(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
    )


def resolve_known_prospect(
    resolver: CompanyWebsiteResolver,
    request: KnownProspectResearchRequest,
) -> ResolvedCompany:
    return resolver.resolve(
        company_name=request.business_name,
        location=request.location,
        supplied_website=str(request.website) if request.website else None,
    )


def confirm_known_prospect(
    db: Session,
    current_user: User,
    request: KnownProspectResearchRequest,
    resolution: ResolvedCompany,
) -> ResearchRequest:
    if resolution.identity_state is not IdentityState.VERIFIED:
        raise KnownProspectResolutionError(
            "Resolve a verified business identity before confirming research."
        )
    if resolution.website is None or resolution.source is None:
        raise KnownProspectResolutionError(
            "A verified website and traceable source are required before confirmation."
        )

    identity_key = _website_identity_key(resolution.website)
    company = db.scalar(
        select(Company).where(
            Company.user_id == current_user.id,
            or_(
                Company.identity_key == identity_key,
                Company.website == resolution.website,
            ),
        )
    )
    is_new_company = company is None
    if is_new_company:
        company = Company(
            id=uuid.uuid4(),
            user_id=current_user.id,
            name=resolution.company_name,
            website=resolution.website,
            identity_key=identity_key,
        )

    existing_pending_request = db.scalar(
        select(ResearchRequest.id).where(
            ResearchRequest.company_id == company.id,
            ResearchRequest.user_id == current_user.id,
            ResearchRequest.status == ResearchStatus.PENDING,
        )
    )
    if existing_pending_request is not None:
        raise KnownProspectResolutionError(
            "This prospect already has a pending evidence-review request."
        )

    research_request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=current_user.id,
        status=ResearchStatus.PENDING,
        objective={
            "mode": "known_prospect",
            "goal": request.goal,
            "offering": request.offering,
            "desired_outcome": request.desired_outcome,
            "location": request.location,
            "region": request.location,
            "resolved_target": {
                "business_name": resolution.company_name,
                "website": resolution.website,
                "identity_state": resolution.identity_state.value,
                "source": resolution.source.model_dump(mode="json"),
            },
        },
    )
    try:
        if is_new_company:
            db.add(company)
        db.add(research_request)
        db.commit()
        db.refresh(research_request)
    except Exception:
        db.rollback()
        raise
    return research_request


def _website_identity_key(website: str) -> str:
    hostname = urlparse(website).hostname
    if hostname is None:
        raise KnownProspectResolutionError("Resolved website has no hostname.")
    return f"website:{hostname.casefold().removeprefix('www.')}"
