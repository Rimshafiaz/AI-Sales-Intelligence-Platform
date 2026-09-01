from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.current_user import get_current_user
from app.integrations.search_provider import SearchProviderError
from app.models.user import User
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
)
from app.services.company_discovery import discover_companies


router = APIRouter(tags=["Company Discovery"])


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
    try:
        return discover_companies(criteria)
    except (SearchProviderError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Company discovery failed. Please try again.",
        ) from error
