from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.research_report import ReportReviewStatus
from app.models.user import User
from app.schemas.report_list import ReportListResponse
from app.schemas.research_report import (
    RegenerateReportRequest,
    ReportDetailResponse,
    ReportEditRequest,
    ResearchReportResponse,
)
from app.services.report_generation import (
    ReportGenerationConflict,
    ReportGenerationFailed,
    generate_report_for_request,
    regenerate_report_for_user,
)
from app.services.reports import (
    approve_report_for_user,
    edit_report_for_user,
    get_report_detail_for_user,
    list_report_history_for_user,
)


router = APIRouter(tags=["Reports"])


@router.get(
    "/reports",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
)
def list_reports_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    company: str | None = Query(default=None, max_length=255),
    industry: str | None = Query(default=None, max_length=100),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    report_status: ReportReviewStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return list_report_history_for_user(
            db=db,
            current_user=current_user,
            page=page,
            page_size=page_size,
            company=company,
            industry=industry,
            from_date=from_date,
            to_date=to_date,
            min_score=min_score,
            max_score=max_score,
            status=report_status,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


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


@router.post(
    "/reports/{report_id}/approve",
    response_model=ResearchReportResponse,
    status_code=status.HTTP_200_OK,
)
def approve_report_endpoint(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approved_report = approve_report_for_user(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
    if approved_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return approved_report


@router.patch(
    "/reports/{report_id}",
    response_model=ResearchReportResponse,
    status_code=status.HTTP_200_OK,
)
def edit_report_endpoint(
    report_id: UUID,
    edits: ReportEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        edited_report = edit_report_for_user(
            db=db,
            report_id=report_id,
            current_user=current_user,
            edits=edits,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    if edited_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return edited_report


@router.post(
    "/reports/{report_id}/regenerate",
    response_model=ResearchReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_report_endpoint(
    report_id: UUID,
    regeneration: RegenerateReportRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instruction = regeneration.instruction if regeneration else None

    try:
        regenerated_report = regenerate_report_for_user(
            db=db,
            report_id=report_id,
            current_user=current_user,
            instruction=instruction,
        )
    except ReportGenerationFailed as failure:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(failure),
        ) from failure

    if regenerated_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return regenerated_report
