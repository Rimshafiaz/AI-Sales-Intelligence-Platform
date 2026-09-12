from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import AuthenticatedIdentity, get_authenticated_identity
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import get_dashboard_summary_for_user


router = APIRouter(tags=["Dashboard"])


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Show the current user's prospecting actions and pipeline",
)
def get_dashboard_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> DashboardSummaryResponse:
    return get_dashboard_summary_for_user(db=db, current_user=current_user)
