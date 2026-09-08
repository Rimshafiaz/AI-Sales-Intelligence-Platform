import copy
from datetime import date
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.research_report import ReportKind, ReportReviewStatus, ResearchReport
from app.models.user import User
from app.repositories.research_reports import (
    approve_research_report,
    count_research_reports_for_user,
    get_research_report_by_id_for_user,
    list_report_summaries_for_user,
    save_report_edits,
)
from app.repositories.research_requests import get_research_request_for_user
from app.repositories.research_sources import list_research_sources_for_user
from app.schemas.company_discovery import DiscoveryObjective
from app.schemas.report_list import ReportListResponse, ReportSummary
from app.schemas.research_report import (
    ReportDetailResponse,
    ReportEditRequest,
    ResearchReportResponse,
)
from app.schemas.research_source import ResearchSourceResponse
from app.schemas.sales_intelligence_report import SalesIntelligenceReport


DETAIL_SOURCE_LIMIT = 50


def get_report_detail_for_user(
    db: Session,
    report_id: UUID,
    current_user: User,
) -> ReportDetailResponse | None:
    report = get_research_report_by_id_for_user(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
    if report is None:
        return None
    sources = list_research_sources_for_user(
        db=db,
        research_request_id=report.research_request_id,
        user_id=current_user.id,
        limit=DETAIL_SOURCE_LIMIT,
    )

    research_request = get_research_request_for_user(
        db=db,
        request_id=report.research_request_id,
        user_id=current_user.id,
    )
    goal: str | None = None
    objective: DiscoveryObjective | None = None
    if research_request is not None and isinstance(
        research_request.objective, dict
    ):
        raw_goal = research_request.objective.get("goal")
        goal = raw_goal if isinstance(raw_goal, str) and raw_goal.strip() else None
        try:
            objective = DiscoveryObjective.model_validate(
                research_request.objective
            )
        except ValidationError:
            objective = None

    return ReportDetailResponse(
        report=ResearchReportResponse.model_validate(report),
        sources=[
            ResearchSourceResponse.model_validate(source) for source in sources
        ],
        goal=goal,
        objective=objective,
    )


def approve_report_for_user(
    db: Session,
    report_id: UUID,
    current_user: User,
) -> ResearchReport | None:
    return approve_research_report(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )


def _apply_edits(report_data: dict, edits: ReportEditRequest) -> None:
    strategy = report_data["strategy"]
    if edits.strategy is not None:
        strategy["recommended_strategy"]["statement"] = edits.strategy
    if edits.sales_angle is not None:
        strategy["recommended_sales_angle"]["statement"] = edits.sales_angle
    if edits.value_proposition is not None:
        strategy["suggested_value_proposition"]["statement"] = edits.value_proposition

    if edits.cold_email is not None:
        report_data["personalized_outreach"]["cold_email"] = edits.cold_email
    if edits.linkedin_message is not None:
        report_data["personalized_outreach"]["linkedin_message"] = (
            edits.linkedin_message
        )

    if edits.suggested_decision_makers is not None:
        hypotheses = report_data["suggested_decision_makers"]
        if len(edits.suggested_decision_makers) > len(hypotheses):
            raise ValueError(
                "Cannot add decision-maker hypotheses. Edit the existing roles "
                "or regenerate the report."
            )
        for hypothesis, role in zip(hypotheses, edits.suggested_decision_makers):
            hypothesis["suggested_role"] = role


def edit_report_for_user(
    db: Session,
    report_id: UUID,
    current_user: User,
    edits: ReportEditRequest,
) -> ResearchReport | None:
    report = get_research_report_by_id_for_user(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
    if report is None:
        return None
    if report.report_kind is ReportKind.PROSPECT_EVIDENCE_BRIEF:
        raise ValueError("Prospect Evidence Brief editing will be available with its dedicated workspace.")

    merged_report_data = copy.deepcopy(report.report_data)
    _apply_edits(merged_report_data, edits)

    content_changed = merged_report_data != report.report_data
    note_changed = (
        edits.review_note is not None
        and edits.review_note != report.review_note
    )
    if not content_changed and not note_changed:
        return report

    if content_changed:
        SalesIntelligenceReport.model_validate(merged_report_data)

    effective_note = (
        edits.review_note
        if edits.review_note is not None
        else report.review_note
    )
    return save_report_edits(
        db=db,
        report=report,
        report_data=merged_report_data,
        review_note=effective_note,
    )


def list_report_history_for_user(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    company: str | None = None,
    industry: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    status: ReportReviewStatus | None = None,
) -> ReportListResponse:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ValueError("from_date cannot be after to_date.")
    if (
        min_score is not None
        and max_score is not None
        and min_score > max_score
    ):
        raise ValueError("min_score cannot be greater than max_score.")

    offset = (page - 1) * page_size
    summary_rows = list_report_summaries_for_user(
        db=db,
        user_id=current_user.id,
        limit=page_size,
        offset=offset,
        company=company,
        industry=industry,
        from_date=from_date,
        to_date=to_date,
        min_score=min_score,
        max_score=max_score,
        status=status,
    )
    total = count_research_reports_for_user(
        db=db,
        user_id=current_user.id,
        company=company,
        industry=industry,
        from_date=from_date,
        to_date=to_date,
        min_score=min_score,
        max_score=max_score,
        status=status,
    )

    items = [
        ReportSummary(
            id=report.id,
            research_request_id=report.research_request_id,
            company_id=report.company_id,
            company_name=company_name,
            report_kind=report.report_kind.value,
            opportunity_score=report.opportunity_score,
            contact_recommendation=report.contact_recommendation,
            review_status=report.review_status.value,
            generated_at=report.generated_at,
        )
        for report, company_name in summary_rows
    ]

    return ReportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
