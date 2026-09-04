from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.research_report import ReportReviewStatus
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.repositories.research_reports import (
    get_research_report_by_id_for_user,
    get_research_report_for_user,
)
from app.repositories.research_requests import get_research_request_for_user
from app.schemas.report_list import ReportListResponse
from app.schemas.research_report import (
    RegenerateReportRequest,
    ReportDetailResponse,
    ReportEditRequest,
    ResearchReportResponse,
)
from app.services.report_generation import (
    run_generation_background,
    run_regeneration_background,
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
    summary="List the current user's report history",
    responses={422: {"description": "Invalid pagination or filter values"}},
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
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start asynchronous report generation for a completed request",
    responses={
        202: {"description": "Generation started; poll report history for the new draft"},
        404: {"description": "Request unknown or owned by another user"},
        409: {"description": "Request not completed, or a report already exists"},
    },
)
def create_report_endpoint(
    request_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
    )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )
    if research_request.status != ResearchStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research request is not completed yet.",
        )
    existing_report = get_research_report_for_user(
        db=db,
        research_request_id=research_request.id,
        user_id=current_user.id,
    )
    if existing_report is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A report already exists for this research request.",
        )

    background_tasks.add_task(
        run_generation_background,
        request_id=request_id,
        user_id=current_user.id,
    )

    return {"status": "generating"}


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Show a report with its evidence sources",
    responses={404: {"description": "Report unknown or owned by another user"}},
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
    summary="Approve a report (idempotent)",
    responses={404: {"description": "Report unknown or owned by another user"}},
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
    summary="Edit the report's outreach fields (reverts to draft)",
    responses={
        404: {"description": "Report unknown or owned by another user"},
        422: {"description": "Field outside the allowlist, blank, or too long"},
    },
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
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start an asynchronous report regeneration",
    responses={
        202: {"description": "Regeneration started; poll report history for the new draft"},
        404: {"description": "Report unknown or owned by another user"},
    },
)
def regenerate_report_endpoint(
    report_id: UUID,
    regeneration: RegenerateReportRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    instruction = regeneration.instruction if regeneration else None

    existing_report = get_research_report_by_id_for_user(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
    if existing_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    background_tasks.add_task(
        run_regeneration_background,
        report_id=report_id,
        user_id=current_user.id,
        instruction=instruction,
    )

    return {"status": "regenerating"}
