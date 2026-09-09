from app.integrations.business_discovery import DiscoverySourceType
from app.schemas.company_discovery import DiscoveredCompanyCandidate
from app.schemas.discovery_shortlist import (
    CandidateShortlistInput,
    DiscoveryOpportunityPreparationRequest,
    DiscoveryOpportunityPreparationResponse,
    DiscoveryShortlistRequest,
    PreparedDiscoveryOpportunity,
)
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
)
from app.services.discovery_opportunity_queue import build_discovery_opportunity_queue
from app.services.discovery_shortlist import shortlist_discovery_candidates


def prepare_discovery_opportunity_queue(
    request: DiscoveryOpportunityPreparationRequest,
) -> DiscoveryOpportunityPreparationResponse:
    candidate_inputs = [
        CandidateShortlistInput(
            candidate=candidate,
            evidence_signals=seed_discovery_evidence(candidate),
        )
        for candidate in request.candidates
    ]
    shortlist_request = DiscoveryShortlistRequest(
        criteria=request.criteria,
        model_selection=request.model_selection,
        candidates=candidate_inputs,
    )
    shortlist = shortlist_discovery_candidates(shortlist_request)
    queue = build_discovery_opportunity_queue(shortlist_request)
    return DiscoveryOpportunityPreparationResponse(
        candidates=[
            PreparedDiscoveryOpportunity(
                queue_entry=queue_entry,
                candidate_input=candidate_inputs[queue_entry.candidate_index],
                shortlist_entry=shortlist.candidates[queue_entry.candidate_index],
            )
            for queue_entry in queue.candidates
        ],
        needs_verification_count=queue.needs_verification_count,
        not_surfaced_count=queue.not_surfaced_count,
    )


def seed_discovery_evidence(
    candidate: DiscoveredCompanyCandidate,
) -> list[EvidenceSignal]:
    source_types = set(candidate.discovery_source_types)
    if (
        DiscoverySourceType.LOCAL_PLACES.value not in source_types
        or not candidate.formatted_address
        or not candidate.source_provider
        or not candidate.source_record_id
        or candidate.source_retrieved_at is None
    ):
        return []
    source = EvidenceSource(
        provider=candidate.source_provider,
        provider_record_id=candidate.source_record_id,
        source_url=(
            candidate.supporting_source_urls[0]
            if candidate.supporting_source_urls
            else None
        ),
        retrieved_at=candidate.source_retrieved_at,
    )
    signals = [
        EvidenceSignal(
            signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value=(
                f"{candidate.source_provider} returned this business name at "
                f"{candidate.formatted_address}."
            ),
            source=source,
            captured_at=candidate.source_retrieved_at,
        )
    ]
    if candidate.business_status and candidate.business_status.casefold() in {
        "operational",
        "open",
    }:
        signals.append(
            EvidenceSignal(
                signal_type=EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED,
                evidence_type=EvidenceType.OBSERVED,
                supporting_value=(
                    f"{candidate.source_provider} listed the business status as "
                    f"{candidate.business_status}."
                ),
                source=source,
                captured_at=candidate.source_retrieved_at,
            )
        )
    return signals
