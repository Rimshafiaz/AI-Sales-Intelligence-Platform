from datetime import UTC, datetime

from app.schemas.company_discovery import CompanyDiscoveryRequest, DiscoveredCompanyCandidate
from app.schemas.discovery_shortlist import (
    CandidateShortlistInput,
    DiscoveryShortlistRequest,
)
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelSelection,
)
from app.services.discovery_opportunity_queue import build_discovery_opportunity_queue


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def source(record_id: str = "overture:glow") -> EvidenceSource:
    return EvidenceSource(
        provider="open_places",
        provider_record_id=record_id,
        retrieved_at=NOW,
    )


def signal(
    signal_type: EvidenceSignalType,
    *,
    numeric_value: float | None = None,
    evidence_type: EvidenceType = EvidenceType.OBSERVED,
) -> EvidenceSignal:
    return EvidenceSignal(
        signal_type=signal_type,
        evidence_type=evidence_type,
        supporting_value=f"Observed {signal_type.value}.",
        numeric_value=numeric_value,
        source=source(),
        captured_at=NOW,
        inference_basis=(
            "Test-only inferred evidence basis."
            if evidence_type is EvidenceType.INFERENCE
            else None
        ),
    )


def candidate(
    name: str = "Glow Boutique",
    *,
    website: str | None = None,
    source_types: list[str] | None = None,
) -> DiscoveredCompanyCandidate:
    return DiscoveredCompanyCandidate(
        company_name=name,
        website=website,
        industry="clothing_store",
        match_explanation="Discovery returned this business identity.",
        source_provider="open_places",
        source_record_id=f"overture:{name.casefold().replace(' ', '-')}",
        source_retrieved_at=NOW,
        discovery_source_types=source_types or ["local_places"],
    )


def request(
    candidates: list[CandidateShortlistInput],
    *model_ids: str,
    business_category: str = "Boutiques",
) -> DiscoveryShortlistRequest:
    return DiscoveryShortlistRequest(
        criteria=CompanyDiscoveryRequest(
            offering="Website redesign",
            desired_outcome="Find businesses worth investigating.",
            business_category=business_category,
            location="Lahore",
        ),
        model_selection=OpportunityModelSelection(
            model_ids=tuple(model_ids),
            confirmed_by_user=True,
        ),
        candidates=candidates,
    )


class TestDiscoveryOpportunityQueue:
    def test_surfaces_verified_identity_with_no_listed_website(self):
        response = build_discovery_opportunity_queue(
            request(
                [
                    CandidateShortlistInput(
                        candidate=candidate(),
                        evidence_signals=[
                            signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                        ],
                    )
                ],
                "web_conversion.no_verified_web_presence",
            )
        )

        entry = response.candidates[0]
        assert entry.reasons[0].signal_type is EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE
        assert entry.reasons[0].source.provider_record_id == "overture:glow-boutique"

    def test_hides_candidates_that_only_match_the_industry(self):
        response = build_discovery_opportunity_queue(
            request(
                [CandidateShortlistInput(candidate=candidate())],
                "web_conversion.no_verified_web_presence",
            )
        )

        assert response.candidates == []
        assert response.needs_verification_count == 1
        assert response.not_surfaced_count == 0

    def test_surfaces_manual_booking_path_with_its_observed_evidence(self):
        response = build_discovery_opportunity_queue(
            request(
                [
                    CandidateShortlistInput(
                        candidate=candidate(website="https://glow.example"),
                        evidence_signals=[
                            signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                            signal(EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED),
                            signal(EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY),
                        ],
                    )
                ],
                "web_conversion.booking_contact_path",
                business_category="Beauty salons",
            )
        )

        entry = response.candidates[0]
        assert entry.reasons[0].signal_type is EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY

    def test_does_not_surface_a_social_dormancy_measurement_below_threshold(self):
        response = build_discovery_opportunity_queue(
            request(
                [
                    CandidateShortlistInput(
                        candidate=candidate(source_types=["social_search"]),
                        evidence_signals=[
                            signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                            signal(EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED),
                            signal(EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED),
                            signal(EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED),
                            signal(
                                EvidenceSignalType.SOCIAL_DORMANCY_MEASURED,
                                numeric_value=14,
                            ),
                        ],
                    )
                ],
                "social_presence.dormant_official_presence",
            )
        )

        assert response.candidates == []
        assert response.not_surfaced_count == 1

    def test_surfaces_social_dormancy_only_when_measurement_meets_threshold(self):
        response = build_discovery_opportunity_queue(
            request(
                [
                    CandidateShortlistInput(
                        candidate=candidate(source_types=["social_search"]),
                        evidence_signals=[
                            signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                            signal(EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED),
                            signal(EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED),
                            signal(EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED),
                            signal(
                                EvidenceSignalType.SOCIAL_DORMANCY_MEASURED,
                                numeric_value=90,
                            ),
                        ],
                    )
                ],
                "social_presence.dormant_official_presence",
            )
        )

        entry = response.candidates[0]
        assert entry.reasons[0].signal_type is EvidenceSignalType.SOCIAL_DORMANCY_MEASURED

    def test_mobile_measurement_requires_an_observed_low_score(self):
        candidates = [
            CandidateShortlistInput(
                candidate=candidate(name="Strong Mobile", website="https://strong.example"),
                evidence_signals=[
                    signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                    signal(EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED),
                    signal(
                        EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
                        numeric_value=91,
                    ),
                ],
            ),
            CandidateShortlistInput(
                candidate=candidate(name="Weak Mobile", website="https://weak.example"),
                evidence_signals=[
                    signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                    signal(EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED),
                    signal(
                        EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
                        numeric_value=42,
                    ),
                ],
            ),
        ]
        response = build_discovery_opportunity_queue(
            request(candidates, "web_conversion.mobile_performance")
        )

        assert [entry.company_name for entry in response.candidates] == ["Weak Mobile"]
        assert response.not_surfaced_count == 1

    def test_does_not_surface_inferred_trigger_evidence(self):
        response = build_discovery_opportunity_queue(
            request(
                [
                    CandidateShortlistInput(
                        candidate=candidate(website="https://glow.example"),
                        evidence_signals=[
                            signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED),
                            signal(EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED),
                            signal(
                                EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY,
                                evidence_type=EvidenceType.INFERENCE,
                            ),
                        ],
                    )
                ],
                "web_conversion.booking_contact_path",
                business_category="Beauty salons",
            )
        )

        assert response.candidates == []
        assert response.not_surfaced_count == 1

    def test_queue_order_does_not_depend_on_raw_candidate_order(self):
        alpha = CandidateShortlistInput(
            candidate=candidate(name="Alpha Boutique"),
            evidence_signals=[signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED)],
        )
        zebra = CandidateShortlistInput(
            candidate=candidate(name="Zebra Boutique"),
            evidence_signals=[signal(EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED)],
        )
        first = build_discovery_opportunity_queue(
            request([zebra, alpha], "web_conversion.no_verified_web_presence")
        )
        second = build_discovery_opportunity_queue(
            request([alpha, zebra], "web_conversion.no_verified_web_presence")
        )

        assert [entry.company_name for entry in first.candidates] == [
            "Alpha Boutique",
            "Zebra Boutique",
        ]
        assert [entry.company_name for entry in second.candidates] == [
            "Alpha Boutique",
            "Zebra Boutique",
        ]
