from datetime import UTC, datetime

import pytest

from app.schemas.campaign import CampaignRecommendedBatchCreate
from app.schemas.company_discovery import CompanyDiscoveryRequest, DiscoveredCompanyCandidate
from app.schemas.discovery_shortlist import (
    DiscoveryOpportunityQueueEntry,
    DiscoveryOpportunityReason,
    DiscoveryOpportunityPreparationRequest,
    DiscoveryShortlistState,
)
from app.schemas.opportunity_models import EvidenceSignalType, OpportunityModelSelection
from app.services.discovery_queue_preparation import (
    prepare_discovery_opportunity_queue,
    seed_discovery_evidence,
)
from app.services.discovery_opportunity_queue import opportunity_sort_key


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


def research_dependent_request(candidates: list[DiscoveredCompanyCandidate]):
    value = request(candidates)
    value.criteria.business_category = "Dental practices"
    value.model_selection = OpportunityModelSelection(
        model_ids=(
            "web_conversion.mobile_performance",
            "web_conversion.clinic_patient_path",
        ),
        confirmed_by_user=True,
    )
    return value


def social_research_request(candidates: list[DiscoveredCompanyCandidate]):
    value = request(candidates)
    value.criteria.business_category = "Restaurants & cafes"
    value.criteria.offering = "Social media management and content creation"
    value.model_selection = OpportunityModelSelection(
        model_ids=("social_presence.dormant_official_presence",),
        confirmed_by_user=True,
    )
    return value


class TestDiscoveryQueuePreparation:
    def test_observed_signals_sort_before_verification_then_alphabetically(self):
        source = EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE
        observed = DiscoveryOpportunityQueueEntry(
            candidate_index=2,
            company_name="Zulu Salon",
            reasons=[
                DiscoveryOpportunityReason(
                    model_id="web_conversion.no_verified_web_presence",
                    signal_type=source,
                    supporting_value="No website listed.",
                    source={
                        "provider": "open_places",
                        "provider_record_id": "overture:zulu-salon",
                        "retrieved_at": NOW,
                    },
                    captured_at=NOW,
                )
            ],
        )
        verification_b = DiscoveryOpportunityQueueEntry(
            candidate_index=1,
            company_name="Beta Clinic",
            verification_reason="Website checks require verification.",
        )
        verification_a = verification_b.model_copy(
            update={"candidate_index": 0, "company_name": "Alpha Clinic"}
        )

        ordered = sorted(
            [verification_b, verification_a, observed], key=opportunity_sort_key
        )

        assert [item.company_name for item in ordered] == [
            "Zulu Salon",
            "Alpha Clinic",
            "Beta Clinic",
        ]

    def test_research_dependent_web_models_surface_verified_identity_for_research(self):
        response = prepare_discovery_opportunity_queue(
            research_dependent_request([candidate()])
        )

        opportunity = response.candidates[0]
        assert opportunity.queue_entry.reasons == []
        assert opportunity.queue_entry.verification_reason is not None
        assert opportunity.shortlist_entry.state is (
            DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH
        )
        assert response.needs_verification_count == 1
        assert CampaignRecommendedBatchCreate(opportunities=[opportunity]).opportunities == [
            opportunity
        ]

    def test_social_model_surfaces_identity_sufficient_candidate_for_research(self):
        response = prepare_discovery_opportunity_queue(
            social_research_request([candidate(business_status="operational")])
        )

        opportunity = response.candidates[0]
        assert opportunity.queue_entry.reasons == []
        assert "social profile" in opportunity.queue_entry.verification_reason
        assert opportunity.shortlist_entry.state is (
            DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH
        )
        assert response.needs_verification_count == 1

    def test_social_model_does_not_surface_identity_unresolved_candidate(self):
        response = prepare_discovery_opportunity_queue(
            social_research_request(
                [candidate(source_types=["social_search"], address=None)]
            )
        )

        assert response.candidates == []
        assert response.needs_verification_count == 1

    def test_social_model_surfaces_current_traceable_local_listing(self):
        response = prepare_discovery_opportunity_queue(
            social_research_request([candidate()])
        )

        assert len(response.candidates) == 1
        assert response.needs_verification_count == 1

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

    def test_current_traceable_local_listing_confirms_business_activity(self):
        signals = seed_discovery_evidence(candidate())

        activity = next(
            signal
            for signal in signals
            if signal.signal_type is EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED
        )
        assert activity.supporting_value == (
            "Current local-business listing was retrieved and no closed/inactive "
            "status was reported."
        )
        assert activity.source.provider == "open_places"
        assert activity.captured_at == NOW

    @pytest.mark.parametrize("status", ["closed", "inactive", "permanently closed"])
    def test_explicit_closed_or_inactive_status_does_not_confirm_activity(self, status):
        signals = seed_discovery_evidence(candidate(business_status=status))

        assert EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED not in {
            signal.signal_type for signal in signals
        }

    def test_identity_unresolved_source_does_not_confirm_activity(self):
        signals = seed_discovery_evidence(
            candidate(source_types=["social_search"], address=None)
        )

        assert signals == []

    def test_untraceable_local_source_does_not_confirm_activity(self):
        untraceable = candidate().model_copy(update={"source_record_id": None})

        assert seed_discovery_evidence(untraceable) == []

    def test_candidate_actionable_for_one_model_can_enter_a_research_batch(self):
        preparation_request = request([candidate(business_status="operational")])
        preparation_request.model_selection = OpportunityModelSelection(
            model_ids=(
                "web_conversion.no_verified_web_presence",
                "social_presence.dormant_official_presence",
            ),
            confirmed_by_user=True,
        )

        response = prepare_discovery_opportunity_queue(preparation_request)
        opportunity = response.candidates[0]
        batch = CampaignRecommendedBatchCreate(opportunities=[opportunity])

        assert opportunity.shortlist_entry.state is (
            DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH
        )
        assert {
            evaluation.state
            for evaluation in opportunity.shortlist_entry.model_evaluations
        } == {DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH}
        assert batch.opportunities == [opportunity]
