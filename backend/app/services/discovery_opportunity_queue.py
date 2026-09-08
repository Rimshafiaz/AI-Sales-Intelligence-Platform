from app.schemas.discovery_shortlist import (
    CandidateShortlistInput,
    DiscoveryOpportunityQueueEntry,
    DiscoveryOpportunityQueueResponse,
    DiscoveryOpportunityReason,
    DiscoveryShortlistRequest,
    DiscoveryShortlistState,
    OpportunityModelShortlistEvaluation,
)
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelId,
)
from app.services.discovery_shortlist import shortlist_discovery_candidates


MOBILE_PERFORMANCE_RESEARCH_THRESHOLD = 50
SOCIAL_DORMANCY_RESEARCH_THRESHOLD_DAYS = 60


def build_discovery_opportunity_queue(
    request: DiscoveryShortlistRequest,
) -> DiscoveryOpportunityQueueResponse:
    shortlist = shortlist_discovery_candidates(request)
    candidates: list[DiscoveryOpportunityQueueEntry] = []
    needs_verification_count = 0

    for candidate_index, (candidate_input, shortlist_entry) in enumerate(
        zip(request.candidates, shortlist.candidates, strict=True)
    ):
        reasons = actionable_reasons(candidate_input, shortlist_entry.model_evaluations)
        if reasons:
            candidates.append(
                DiscoveryOpportunityQueueEntry(
                    candidate_index=candidate_index,
                    company_name=candidate_input.candidate.company_name,
                    reasons=reasons,
                )
            )
            continue
        if shortlist_entry.state in {
            DiscoveryShortlistState.NEEDS_IDENTITY_REVIEW,
            DiscoveryShortlistState.NEEDS_EVIDENCE,
        }:
            needs_verification_count += 1

    candidates.sort(key=opportunity_sort_key)
    return DiscoveryOpportunityQueueResponse(
        candidates=candidates,
        needs_verification_count=needs_verification_count,
        not_surfaced_count=len(request.candidates) - len(candidates) - needs_verification_count,
    )


def actionable_reasons(
    candidate_input: CandidateShortlistInput,
    evaluations: list[OpportunityModelShortlistEvaluation],
) -> list[DiscoveryOpportunityReason]:
    observed_signals = observed_evidence_by_type(candidate_input.evidence_signals)
    reasons = []
    for evaluation in evaluations:
        if evaluation.state is not DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH:
            continue
        reason = reason_for_eligible_model(
            candidate_input,
            evaluation.model_id,
            observed_signals,
        )
        if reason is not None:
            reasons.append(reason)
    return sorted(reasons, key=lambda reason: reason.model_id)


def observed_evidence_by_type(
    signals: list[EvidenceSignal],
) -> dict[EvidenceSignalType, EvidenceSignal]:
    selected: dict[EvidenceSignalType, EvidenceSignal] = {}
    for signal in signals:
        if signal.evidence_type is not EvidenceType.OBSERVED:
            continue
        existing = selected.get(signal.signal_type)
        if existing is None or evidence_order_key(signal) > evidence_order_key(existing):
            selected[signal.signal_type] = signal
    return selected


def evidence_order_key(signal: EvidenceSignal) -> tuple:
    return (
        signal.captured_at,
        signal.source.provider,
        signal.source.provider_record_id or "",
        str(signal.source.source_url or ""),
    )


def reason_for_eligible_model(
    candidate_input: CandidateShortlistInput,
    model_id: OpportunityModelId,
    observed_signals: dict[EvidenceSignalType, EvidenceSignal],
) -> DiscoveryOpportunityReason | None:
    if model_id == "web_conversion.no_verified_web_presence":
        return no_listed_website_reason(candidate_input, observed_signals)
    if model_id == "web_conversion.booking_contact_path":
        return reason_from_signal(
            model_id,
            EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY,
            observed_signals,
        )
    if model_id == "web_conversion.restaurant_reservation_path":
        return reason_from_signal(
            model_id,
            EvidenceSignalType.WEBSITE_RESERVATION_PATH_MANUAL_ONLY,
            observed_signals,
        )
    if model_id == "web_conversion.mobile_performance":
        return mobile_performance_reason(observed_signals)
    if model_id == "social_presence.dormant_official_presence":
        return social_dormancy_reason(observed_signals)
    return None


def no_listed_website_reason(
    candidate_input: CandidateShortlistInput,
    observed_signals: dict[EvidenceSignalType, EvidenceSignal],
) -> DiscoveryOpportunityReason | None:
    candidate = candidate_input.candidate
    identity_signal = observed_signals.get(
        EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED
    )
    if candidate.website is not None or identity_signal is None:
        return None
    source = EvidenceSource(
        provider=candidate.source_provider or "discovery",
        provider_record_id=candidate.source_record_id,
        source_url=(
            candidate.supporting_source_urls[0]
            if candidate.supporting_source_urls
            else None
        ),
        retrieved_at=candidate.source_retrieved_at,
    )
    return DiscoveryOpportunityReason(
        model_id="web_conversion.no_verified_web_presence",
        signal_type=EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE,
        supporting_value=(
            f"{candidate.source_provider} did not list an official website for this "
            "verified business identity."
        ),
        source=source,
        captured_at=candidate.source_retrieved_at,
    )


def mobile_performance_reason(
    observed_signals: dict[EvidenceSignalType, EvidenceSignal],
) -> DiscoveryOpportunityReason | None:
    signal = observed_signals.get(
        EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED
    )
    if signal is None or signal.numeric_value is None:
        return None
    if not 0 <= signal.numeric_value <= MOBILE_PERFORMANCE_RESEARCH_THRESHOLD:
        return None
    return DiscoveryOpportunityReason(
        model_id="web_conversion.mobile_performance",
        signal_type=signal.signal_type,
        supporting_value=signal.supporting_value,
        source=signal.source,
        captured_at=signal.captured_at,
    )


def social_dormancy_reason(
    observed_signals: dict[EvidenceSignalType, EvidenceSignal],
) -> DiscoveryOpportunityReason | None:
    signal = observed_signals.get(EvidenceSignalType.SOCIAL_DORMANCY_MEASURED)
    if signal is None or signal.numeric_value is None:
        return None
    if signal.numeric_value < SOCIAL_DORMANCY_RESEARCH_THRESHOLD_DAYS:
        return None
    return DiscoveryOpportunityReason(
        model_id="social_presence.dormant_official_presence",
        signal_type=signal.signal_type,
        supporting_value=signal.supporting_value,
        source=signal.source,
        captured_at=signal.captured_at,
    )


def reason_from_signal(
    model_id: OpportunityModelId,
    signal_type: EvidenceSignalType,
    observed_signals: dict[EvidenceSignalType, EvidenceSignal],
) -> DiscoveryOpportunityReason | None:
    signal = observed_signals.get(signal_type)
    if signal is None:
        return None
    return DiscoveryOpportunityReason(
        model_id=model_id,
        signal_type=signal.signal_type,
        supporting_value=signal.supporting_value,
        source=signal.source,
        captured_at=signal.captured_at,
    )


def opportunity_sort_key(
    entry: DiscoveryOpportunityQueueEntry,
) -> tuple[str, int]:
    return entry.company_name.casefold(), entry.candidate_index
