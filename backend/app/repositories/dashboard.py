from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.research_report import ResearchReport
from app.models.research_request import ResearchRequest
from app.repositories.research_reports import count_research_reports_for_user

_INDUSTRY_EXPRESSION = (
    ResearchReport.report_data["company_profile"]["industry"]["statement"].astext
)


def count_distinct_companies_researched(
    db: Session,
    user_id: UUID,
) -> int:
    statement = select(
        func.count(func.distinct(ResearchReport.company_id))
    ).where(ResearchReport.user_id == user_id)
    return db.scalar(statement)


def count_distinct_industries_researched(
    db: Session,
    user_id: UUID,
) -> int:
    statement = select(
        func.count(func.distinct(_INDUSTRY_EXPRESSION))
    ).where(
        ResearchReport.user_id == user_id,
        _INDUSTRY_EXPRESSION.is_not(None),
    )
    return db.scalar(statement)


def list_most_researched_industries(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[str, int]]:
    statement = (
        select(
            _INDUSTRY_EXPRESSION,
            func.count(ResearchReport.id),
        )
        .where(
            ResearchReport.user_id == user_id,
            _INDUSTRY_EXPRESSION.is_not(None),
        )
        .group_by(_INDUSTRY_EXPRESSION)
        .order_by(func.count(ResearchReport.id).desc())
        .limit(limit)
    )
    return db.execute(statement).all()


def average_opportunity_score_for_user(
    db: Session,
    user_id: UUID,
) -> float | None:
    statement = select(func.avg(ResearchReport.opportunity_score)).where(
        ResearchReport.user_id == user_id
    )
    return db.scalar(statement)


def list_recent_research_requests_with_company(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[ResearchRequest, str]]:
    statement = (
        select(ResearchRequest, Company.name)
        .join(Company, ResearchRequest.company_id == Company.id)
        .where(ResearchRequest.user_id == user_id)
        .order_by(ResearchRequest.created_at.desc())
        .limit(limit)
    )
    return db.execute(statement).all()


def list_recent_reports_with_company(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[ResearchReport, str]]:
    statement = (
        select(ResearchReport, Company.name)
        .join(Company, ResearchReport.company_id == Company.id)
        .where(ResearchReport.user_id == user_id)
        .order_by(ResearchReport.generated_at.desc())
        .limit(limit)
    )
    return db.execute(statement).all()
