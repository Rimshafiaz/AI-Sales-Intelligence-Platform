from datetime import datetime, timezone
import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.context import MAX_EVIDENCE_SOURCES, build_research_evidence_context
from app.ai.crew import run_prospect_evidence_brief_crew, run_sales_intelligence_crew
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_report import ReportKind
from app.models.research_request import ResearchRequest, ResearchStatus
from app.repositories.companies import get_company_by_id
from app.repositories.research_reports import (
    create_research_report,
    get_research_report_by_id_for_user,
    get_research_report_for_user,
)
from app.repositories.research_requests import get_research_request_for_user
from app.repositories.research_sources import list_research_sources_for_user
from app.schemas.company_discovery import DiscoveryObjective
from app.schemas.prospect_evidence_brief import ProspectEvidenceBrief
from app.schemas.sales_intelligence_report import SalesIntelligenceReport
from app.schemas.evidence_gate import EvidenceGateState, SourceAdmissionState
from app.services.company_discovery import build_objective_context
from app.services.evidence_gate import requires_deep_qualification
from app.services.prospect_evidence_brief import build_prospect_evidence_brief_handoffs

logger = get_logger(__name__)

MAX_GENERATION_ATTEMPTS = 3
GENERATION_RETRY_DELAY_SECONDS = 45


def _objective_context_from_request(research_request) -> str | None:
    raw_objective = getattr(research_request, "objective", None)
    if not isinstance(raw_objective, dict):
        return None
    if "goal_type" in raw_objective:
        try:
            objective = DiscoveryObjective.model_validate(raw_objective)
        except Exception as error:
            logger.warning(
                "Stored discovery objective could not be validated for request %s: %s",
                getattr(research_request, "id", "?"),
                error,
            )
            return None
        return build_objective_context(
            raw_objective.get("goal")
            if isinstance(raw_objective.get("goal"), str)
            else None,
            objective,
        )
    goal = raw_objective.get("goal")
    offering = raw_objective.get("offering")
    if not isinstance(goal, str) and not isinstance(offering, str):
        return None
    lines = ["- Mode: manual known-prospect research"]
    if isinstance(goal, str):
        lines.append(f"- Original request: {goal}")
    if isinstance(offering, str):
        lines.append(f"- Offering: {offering}")
    if isinstance(raw_objective.get("region"), str):
        lines.append(f"- Target city/region: {raw_objective['region']}")
    if isinstance(raw_objective.get("website"), str):
        lines.append(f"- Provided website: {raw_objective['website']}")
    return "\n".join(lines)


def run_generation_background(request_id: UUID, user_id: UUID) -> None:
    db = SessionLocal()
    try:
        research_request = get_research_request_for_user(
            db=db,
            request_id=request_id,
            user_id=user_id,
        )
        if research_request is None:
            logger.warning("Background generation skipped: request %s not found.", request_id)
            return
        if research_request.status != ResearchStatus.COMPLETED:
            logger.warning(
                "Background generation skipped: request %s is not completed.", request_id
            )
            return
        if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
            logger.warning(
                "Background generation skipped: request %s has not passed the evidence gate.",
                request_id,
            )
            return
        existing_report = get_research_report_for_user(
            db=db,
            research_request_id=research_request.id,
            user_id=user_id,
        )
        if existing_report is not None:
            logger.warning(
                "Background generation skipped: report already exists for request %s.",
                request_id,
            )
            return

        company = get_company_by_id(
            db=db,
            company_id=research_request.company_id,
            user_id=user_id,
        )
        if company is None:
            logger.error("Background generation failed: company missing for request %s.", request_id)
            return

        report = None
        report_kind = ReportKind.LEGACY_SALES_INTELLIGENCE
        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            try:
                report, report_kind = _generate_report(
                    db,
                    research_request,
                    company,
                )
                break
            except Exception as error:
                db.rollback()
                logger.warning(
                    "Generation attempt %d/%d failed for request %s: %s",
                    attempt,
                    MAX_GENERATION_ATTEMPTS,
                    request_id,
                    error,
                )
                if attempt < MAX_GENERATION_ATTEMPTS:
                    time.sleep(GENERATION_RETRY_DELAY_SECONDS)
        if report is None:
            logger.error(
                "Background generation failed after %d attempts for request %s.",
                MAX_GENERATION_ATTEMPTS,
                request_id,
            )
            return

        create_research_report(
            db=db,
            research_request_id=research_request.id,
            company_id=research_request.company_id,
            user_id=user_id,
            report_data=report.model_dump(mode="json"),
            opportunity_score=(
                report.opportunity_assessment.score
                if report_kind is ReportKind.LEGACY_SALES_INTELLIGENCE
                else None
            ),
            contact_recommendation=(
                report.contact_recommendation.recommendation
                if report_kind is ReportKind.LEGACY_SALES_INTELLIGENCE
                else None
            ),
            generated_at=datetime.now(timezone.utc),
            report_kind=report_kind,
        )
        logger.info("Background generation completed for request %s.", request_id)
    finally:
        db.close()


def run_regeneration_background(
    report_id: UUID,
    user_id: UUID,
    instruction: str | None,
) -> None:
    db = SessionLocal()
    try:
        existing_report = get_research_report_by_id_for_user(
            db=db,
            report_id=report_id,
            user_id=user_id,
        )
        if existing_report is None:
            logger.warning("Background regeneration skipped: report %s not found.", report_id)
            return

        research_request = get_research_request_for_user(
            db=db,
            request_id=existing_report.research_request_id,
            user_id=user_id,
        )
        if (
            research_request is None
            or research_request.evidence_gate_state
            is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH
        ):
            logger.warning(
                "Background regeneration skipped: report %s has not passed the evidence gate.",
                report_id,
            )
            return
        company = get_company_by_id(
            db=db,
            company_id=existing_report.company_id,
            user_id=user_id,
        )
        if company is None:
            logger.error("Background regeneration failed: company missing for report %s.", report_id)
            return

        try:
            report, report_kind = _generate_report(
                db,
                research_request,
                company,
                instruction,
            )
        except Exception as error:
            db.rollback()
            logger.error(
                "Background regeneration failed for report %s: %s",
                report_id,
                error,
                exc_info=True,
            )
            return

        create_research_report(
            db=db,
            research_request_id=existing_report.research_request_id,
            company_id=existing_report.company_id,
            user_id=user_id,
            report_data=report.model_dump(mode="json"),
            opportunity_score=(
                report.opportunity_assessment.score
                if report_kind is ReportKind.LEGACY_SALES_INTELLIGENCE
                else None
            ),
            contact_recommendation=(
                report.contact_recommendation.recommendation
                if report_kind is ReportKind.LEGACY_SALES_INTELLIGENCE
                else None
            ),
            generated_at=datetime.now(timezone.utc),
            report_kind=report_kind,
        )
        logger.info("Background regeneration completed for report %s.", report_id)
    finally:
        db.close()


def _generate_report(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    guidance: str | None = None,
) -> tuple[SalesIntelligenceReport | ProspectEvidenceBrief, ReportKind]:
    if requires_deep_qualification(research_request):
        selection = (
            db.get(
                CampaignCandidateSelection,
                research_request.campaign_candidate_selection_id,
            )
            if research_request.campaign_candidate_selection_id is not None
            else None
        )
        handoffs = build_prospect_evidence_brief_handoffs(
            db,
            research_request,
            company,
            selection,
        )
        return (
            run_prospect_evidence_brief_crew(handoffs),
            ReportKind.PROSPECT_EVIDENCE_BRIEF,
        )

    sources = list_research_sources_for_user(
        db=db,
        research_request_id=research_request.id,
        user_id=research_request.user_id,
        limit=MAX_EVIDENCE_SOURCES,
        admission_state=SourceAdmissionState.ACCEPTED,
    )
    if not sources:
        raise ValueError("No accepted evidence sources are available for report generation.")
    evidence_context = build_research_evidence_context(sources)
    return (
        run_sales_intelligence_crew(
            company_name=company.name,
            evidence_context=evidence_context,
            guidance=guidance,
            objective_context=_objective_context_from_request(research_request),
        ),
        ReportKind.LEGACY_SALES_INTELLIGENCE,
    )
