from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.current_user import get_current_user
from app.integrations.open_places import OpenPlacesProviderError
from app.integrations.serper import SerperProviderError
from app.models.user import User
from app.services.local_business_discovery import LocalBusinessDiscoveryError
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    ParseDiscoveryRequest,
    ParseDiscoveryResponse,
)
from app.services.company_discovery import (
    check_supported_objective,
    discover_companies,
    parse_discovery_objective,
)


router = APIRouter(tags=["Company Discovery"])


@router.post(
    "/company-discovery/parse",
    response_model=ParseDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Interpret a discovery goal into a structured objective (stateless)",
    responses={
        422: {"description": "Empty or invalid goal"},
        503: {"description": "AI failure"},
    },
)
def parse_discovery_goal_endpoint(
    request: ParseDiscoveryRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        objective = parse_discovery_objective(request)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not interpret the discovery goal. Please try again.",
        ) from error

    supported, message = check_supported_objective(objective)
    return ParseDiscoveryResponse(
        objective=objective,
        supported=supported,
        message=message,
    )


@router.post(
    "/company-discovery",
    response_model=CompanyDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover companies matching business criteria (stateless)",
    responses={
        422: {"description": "Empty or invalid criteria"},
        503: {"description": "Search provider or AI failure"},
    },
)
def discover_companies_endpoint(
    criteria: CompanyDiscoveryRequest,
    current_user: User = Depends(get_current_user),
):
    if criteria.objective is not None:
        supported, message = check_supported_objective(criteria.objective)
        if not supported:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=message,
            )
    try:
        return discover_companies(criteria)
    except LocalBusinessDiscoveryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except (
        OpenPlacesProviderError,
        SerperProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Company discovery failed. Please try again.",
        ) from error
