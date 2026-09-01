from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.research_report import ReportDetailResponse, ResearchReportResponse
from app.services.report_generation import (
    ReportGenerationConflict,
    ReportGenerationFailed,
    generate_report_for_request,
)
from app.services.reports import get_report_detail_for_user


router = APIRouter(tags=["Reports"])


@router.post(
    "/research-requests/{request_id}/reports",
    response_model=ResearchReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        report = generate_report_for_request(
            db=db,
            request_id=request_id,
            current_user=current_user,
        )
    except ReportGenerationConflict as conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(conflict),
        ) from conflict
    except ReportGenerationFailed as failure:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(failure),
        ) from failure

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )

    return report


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_report_endpoint(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report_detail = get_report_detail_for_user(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
    if report_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return report_detail
