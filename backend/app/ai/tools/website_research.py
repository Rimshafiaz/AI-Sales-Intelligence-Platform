from uuid import UUID

from crewai.tools import BaseTool, tool
from sqlalchemy.orm import Session

from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.repositories.research_evidence import list_research_evidence_for_user
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelSelection,
    ServiceFamily,
)
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.website_research import (
    GroundedWebsiteEvidenceResult,
    SelectedWebsiteModel,
    VerifiedWebsiteTargetResult,
    WebsiteCapabilityResult,
    WebsiteTargetStatus,
)
from app.services.evidence_gate import target_from_research_request
from app.services.opportunity_model_catalog import get_opportunity_model
from app.services.website_audit import (
    WebsiteAuditError,
    inspect_verified_website_conversion_paths as inspect_conversion_paths,
    measure_verified_website_mobile_performance as measure_mobile_performance,
)


WEBSITE_SIGNALS = {
    EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
    EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED,
    EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE,
    EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
    EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY,
    EvidenceSignalType.WEBSITE_RESERVATION_PATH_MANUAL_ONLY,
    EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_FITNESS_ENQUIRY_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_RETAIL_PRODUCT_PATH_NOT_OBSERVED,
    EvidenceSignalType.WEBSITE_CLINIC_PATIENT_PATH_INCOMPLETE,
}


def build_website_research_tools(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> tuple[BaseTool, BaseTool, BaseTool, BaseTool]:
    _require_bound_context(research_request, company, selection, expected_user_id)

    @tool("get_verified_website_target", max_usage_count=1)
    def get_verified_website_target() -> str:
        """Read the already persisted trusted website target and its verification status."""
        return _target_result(research_request, company, selection).model_dump_json()

    @tool("measure_verified_website_mobile_performance", max_usage_count=1)
    def measure_verified_website_mobile_performance() -> str:
        """Measure mobile performance only when trusted scope and a verified website permit it."""
        result = measure_mobile_performance(
            db, research_request, company, selection, expected_user_id
        )
        return WebsiteCapabilityResult.model_validate(result.__dict__).model_dump_json()

    @tool("inspect_verified_website_conversion_paths", max_usage_count=1)
    def inspect_verified_website_conversion_paths() -> str:
        """Inspect deterministic conversion paths only when trusted selected scope permits it."""
        result = inspect_conversion_paths(
            db, research_request, company, selection, expected_user_id
        )
        return WebsiteCapabilityResult.model_validate(result.__dict__).model_dump_json()

    @tool("read_grounded_website_evidence", max_usage_count=3)
    def read_grounded_website_evidence() -> str:
        """Read owned canonical website evidence and unresolved selected-model requirements."""
        return build_grounded_website_evidence(
            db, research_request, company, selection, expected_user_id
        ).model_dump_json()

    return (
        get_verified_website_target,
        measure_verified_website_mobile_performance,
        inspect_verified_website_conversion_paths,
        read_grounded_website_evidence,
    )


def _require_bound_context(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> None:
    if research_request.user_id != expected_user_id or company.user_id != expected_user_id:
        raise WebsiteAuditError("Research request is not available to this user.")
    if research_request.company_id != company.id:
        raise WebsiteAuditError("Research request does not belong to the supplied company.")
    if selection is not None and (
        research_request.campaign_candidate_selection_id != selection.id
        or selection.company_id != company.id
    ):
        raise WebsiteAuditError("Campaign selection does not belong to this research request.")


def _target_result(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
) -> VerifiedWebsiteTargetResult:
    target = target_from_research_request(research_request, company, selection)
    source = _target_source(research_request, selection)
    if target.identity_verified and target.official_website:
        status = WebsiteTargetStatus.VERIFIED
        reason = "The persisted resolved target contains a verified official website."
    elif target.identity_verified and target.no_listed_official_website:
        status = WebsiteTargetStatus.NOT_VERIFIED
        reason = "The trusted provider record did not list an official website."
    else:
        status = WebsiteTargetStatus.UNRESOLVED
        reason = research_request.evidence_gate_reason or "No official website was verified."
    return VerifiedWebsiteTargetResult(
        website_status=status,
        official_website=target.official_website if status is WebsiteTargetStatus.VERIFIED else None,
        reason=reason,
        source=source,
    )


def build_grounded_website_evidence(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> GroundedWebsiteEvidenceResult:
    _require_bound_context(research_request, company, selection, expected_user_id)
    target_result = _target_result(research_request, company, selection)
    models = _selected_web_models(db, selection)
    evidence = _persisted_evidence(db, research_request, expected_user_id)
    evidence.extend(_selection_evidence(selection))
    evidence.extend(_target_evidence(research_request, company, selection))
    unique = {item.key: item for item in evidence if item.signal_type in WEBSITE_SIGNALS}
    available = {item.signal_type for item in unique.values()}
    required = {
        signal
        for model in models
        for signal in model.required_evidence_signals
        if signal in WEBSITE_SIGNALS
    }
    return GroundedWebsiteEvidenceResult(
        website_status=target_result.website_status,
        selected_models=models,
        evidence=list(unique.values()),
        unresolved_requirements=sorted(required - available, key=lambda item: item.value),
        audit_state=research_request.website_audit_state,
        audit_reason=research_request.website_audit_reason,
    )


def _selected_web_models(
    db: Session,
    selection: CampaignCandidateSelection | None,
) -> list[SelectedWebsiteModel]:
    if selection is None:
        return []
    run = db.get(CampaignRun, selection.campaign_run_id)
    if run is None:
        raise WebsiteAuditError("The selected campaign run is unavailable.")
    try:
        selected = OpportunityModelSelection.model_validate(run.model_selection_snapshot)
    except ValueError as error:
        raise WebsiteAuditError("The selected opportunity-model scope is invalid.") from error
    return [
        SelectedWebsiteModel(
            model_id=model.id,
            required_evidence_signals=list(model.required_signal_types),
        )
        for model_id in selected.model_ids
        if (model := get_opportunity_model(model_id)).service_family is ServiceFamily.WEB_CONVERSION
    ]


def _persisted_evidence(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
) -> list[BriefEvidence]:
    return [
        BriefEvidence(
            key=f"research_evidence:{item.id}",
            signal_type=EvidenceSignalType(item.signal_type),
            evidence_type=EvidenceType(item.evidence_type),
            supporting_value=item.supporting_value,
            numeric_value=item.numeric_value,
            source=EvidenceSource(
                provider=item.source_provider,
                provider_record_id=item.source_record_id,
                source_url=item.source_url,
                retrieved_at=item.retrieved_at,
            ),
            captured_at=item.captured_at,
        )
        for item in list_research_evidence_for_user(
            db, research_request.id, expected_user_id
        )
        if EvidenceSignalType(item.signal_type) in WEBSITE_SIGNALS
    ]


def _selection_evidence(
    selection: CampaignCandidateSelection | None,
) -> list[BriefEvidence]:
    if selection is None:
        return []
    evidence = []
    for index, value in enumerate(selection.evidence_snapshot):
        try:
            signal = EvidenceSignal.model_validate(value)
        except ValueError:
            continue
        if signal.signal_type in WEBSITE_SIGNALS:
            evidence.append(
                BriefEvidence(
                    key=f"selection_evidence:{selection.id}:{index}",
                    signal_type=signal.signal_type,
                    evidence_type=signal.evidence_type,
                    supporting_value=signal.supporting_value,
                    numeric_value=signal.numeric_value,
                    source=signal.source,
                    captured_at=signal.captured_at,
                )
            )
    candidate = selection.candidate_snapshot
    if candidate.get("website") is None and "local_places" in candidate.get(
        "discovery_source_types", []
    ):
        source = _candidate_source(candidate)
        if source is not None:
            evidence.append(
                BriefEvidence(
                    key=f"selection_candidate:{selection.id}:no_listed_official_website",
                    signal_type=EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE,
                    evidence_type=EvidenceType.OBSERVED,
                    supporting_value=(
                        "The traceable local discovery record did not list an official website."
                    ),
                    source=source,
                    captured_at=source.retrieved_at,
                )
            )
    return evidence


def _target_evidence(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
) -> list[BriefEvidence]:
    target = target_from_research_request(research_request, company, selection)
    source = _target_source(research_request, selection)
    if not target.identity_verified or source is None:
        return []
    evidence = [
        BriefEvidence(
            key="resolved_target:identity",
            signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value="The research target was resolved to a verified business identity.",
            source=source,
            captured_at=source.retrieved_at,
        )
    ]
    if target.official_website:
        evidence.append(
            BriefEvidence(
                key="resolved_target:official_website",
                signal_type=EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED,
                evidence_type=EvidenceType.OBSERVED,
                supporting_value="The resolved target includes a verified official website.",
                source=source,
                captured_at=source.retrieved_at,
            )
        )
    return evidence


def _target_source(
    research_request: ResearchRequest,
    selection: CampaignCandidateSelection | None,
) -> EvidenceSource | None:
    target = (research_request.objective or {}).get("resolved_target")
    if isinstance(target, dict) and isinstance(target.get("source"), dict):
        try:
            return EvidenceSource.model_validate(target["source"])
        except ValueError:
            return None
    return next((item.source for item in _selection_evidence(selection)), None)


def _candidate_source(candidate: dict) -> EvidenceSource | None:
    try:
        return EvidenceSource(
            provider=candidate["source_provider"],
            provider_record_id=candidate.get("source_record_id"),
            source_url=next(iter(candidate.get("supporting_source_urls", [])), None),
            retrieved_at=candidate["source_retrieved_at"],
        )
    except (KeyError, ValueError):
        return None
