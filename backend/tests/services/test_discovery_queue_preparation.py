from datetime import UTC, datetime

from app.schemas.company_discovery import CompanyDiscoveryRequest, DiscoveredCompanyCandidate
from app.schemas.discovery_shortlist import DiscoveryOpportunityPreparationRequest
from app.schemas.opportunity_models import EvidenceSignalType, OpportunityModelSelection
from app.services.discovery_queue_preparation import prepare_discovery_opportunity_queue


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def criteria() -> CompanyDiscoveryRequest:
    return CompanyDiscoveryRequest(
        offering="Website redesign",
        desired_outcome="Find businesses worth investigating.",
        business_category="Beauty salons",
        location="Lahore",
    )


def candidate(
    *,
    source_types: list[str] | None = None,
    address: str | None = "Gulberg, Lahore",
    business_status: str | None = None,
) -> DiscoveredCompanyCandidate:
    return DiscoveredCompanyCandidate(
        company_name="Glow Salon",
        industry="beauty_salon",
        match_explanation="Discovery returned this business.",
        source_provider="open_places",
        source_record_id="overture:glow-salon",
        source_retrieved_at=NOW,
        formatted_address=address,
        business_status=business_status,
        discovery_source_types=source_types or ["local_places"],
    )


def request(candidates: list[DiscoveredCompanyCandidate]):
    return DiscoveryOpportunityPreparationRequest(
        criteria=criteria(),
        model_selection=OpportunityModelSelection(
            model_ids=("web_conversion.no_verified_web_presence",),
            confirmed_by_user=True,
        ),
        candidates=candidates,
    )


class TestDiscoveryQueuePreparation:
    def test_seeds_a_traceable_local_identity_and_surfaces_no_listed_website(self):
        response = prepare_discovery_opportunity_queue(request([candidate()]))

        opportunity = response.candidates[0]
        assert opportunity.candidate_input.evidence_signals[0].supporting_value.endswith(
            "Gulberg, Lahore."
        )
        assert opportunity.queue_entry.reasons[0].signal_type == "no_listed_official_website"

    def test_does_not_treat_unverified_web_or_social_results_as_confirmed_identity(self):
        response = prepare_discovery_opportunity_queue(
            request(
                [
                    candidate(source_types=["web_search"], address=None),
                    candidate(source_types=["social_search"], address=None),
                ]
            )
        )

        assert response.candidates == []
        assert response.needs_verification_count == 2

    def test_seeds_activity_only_from_an_explicit_operating_status(self):
        active = prepare_discovery_opportunity_queue(
            request([candidate(business_status="operational")])
        )
        unknown = prepare_discovery_opportunity_queue(request([candidate()]))

        assert EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED in {
            signal.signal_type
            for signal in active.candidates[0].candidate_input.evidence_signals
        }
        assert EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED not in {
            signal.signal_type
            for signal in unknown.candidates[0].candidate_input.evidence_signals
        }
