from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.company import Company
from app.models.research_report import ReportReviewStatus, ResearchReport


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


def approve_research_report(
    db: Session,
    report_id: UUID,
    user_id: UUID,
) -> ResearchReport | None:
    report = get_research_report_by_id_for_user(
        db=db,
        report_id=report_id,
        user_id=user_id,
    )
    if report is None:
        return None

    if report.review_status == ReportReviewStatus.APPROVED:
        return report

    report.review_status = ReportReviewStatus.APPROVED
    report.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report


def save_report_edits(
    db: Session,
    report: ResearchReport,
    report_data: dict[str, Any],
    review_note: str | None,
) -> ResearchReport:
    report.report_data = report_data
    report.review_note = review_note
    report.review_status = ReportReviewStatus.DRAFT
    report.approved_at = None
    db.commit()
    db.refresh(report)
    return report


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


def _report_filter_conditions(
    user_id: UUID,
    company: str | None,
    industry: str | None,
    from_date: date | None,
    to_date: date | None,
    min_score: int | None,
    max_score: int | None,
    status: ReportReviewStatus | None,
) -> list:
    conditions = [ResearchReport.user_id == user_id]

    if company:
        conditions.append(Company.name.ilike(f"%{company}%"))
    if industry:
        conditions.append(
            ResearchReport.report_data["company_profile"]["industry"]["statement"]
            .astext.ilike(f"%{industry}%")
        )
    if from_date is not None:
        conditions.append(
            ResearchReport.generated_at
            >= datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        )
    if to_date is not None:
        conditions.append(
            ResearchReport.generated_at
            < datetime.combine(
                to_date + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
        )
    if min_score is not None:
        conditions.append(ResearchReport.opportunity_score >= min_score)
    if max_score is not None:
        conditions.append(ResearchReport.opportunity_score <= max_score)
    if status is not None:
        conditions.append(ResearchReport.review_status == status)

    return conditions


def list_report_summaries_for_user(
    db: Session,
    user_id: UUID,
    limit: int,
    offset: int,
    company: str | None = None,
    industry: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    status: ReportReviewStatus | None = None,
) -> list[tuple[ResearchReport, str]]:
    statement = (
        select(ResearchReport, Company.name)
        .join(Company, ResearchReport.company_id == Company.id)
        .where(
            *_report_filter_conditions(
                user_id,
                company,
                industry,
                from_date,
                to_date,
                min_score,
                max_score,
                status,
            )
        )
        .order_by(ResearchReport.generated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.execute(statement).all()


def count_research_reports_for_user(
    db: Session,
    user_id: UUID,
    company: str | None = None,
    industry: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    status: ReportReviewStatus | None = None,
) -> int:
    statement = (
        select(func.count(ResearchReport.id))
        .join(Company, ResearchReport.company_id == Company.id)
        .where(
            *_report_filter_conditions(
                user_id,
                company,
                industry,
                from_date,
                to_date,
                min_score,
                max_score,
                status,
            )
        )
    )
    return db.scalar(statement)
