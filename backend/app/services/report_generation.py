from datetime import datetime, timezone
import time
from uuid import UUID

from app.ai.context import MAX_EVIDENCE_SOURCES, build_research_evidence_context
from app.ai.crew import run_sales_intelligence_crew
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.research_report import ResearchReport
from app.models.research_request import ResearchStatus
from app.repositories.companies import get_company_by_id
from app.repositories.research_reports import (
    create_research_report,
    get_research_report_by_id_for_user,
    get_research_report_for_user,
)
from app.repositories.research_requests import get_research_request_for_user
from app.repositories.research_sources import list_research_sources_for_user
from app.schemas.company_discovery import DiscoveryObjective
from app.schemas.evidence_gate import EvidenceGateState, SourceAdmissionState
from app.services.company_discovery import build_objective_context
from app.services.evidence_gate import requires_deep_qualification

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
        if requires_deep_qualification(research_request):
            logger.warning(
                "Background generation skipped: request %s needs deep qualification.",
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

        sources = list_research_sources_for_user(
            db=db,
            research_request_id=research_request.id,
            user_id=user_id,
            limit=MAX_EVIDENCE_SOURCES,
            admission_state=SourceAdmissionState.ACCEPTED,
        )
        if not sources:
            logger.error("Background generation failed: no sources for request %s.", request_id)
            return

        report = None
        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            try:
                evidence_context = build_research_evidence_context(sources)
                report = run_sales_intelligence_crew(
                    company_name=company.name,
                    evidence_context=evidence_context,
                    objective_context=_objective_context_from_request(
                        research_request,
                    ),
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
            opportunity_score=report.opportunity_assessment.score,
            contact_recommendation=report.contact_recommendation.recommendation,
            generated_at=datetime.now(timezone.utc),
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
        if requires_deep_qualification(research_request):
            logger.warning(
                "Background regeneration skipped: report %s needs deep qualification.",
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

        sources = list_research_sources_for_user(
            db=db,
            research_request_id=existing_report.research_request_id,
            user_id=user_id,
            limit=MAX_EVIDENCE_SOURCES,
            admission_state=SourceAdmissionState.ACCEPTED,
        )
        if not sources:
            logger.error("Background regeneration failed: no sources for report %s.", report_id)
            return

        try:
            evidence_context = build_research_evidence_context(sources)
            objective_context = _objective_context_from_request(research_request)
            report = run_sales_intelligence_crew(
                company_name=company.name,
                evidence_context=evidence_context,
                guidance=instruction,
                objective_context=objective_context,
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
            opportunity_score=report.opportunity_assessment.score,
            contact_recommendation=report.contact_recommendation.recommendation,
            generated_at=datetime.now(timezone.utc),
        )
        logger.info("Background regeneration completed for report %s.", report_id)
    finally:
        db.close()
