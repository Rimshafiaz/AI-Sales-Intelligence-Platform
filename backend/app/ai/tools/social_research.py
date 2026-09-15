from uuid import UUID

from crewai.tools import BaseTool, tool
from sqlalchemy.orm import Session

from app.integrations.social_enrichment import social_profile_target
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.repositories.research_evidence import list_research_evidence_for_user
from app.repositories.research_social_observations import list_social_observations_for_user
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelSelection,
    ServiceFamily,
)
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.social_audit import (
    SocialCandidateDiscoveryResult,
    SocialCandidateDiscoveryState,
    SocialCandidateEnrichmentResult,
    SocialEnrichmentResultState,
    SocialProfileCandidate,
)
from app.schemas.social_research import (
    GroundedSocialEvidenceResult,
    GroundedSocialObservation,
    SelectedSocialModel,
    SocialIdentityState,
)
from app.services.evidence_gate import target_from_research_request
from app.services.opportunity_model_catalog import get_opportunity_model
from app.services.social_audit import (
    SocialAuditError,
    discover_social_profile_candidates as discover_candidates,
    enrich_social_profile_candidates as enrich_candidates,
    verify_social_profiles_and_measure_activity as verify_profiles,
)


SOCIAL_SIGNALS = {
    EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
    EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED,
    EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED,
    EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED,
    EvidenceSignalType.SOCIAL_DORMANCY_MEASURED,
}


def build_social_research_tools(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> tuple[BaseTool, BaseTool, BaseTool, BaseTool]:
    _require_bound_context(research_request, company, selection, expected_user_id)
    discovered: SocialCandidateDiscoveryResult | None = None

    @tool("read_grounded_social_evidence", max_usage_count=3)
    def read_grounded_social_evidence() -> str:
        """Read owned canonical social evidence, observations, and selected requirements."""
        return build_grounded_social_evidence(
            db, research_request, company, selection, expected_user_id
        ).model_dump_json()

    @tool("discover_social_profile_candidates", max_usage_count=1)
    def discover_social_profile_candidates() -> str:
        """Find bounded server-controlled social profile candidates for the trusted business."""
        nonlocal discovered
        discovered = discover_candidates(
            db, research_request, company, selection, expected_user_id
        )
        return discovered.model_dump_json()

    @tool("enrich_social_profile_candidates", max_usage_count=1)
    def enrich_social_profile_candidates() -> str:
        """Enrich only candidates produced by the bound deterministic discovery capability."""
        if discovered is None:
            return SocialCandidateEnrichmentResult(
                state=SocialEnrichmentResultState.NO_CANDIDATES,
                reason="Run bounded candidate discovery before enrichment.",
            ).model_dump_json()
        return enrich_candidates(
            db,
            research_request,
            company,
            selection,
            expected_user_id,
            discovered,
        ).model_dump_json()

    @tool("verify_social_profiles_and_measure_activity", max_usage_count=1)
    def verify_social_profiles_and_measure_activity() -> str:
        """Verify owned persisted observations and derive factual social activity evidence."""
        return verify_profiles(
            db, research_request, company, selection, expected_user_id
        ).model_dump_json()

    return (
        read_grounded_social_evidence,
        discover_social_profile_candidates,
        enrich_social_profile_candidates,
        verify_social_profiles_and_measure_activity,
    )


def build_grounded_social_evidence(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> GroundedSocialEvidenceResult:
    _require_bound_context(research_request, company, selection, expected_user_id)
    target = target_from_research_request(research_request, company, selection)
    models = _selected_social_models(research_request)
    evidence = _persisted_evidence(db, research_request, expected_user_id)
    evidence.extend(_selection_evidence(selection))
    if target.identity_verified:
        source = _target_source(research_request)
        if source is not None:
            evidence.append(
                BriefEvidence(
                    key="resolved_target:identity",
                    signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
                    evidence_type=EvidenceType.OBSERVED,
                    supporting_value="The research target was resolved to a verified business identity.",
                    source=source,
                    captured_at=source.retrieved_at,
                )
            )
    unique = {item.key: item for item in evidence if item.signal_type in SOCIAL_SIGNALS}
    required = {
        signal
        for model in models
        for signal in model.required_evidence_signals
        if signal in SOCIAL_SIGNALS
    }
    available = {item.signal_type for item in unique.values()}
    observations = list_social_observations_for_user(
        db, research_request.id, expected_user_id
    )
    return GroundedSocialEvidenceResult(
        identity_state=(
            SocialIdentityState.VERIFIED
            if target.identity_verified
            else SocialIdentityState.UNRESOLVED
        ),
        selected_models=models,
        candidate_profiles=_campaign_candidates(selection),
        observations=[_grounded_observation(item) for item in observations],
        evidence=list(unique.values()),
        unresolved_requirements=sorted(required - available, key=lambda item: item.value),
        audit_state=research_request.social_audit_state,
        audit_reason=research_request.social_audit_reason,
    )


def _require_bound_context(research_request, company, selection, expected_user_id) -> None:
    if research_request.user_id != expected_user_id or company.user_id != expected_user_id:
        raise SocialAuditError("Research request is not available to this user.")
    if research_request.company_id != company.id:
        raise SocialAuditError("Research request does not belong to the supplied company.")
    if selection is not None and (
        research_request.campaign_candidate_selection_id != selection.id
        or selection.company_id != company.id
    ):
        raise SocialAuditError("Campaign selection does not belong to this research request.")


def _selected_social_models(research_request) -> list[SelectedSocialModel]:
    try:
        selected = OpportunityModelSelection.model_validate(
            research_request.opportunity_model_selection
        )
    except ValueError as error:
        raise SocialAuditError("The selected opportunity-model scope is invalid.") from error
    return [
        SelectedSocialModel(
            model_id=model.id,
            required_evidence_signals=list(model.required_signal_types),
        )
        for model_id in selected.model_ids
        if (model := get_opportunity_model(model_id)).service_family
        is ServiceFamily.SOCIAL_PRESENCE_CONTENT
    ]


def _campaign_candidates(selection) -> list[SocialProfileCandidate]:
    values = selection.candidate_snapshot.get("social_profile_urls", []) if selection else []
    candidates = []
    for value in values:
        target = social_profile_target(value)
        if target is not None:
            candidates.append(
                SocialProfileCandidate(
                    profile_url=target.profile_url,
                    platform=target.platform,
                    handle=target.handle,
                    source="campaign",
                )
            )
    return candidates[:3]


def _persisted_evidence(db, research_request, expected_user_id) -> list[BriefEvidence]:
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
        if EvidenceSignalType(item.signal_type) in SOCIAL_SIGNALS
    ]


def _selection_evidence(selection) -> list[BriefEvidence]:
    result = []
    for index, value in enumerate(selection.evidence_snapshot if selection else []):
        try:
            signal = EvidenceSignal.model_validate(value)
        except ValueError:
            continue
        if signal.signal_type in SOCIAL_SIGNALS:
            result.append(
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
    return result


def _target_source(research_request) -> EvidenceSource | None:
    target = (research_request.objective or {}).get("resolved_target")
    source = target.get("source") if isinstance(target, dict) else None
    try:
        return EvidenceSource.model_validate(source)
    except ValueError:
        return None


def _grounded_observation(item) -> GroundedSocialObservation:
    return GroundedSocialObservation(
        key=f"social_observation:{item.id}",
        profile_url=item.profile_url,
        platform=item.platform,
        state=item.state,
        display_name=item.display_name,
        handle=item.handle,
        external_url=item.external_url,
        public_emails=item.public_emails,
        public_phones=item.public_phones,
        latest_public_post_at=item.latest_public_post_at,
        recent_public_post_dates=item.recent_public_post_dates,
        detail=item.detail,
    )
