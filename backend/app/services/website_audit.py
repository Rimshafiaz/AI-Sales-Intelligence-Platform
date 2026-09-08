from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.pagespeed import (
    PageSpeedInsightsProvider,
    PageSpeedProviderError,
    create_pagespeed_provider,
)
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.models.research_request import ResearchStatus
from app.repositories.research_evidence import upsert_research_evidence
from app.repositories.research_requests import save_website_audit_result
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceSource, EvidenceType
from app.schemas.website_audit import WebsiteAuditResult, WebsiteAuditState
from app.services.evidence_gate import target_from_research_request


class WebsiteAuditError(ValueError):
    pass


def audit_research_website(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    provider: PageSpeedInsightsProvider | None = None,
) -> ResearchRequest:
    if research_request.status is not ResearchStatus.COMPLETED:
        raise WebsiteAuditError("Finish the evidence review before auditing a website.")
    if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
        raise WebsiteAuditError("Accepted evidence is required before a website audit.")

    target = target_from_research_request(research_request, company, selection)
    if not target.identity_verified or target.official_website is None:
        return _save_unavailable(
            db,
            research_request.id,
            "No verified official website is available to audit.",
        )

    try:
        audit_provider = provider or create_pagespeed_provider(settings.pagespeed_api_key)
        measurement = audit_provider.measure_mobile(target.official_website)
    except (PageSpeedProviderError, ValueError) as error:
        return _save_unavailable(db, research_request.id, str(error))

    observed_at = datetime.now(UTC)
    upsert_research_evidence(
        db=db,
        research_request_id=research_request.id,
        signal_type=EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value=(
            "PageSpeed Insights measured a mobile performance score of "
            f"{measurement.score:g}/100 for the verified official website."
        ),
        numeric_value=measurement.score,
        source=EvidenceSource(
            provider="pagespeed_insights",
            source_url=measurement.final_url,
            retrieved_at=measurement.retrieved_at,
        ),
        source_identity_key=f"pagespeed:{measurement.final_url}",
        captured_at=observed_at,
    )
    result = WebsiteAuditResult(
        state=WebsiteAuditState.COMPLETED,
        reason="A factual mobile performance measurement was saved from PageSpeed Insights.",
        audited_at=observed_at,
    )
    saved_request = save_website_audit_result(db, research_request.id, result)
    if saved_request is None:
        raise WebsiteAuditError("Research request was not found while saving the website audit.")
    return saved_request


def _save_unavailable(
    db: Session,
    request_id: UUID,
    reason: str,
) -> ResearchRequest:
    result = WebsiteAuditResult(
        state=WebsiteAuditState.UNAVAILABLE,
        reason=reason,
        audited_at=datetime.now(UTC),
    )
    saved_request = save_website_audit_result(db, request_id, result)
    if saved_request is None:
        raise WebsiteAuditError("Research request was not found while saving the website audit.")
    return saved_request
