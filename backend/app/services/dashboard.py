from sqlalchemy.orm import Session

from app.models.research_report import ReportReviewStatus
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.repositories.dashboard import (
    average_opportunity_score_for_user,
    count_distinct_companies_researched,
    count_distinct_industries_researched,
    list_most_researched_industries,
    list_recent_reports_with_company,
    list_recent_research_requests_with_company,
)
from app.repositories.research_reports import count_research_reports_for_user
from app.schemas.dashboard import ActivityEvent, DashboardSummaryResponse, IndustrySummary


MAX_MOST_RESEARCHED_INDUSTRIES = 3
ACTIVITY_LIMIT = 10
EVENT_FETCH_LIMIT = 10


def _build_activity_events(
    db: Session,
    user_id,
) -> list[ActivityEvent]:
    research_requests = list_recent_research_requests_with_company(
        db=db,
        user_id=user_id,
        limit=EVENT_FETCH_LIMIT,
    )
    reports = list_recent_reports_with_company(
        db=db,
        user_id=user_id,
        limit=EVENT_FETCH_LIMIT,
    )

    events: list[ActivityEvent] = []

    for request, company_name in research_requests:
        events.append(
            ActivityEvent(
                event_type="research_requested",
                company_name=company_name,
                status="pending",
                occurred_at=request.created_at,
            )
        )
        if request.status == ResearchStatus.COMPLETED and request.finished_at:
            events.append(
                ActivityEvent(
                    event_type="research_completed",
                    company_name=company_name,
                    status="completed",
                    occurred_at=request.finished_at,
                )
            )
        elif request.status == ResearchStatus.FAILED and request.finished_at:
            events.append(
                ActivityEvent(
                    event_type="research_failed",
                    company_name=company_name,
                    status="failed",
                    occurred_at=request.finished_at,
                )
            )

    for report, company_name in reports:
        events.append(
            ActivityEvent(
                event_type="report_generated",
                company_name=company_name,
                status="draft",
                occurred_at=report.generated_at,
            )
        )
        if (
            report.review_status == ReportReviewStatus.APPROVED
            and report.approved_at
        ):
            events.append(
                ActivityEvent(
                    event_type="report_approved",
                    company_name=company_name,
                    status="approved",
                    occurred_at=report.approved_at,
                )
            )

    events.sort(key=lambda event: event.occurred_at, reverse=True)
    return events[:ACTIVITY_LIMIT]


def get_dashboard_summary_for_user(
    db: Session,
    current_user: User,
) -> DashboardSummaryResponse:
    average_score = average_opportunity_score_for_user(
        db=db,
        user_id=current_user.id,
    )
    most_researched = list_most_researched_industries(
        db=db,
        user_id=current_user.id,
        limit=MAX_MOST_RESEARCHED_INDUSTRIES,
    )

    return DashboardSummaryResponse(
        reports_generated=count_research_reports_for_user(
            db=db,
            user_id=current_user.id,
        ),
        companies_researched=count_distinct_companies_researched(
            db=db,
            user_id=current_user.id,
        ),
        industries_researched=count_distinct_industries_researched(
            db=db,
            user_id=current_user.id,
        ),
        most_researched_industries=[
            IndustrySummary(industry=industry, report_count=report_count)
            for industry, report_count in most_researched
        ],
        average_opportunity_score=(
            round(average_score, 1) if average_score is not None else None
        ),
        recent_activity=_build_activity_events(
            db=db,
            user_id=current_user.id,
        ),
    )
