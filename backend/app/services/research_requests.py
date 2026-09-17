import uuid
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from uuid import UUID
from app.repositories.research_requests import (
    clone_failed_research_request,
    get_research_request_for_user as get_research_request_for_user_repository,
)
from app.models.research_request import ResearchRequest
from app.models.research_request import ResearchStatus
from app.models.company import Company
from app.models.user import User
from app.schemas.opportunity_models import IdentityState, OpportunityModelSelection
from app.schemas.research_request import KnownProspectConfirmationRequest, KnownProspectResearchRequest
from app.services.company_resolution import CompanyWebsiteResolver, ResolvedCompany


class KnownProspectResolutionError(ValueError):
    pass


class ResearchRetryError(ValueError):
    pass


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


def retry_research_request(
    db: Session,
    request_id: UUID,
    current_user: User,
) -> ResearchRequest | None:
    research_request = get_research_request_for_user_repository(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
    )
    if research_request is None:
        return None
    if research_request.status is not ResearchStatus.FAILED:
        raise ResearchRetryError("Only a failed research request can be retried.")
    if not isinstance(research_request.objective, dict):
        raise ResearchRetryError("The failed request has no reusable research objective.")
    try:
        selection = OpportunityModelSelection.model_validate(
            research_request.opportunity_model_selection
        )
    except ValueError as error:
        raise ResearchRetryError(
            "The failed request has no valid Opportunity Model selection."
        ) from error
    if not selection.confirmed_by_user:
        raise ResearchRetryError("The failed request's model selection is not confirmed.")
    return clone_failed_research_request(db, research_request)


def resolve_known_prospect(
    resolver: CompanyWebsiteResolver,
    request: KnownProspectResearchRequest,
) -> ResolvedCompany:
    return resolver.resolve(
        company_name=request.business_name,
        location=request.location,
        supplied_website=str(request.website) if request.website else None,
        phone_number=request.phone_number,
    )


def confirm_known_prospect(
    db: Session,
    current_user: User,
    request: KnownProspectConfirmationRequest,
    resolution: ResolvedCompany,
) -> ResearchRequest:
    if resolution.identity_state is not IdentityState.VERIFIED:
        raise KnownProspectResolutionError(
            "Resolve a verified business identity before confirming research."
        )
    if resolution.source is None:
        raise KnownProspectResolutionError(
            "A traceable identity source is required before confirmation."
        )

    identity_key = _resolved_identity_key(resolution)
    company = db.scalar(
        select(Company).where(
            Company.user_id == current_user.id,
            or_(
                Company.identity_key == identity_key,
                *(
                    (Company.website == resolution.website,)
                    if resolution.website is not None
                    else ()
                ),
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
        opportunity_model_selection=(
            request.model_selection.model_dump(mode="json")
            if request.model_selection is not None
            else None
        ),
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
                "website_status": (
                    "verified" if resolution.website is not None else "not_verified"
                ),
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


def _resolved_identity_key(resolution: ResolvedCompany) -> str:
    if resolution.website is not None:
        return _website_identity_key(resolution.website)
    if resolution.source is None:
        raise KnownProspectResolutionError("A traceable identity source is required.")
    provider = resolution.source.provider.casefold().strip()
    if resolution.source.provider_record_id:
        return f"{provider}:{resolution.source.provider_record_id.strip()}"
    if resolution.source.source_url is not None:
        normalized = str(resolution.source.source_url).rstrip("/").casefold()
        return f"{provider}:url:{normalized}"
    raise KnownProspectResolutionError("The identity source has no stable reference.")
