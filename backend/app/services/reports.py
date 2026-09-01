from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.research_reports import get_research_report_by_id_for_user
from app.repositories.research_sources import list_research_sources_for_user
from app.schemas.research_report import ReportDetailResponse, ResearchReportResponse
from app.schemas.research_source import ResearchSourceResponse


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

    return ReportDetailResponse(
        report=ResearchReportResponse.model_validate(report),
        sources=[
            ResearchSourceResponse.model_validate(source) for source in sources
        ],
    )
