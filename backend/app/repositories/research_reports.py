from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.research_report import ResearchReport


def create_research_report(
    db: Session,
    research_request_id: UUID,
    company_id: UUID,
    user_id: UUID,
    report_data: dict[str, Any],
    opportunity_score: int | None,
    contact_recommendation: str | None,
    generated_at: datetime,
) -> ResearchReport:
    report = ResearchReport(
        research_request_id=research_request_id,
        company_id=company_id,
        user_id=user_id,
        report_data=report_data,
        opportunity_score=opportunity_score,
        contact_recommendation=contact_recommendation,
        generated_at=generated_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_research_report_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
) -> ResearchReport | None:
    statement = select(ResearchReport).where(
        ResearchReport.research_request_id == research_request_id,
        ResearchReport.user_id == user_id,
    )
    return db.scalar(statement)


def get_research_report_by_id_for_user(
    db: Session,
    report_id: UUID,
    user_id: UUID,
) -> ResearchReport | None:
    statement = select(ResearchReport).where(
        ResearchReport.id == report_id,
        ResearchReport.user_id == user_id,
    )
    return db.scalar(statement)


def list_research_reports_for_user(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[ResearchReport]:
    statement = (
        select(ResearchReport)
        .where(ResearchReport.user_id == user_id)
        .order_by(ResearchReport.generated_at.desc())
        .limit(limit)
    )
    return db.scalars(statement).all()
