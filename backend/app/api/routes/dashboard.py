from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import get_dashboard_summary_for_user


router = APIRouter(tags=["Dashboard"])


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Show the current user's metrics and recent activity",
)
def get_dashboard_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_summary_for_user(db=db, current_user=current_user)
