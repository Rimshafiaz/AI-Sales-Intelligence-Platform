from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.context import MAX_EVIDENCE_SOURCES, build_research_evidence_context
from app.ai.crew import run_sales_intelligence_crew
from app.models.research_report import ResearchReport
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.repositories.companies import get_company_by_id
from app.repositories.research_reports import (
    create_research_report,
    get_research_report_by_id_for_user,
    get_research_report_for_user,
)
from app.repositories.research_requests import get_research_request_for_user
from app.repositories.research_sources import list_research_sources_for_user


class ReportGenerationConflict(Exception):
    pass


class ReportGenerationFailed(Exception):
    pass


def generate_report_for_request(
    db: Session,
    request_id: UUID,
    current_user: User,
) -> ResearchReport | None:
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
    )
    if research_request is None:
        return None

    if research_request.status != ResearchStatus.COMPLETED:
        raise ReportGenerationConflict(
            "Research request is not completed yet."
        )

    existing_report = get_research_report_for_user(
        db=db,
        research_request_id=research_request.id,
        user_id=current_user.id,
    )
    if existing_report is not None:
        raise ReportGenerationConflict(
            "A report already exists for this research request."
        )

    company = get_company_by_id(
        db=db,
        company_id=research_request.company_id,
        user_id=current_user.id,
    )
    if company is None:
        raise ReportGenerationFailed(
            "Company for this research request could not be loaded."
        )

    sources = list_research_sources_for_user(
        db=db,
        research_request_id=research_request.id,
        user_id=current_user.id,
        limit=MAX_EVIDENCE_SOURCES,
    )
    if not sources:
        raise ReportGenerationFailed(
            "No saved evidence sources are available for this research request."
        )

    try:
        evidence_context = build_research_evidence_context(sources)
        report = run_sales_intelligence_crew(
            company_name=company.name,
            evidence_context=evidence_context,
        )
    except Exception as error:
        db.rollback()
        raise ReportGenerationFailed(
            "Report generation failed. Please try again."
        ) from error

    saved_report = create_research_report(
        db=db,
        research_request_id=research_request.id,
        company_id=research_request.company_id,
        user_id=current_user.id,
        report_data=report.model_dump(mode="json"),
        opportunity_score=report.opportunity_assessment.score,
        contact_recommendation=report.contact_recommendation.recommendation,
        generated_at=datetime.now(timezone.utc),
    )

    return saved_report


def regenerate_report_for_user(
    db: Session,
    report_id: UUID,
    current_user: User,
    instruction: str | None,
) -> ResearchReport | None:
    existing_report = get_research_report_by_id_for_user(
        db=db,
        report_id=report_id,
        user_id=current_user.id,
    )
    if existing_report is None:
        return None

    company = get_company_by_id(
        db=db,
        company_id=existing_report.company_id,
        user_id=current_user.id,
    )
    if company is None:
        raise ReportGenerationFailed(
            "Company for this report could not be loaded."
        )

    sources = list_research_sources_for_user(
        db=db,
        research_request_id=existing_report.research_request_id,
        user_id=current_user.id,
        limit=MAX_EVIDENCE_SOURCES,
    )
    if not sources:
        raise ReportGenerationFailed(
            "No saved evidence sources are available for this report."
        )

    try:
        evidence_context = build_research_evidence_context(sources)
        report = run_sales_intelligence_crew(
            company_name=company.name,
            evidence_context=evidence_context,
            guidance=instruction,
        )
    except Exception as error:
        db.rollback()
        raise ReportGenerationFailed(
            "Report regeneration failed. Please try again."
        ) from error

    return create_research_report(
        db=db,
        research_request_id=existing_report.research_request_id,
        company_id=existing_report.company_id,
        user_id=current_user.id,
        report_data=report.model_dump(mode="json"),
        opportunity_score=report.opportunity_assessment.score,
        contact_recommendation=report.contact_recommendation.recommendation,
        generated_at=datetime.now(timezone.utc),
    )
