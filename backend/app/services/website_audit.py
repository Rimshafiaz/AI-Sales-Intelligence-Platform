from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.pagespeed import (
    PageSpeedInsightsProvider,
    PageSpeedProviderError,
    create_pagespeed_provider,
)
from app.integrations.website_metadata import WebsiteMetadataCollector
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.models.research_request import ResearchStatus
from app.repositories.research_evidence import (
    list_research_evidence_for_user,
    upsert_research_evidence,
)
from app.repositories.research_requests import (
    save_website_audit_result,
    save_website_check_execution,
)
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import (
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelSelection,
)
from app.schemas.website_audit import (
    WebsiteAuditResult,
    WebsiteAuditState,
    WebsiteCheckResult,
    WebsiteCheckState,
    WebsiteCheckExecution,
)
from app.services.evidence_gate import target_from_research_request
from app.services.industry_conversion_paths import analyze_conversion_paths
from app.services.local_business_discovery import LocalBusinessDiscoveryError, resolve_industry
from app.services.opportunity_model_catalog import get_opportunity_model


class WebsiteAuditError(ValueError):
    pass


CONVERSION_PATH_SIGNALS = {
    EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_FITNESS_ENQUIRY_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_RETAIL_PRODUCT_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_CLINIC_PATIENT_PATH_INCOMPLETE,
}


def audit_research_website(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    provider: PageSpeedInsightsProvider | None = None,
    website_collector: WebsiteMetadataCollector | None = None,
) -> ResearchRequest:
    conversion = inspect_verified_website_conversion_paths(
        db,
        research_request,
        company,
        selection,
        research_request.user_id,
        website_collector,
    )
    mobile = measure_verified_website_mobile_performance(
        db,
        research_request,
        company,
        selection,
        research_request.user_id,
        provider,
    )
    completed = {WebsiteCheckState.EVIDENCE_FOUND, WebsiteCheckState.ALREADY_AVAILABLE}
    if mobile.state in completed:
        return _save_audit_result(
            db,
            research_request.id,
            WebsiteAuditState.COMPLETED,
            mobile.reason,
        )
    if conversion.state in completed | {WebsiteCheckState.NO_GAP_OBSERVED}:
        return _save_audit_result(
            db,
            research_request.id,
            WebsiteAuditState.COMPLETED,
            conversion.reason,
        )
    reason = next(
        (
            result.reason
            for result in (mobile, conversion)
            if result.state is WebsiteCheckState.UNAVAILABLE
        ),
        "No selected opportunity model permits a website audit capability.",
    )
    return _save_unavailable(db, research_request.id, reason)


def measure_verified_website_mobile_performance(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
    provider: PageSpeedInsightsProvider | None = None,
) -> WebsiteCheckResult:
    target, models = _guard_website_capability(
        db, research_request, company, selection, expected_user_id
    )
    if not any(
        EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED
        in model.required_signal_types
        for model in models
    ):
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "mobile_performance",
            WebsiteCheckResult(
                WebsiteCheckState.NOT_PERMITTED,
                "No selected opportunity model requires mobile-performance evidence.",
            ),
        )
    if not target.identity_verified or target.official_website is None:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "mobile_performance",
            WebsiteCheckResult(
                WebsiteCheckState.UNAVAILABLE,
                "No verified official website is available to audit.",
            ),
        )
    existing = _existing_evidence(
        db,
        research_request,
        expected_user_id,
        EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
    )
    if existing is not None and existing.numeric_value is not None:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "mobile_performance",
            _evidence_result(
                WebsiteCheckState.ALREADY_AVAILABLE,
                "A valid mobile performance measurement is already available.",
                existing,
            ),
        )
    try:
        audit_provider = provider or create_pagespeed_provider(settings.pagespeed_api_key)
        measurement = audit_provider.measure_mobile(target.official_website)
    except (PageSpeedProviderError, ValueError) as error:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "mobile_performance",
            WebsiteCheckResult(WebsiteCheckState.UNAVAILABLE, str(error)),
        )

    observed_at = datetime.now(UTC)
    evidence = upsert_research_evidence(
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
    return _record_execution(
        db,
        research_request,
        expected_user_id,
        "mobile_performance",
        _evidence_result(
            WebsiteCheckState.EVIDENCE_FOUND,
            "A factual mobile performance measurement was saved from PageSpeed Insights.",
            evidence,
        ),
    )


def inspect_verified_website_conversion_paths(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
    website_collector: WebsiteMetadataCollector | None = None,
) -> WebsiteCheckResult:
    target, models = _guard_website_capability(
        db, research_request, company, selection, expected_user_id
    )
    permitted_signals = {
        signal
        for model in models
        for signal in model.required_signal_types
        if signal in CONVERSION_PATH_SIGNALS
    }
    if not permitted_signals:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "conversion_paths",
            WebsiteCheckResult(
                WebsiteCheckState.NOT_PERMITTED,
                "No selected applicable opportunity model supports automated conversion-path inspection.",
            ),
        )
    if not target.identity_verified or target.official_website is None:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "conversion_paths",
            WebsiteCheckResult(
                WebsiteCheckState.UNAVAILABLE,
                "No verified official website is available to inspect.",
            ),
        )
    for signal in permitted_signals:
        existing = _existing_evidence(db, research_request, expected_user_id, signal)
        if existing is not None:
            return _record_execution(
                db,
                research_request,
                expected_user_id,
                "conversion_paths",
                _evidence_result(
                    WebsiteCheckState.ALREADY_AVAILABLE,
                    "Conversion-path evidence is already available.",
                    existing,
                ),
            )
    industry = _selected_industry(db, selection)
    if industry is None or not any(industry in model.applicable_industries for model in models):
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "conversion_paths",
            WebsiteCheckResult(
                WebsiteCheckState.NOT_PERMITTED,
                "The selected conversion-path model is not applicable to the trusted industry.",
            ),
        )
    snapshot = (website_collector or WebsiteMetadataCollector()).collect_conversion_snapshot(
        target.official_website
    )
    if snapshot is None:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "conversion_paths",
            WebsiteCheckResult(
                WebsiteCheckState.UNAVAILABLE,
                "The verified official website could not be inspected.",
            ),
        )
    finding = analyze_conversion_paths(industry, snapshot.links)
    if finding is None or finding.signal_type not in permitted_signals:
        return _record_execution(
            db,
            research_request,
            expected_user_id,
            "conversion_paths",
            WebsiteCheckResult(
                WebsiteCheckState.NO_GAP_OBSERVED,
                "The completed inspection found no qualifying conversion-path gap for the selected models.",
            ),
        )
    observed_at = datetime.now(UTC)
    evidence = upsert_research_evidence(
        db=db,
        research_request_id=research_request.id,
        signal_type=finding.signal_type,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value=finding.supporting_value,
        numeric_value=None,
        source=EvidenceSource(
            provider="official_website",
            source_url=snapshot.url,
            retrieved_at=observed_at,
        ),
        source_identity_key=f"website_conversion:{industry.value}:{snapshot.url}",
        captured_at=observed_at,
    )
    return _record_execution(
        db,
        research_request,
        expected_user_id,
        "conversion_paths",
        _evidence_result(
            WebsiteCheckState.EVIDENCE_FOUND,
            "Deterministic conversion-path evidence was saved from the verified official website.",
            evidence,
        ),
    )


def _guard_website_capability(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
):
    if research_request.user_id != expected_user_id or company.user_id != expected_user_id:
        raise WebsiteAuditError("Research request is not available to this user.")
    if research_request.company_id != company.id:
        raise WebsiteAuditError("Research request does not belong to the supplied company.")
    if research_request.status is not ResearchStatus.COMPLETED:
        raise WebsiteAuditError("Finish the evidence review before auditing a website.")
    if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
        raise WebsiteAuditError("Accepted evidence is required before a website audit.")
    if (
        selection is None
        or research_request.campaign_candidate_selection_id != selection.id
        or selection.company_id != company.id
    ):
        return target_from_research_request(research_request, company, selection), ()
    run = db.get(CampaignRun, selection.campaign_run_id)
    if run is None:
        raise WebsiteAuditError("The selected campaign run is unavailable.")
    try:
        selected = OpportunityModelSelection.model_validate(run.model_selection_snapshot)
    except ValueError as error:
        raise WebsiteAuditError("The selected opportunity-model scope is invalid.") from error
    return (
        target_from_research_request(research_request, company, selection),
        tuple(get_opportunity_model(model_id) for model_id in selected.model_ids),
    )


def _selected_industry(
    db: Session,
    selection: CampaignCandidateSelection | None,
):
    if selection is None:
        return None
    run = db.get(CampaignRun, selection.campaign_run_id)
    if run is None:
        return None
    try:
        return resolve_industry(str(run.criteria_snapshot.get("business_category", "")))
    except LocalBusinessDiscoveryError:
        return None


def _existing_evidence(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    signal_type: EvidenceSignalType,
):
    return next(
        (
            evidence
            for evidence in list_research_evidence_for_user(
                db, research_request.id, expected_user_id
            )
            if evidence.signal_type == signal_type.value
        ),
        None,
    )


def _evidence_result(state, reason, evidence) -> WebsiteCheckResult:
    return WebsiteCheckResult(
        state=state,
        reason=reason,
        signal_type=EvidenceSignalType(evidence.signal_type),
        numeric_value=evidence.numeric_value,
        source_identity_key=evidence.source_identity_key,
    )


def _record_execution(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    capability: Literal["mobile_performance", "conversion_paths"],
    result: WebsiteCheckResult,
) -> WebsiteCheckResult:
    save_website_check_execution(
        db,
        research_request,
        expected_user_id,
        capability,
        WebsiteCheckExecution(
            state=result.state,
            reason=result.reason,
            checked_at=datetime.now(UTC),
        ),
    )
    return result


def _save_unavailable(
    db: Session,
    request_id: UUID,
    reason: str,
) -> ResearchRequest:
    return _save_audit_result(db, request_id, WebsiteAuditState.UNAVAILABLE, reason)


def _save_audit_result(
    db: Session,
    request_id: UUID,
    state: WebsiteAuditState,
    reason: str,
) -> ResearchRequest:
    result = WebsiteAuditResult(
        state=state,
        reason=reason,
        audited_at=datetime.now(UTC),
    )
    saved_request = save_website_audit_result(db, request_id, result)
    if saved_request is None:
        raise WebsiteAuditError("Research request was not found while saving the website audit.")
    return saved_request
