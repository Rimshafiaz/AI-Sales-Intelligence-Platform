import uuid
from datetime import UTC, datetime

import pytest

from app.models.company import Company
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.models.research_social_observation import ResearchSocialObservation
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSource
from app.schemas.social_audit import (
    SocialAuditState,
    SocialCandidateDiscoveryResult,
    SocialCandidateDiscoveryState,
    SocialEnrichmentResultState,
    SocialProfileCandidate,
    SocialVerificationState,
    SocialCheckStates,
)
from app.schemas.social_enrichment import (
    SocialEnrichmentState,
    SocialPlatform,
    SocialProfileObservation,
)
from app.services.social_audit import (
    SocialAuditError,
    audit_research_social_profiles,
    discover_social_profile_candidates,
    enrich_social_profile_candidates,
    verify_social_profiles_and_measure_activity,
)


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.added = []
        self.committed = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return iter(item for item in self.added if isinstance(item, entity))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def refresh(self, value):
        return value


class StubProvider:
    def __init__(self, observations):
        self.observations = observations
        self.targets = []
        self.calls = 0

    def enrich(self, targets):
        self.calls += 1
        self.targets = targets
        return self.observations


def request():
    return ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
        opportunity_model_selection={
            "model_ids": ["social_presence.dormant_official_presence"],
            "confirmed_by_user": True,
        },
        objective={
            "location": "Lahore",
            "resolved_target": {
                "business_name": "Glow Salon",
                "website": "https://glow.example/",
                "identity_state": "verified",
                "source": {"source_url": "https://glow.example/about"},
            },
        },
    )


def company(research_request):
    return Company(
        id=research_request.company_id,
        user_id=research_request.user_id,
        name="Glow Salon",
    )


def campaign_selection(research_request, urls):
    selection = CampaignCandidateSelection(
        id=uuid.uuid4(),
        campaign_run_id=uuid.uuid4(),
        company_id=research_request.company_id,
        source_identity_key="places:glow",
        candidate_snapshot={"social_profile_urls": urls},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    research_request.campaign_candidate_selection_id = selection.id
    return selection


def observation(name="Glow Salon", state=SocialEnrichmentState.OBSERVED):
    return SocialProfileObservation(
        profile_url="https://www.instagram.com/glowsalon/",
        platform=SocialPlatform.INSTAGRAM,
        state=state,
        display_name=name if state is SocialEnrichmentState.OBSERVED else None,
        handle="glowsalon",
        biography="Beauty appointments in Lahore" if state is SocialEnrichmentState.OBSERVED else None,
        latest_public_post_at=datetime(2026, 6, 1, tzinfo=UTC)
        if state is SocialEnrichmentState.OBSERVED
        else None,
        recent_public_post_dates=[
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 5, 1, tzinfo=UTC),
        ]
        if state is SocialEnrichmentState.OBSERVED
        else [],
        source=EvidenceSource(
            provider="apify",
            provider_record_id="apify/instagram-profile-scraper:ig-123",
            source_url="https://www.instagram.com/glowsalon/",
            retrieved_at=NOW,
        ),
        detail="The profile is private." if state is SocialEnrichmentState.UNAVAILABLE else None,
    )


class TestSocialAudit:
    def test_persists_confirmed_profile_and_derived_public_evidence(self):
        research_request = request()
        db = FakeSession([None, None, None, None, research_request])
        provider = StubProvider([observation()])

        result = audit_research_social_profiles(
            db,
            research_request,
            company(research_request),
            None,
            ["https://www.instagram.com/glowsalon/"],
            provider,
        )

        assert result.social_audit_state is SocialAuditState.COMPLETED
        assert provider.targets[0].handle == "glowsalon"
        raw_observation = db.added[0]
        assert isinstance(raw_observation, ResearchSocialObservation)
        assert raw_observation.profile_identity_key == "instagram:glowsalon"
        signals = [item for item in db.added if isinstance(item, ResearchEvidence)]
        assert {item.signal_type for item in signals} == {
            "official_social_profile_confirmed",
            "social_historic_activity_confirmed",
            "social_dormancy_measured",
        }
        assert all(item.evidence_type == "observed" for item in signals)
        assert all(item.source_provider == "apify" for item in signals)
        assert "business_activity_confirmed" not in {item.signal_type for item in signals}

    def test_keeps_an_unmatched_public_profile_without_official_signals(self):
        research_request = request()
        db = FakeSession([None, research_request])
        unmatched = observation(name="Different Salon")
        unmatched.public_emails = ["hello@unrelated.example"]
        unmatched.public_phones = ["+92 300 0000000"]

        result = audit_research_social_profiles(
            db,
            research_request,
            company(research_request),
            None,
            ["https://www.instagram.com/glowsalon/"],
            StubProvider([unmatched]),
        )

        assert result.social_audit_state is SocialAuditState.COMPLETED
        assert "0 matched" in result.social_audit_reason
        assert len(db.added) == 1
        assert isinstance(db.added[0], ResearchSocialObservation)
        assert SocialCheckStates.model_validate(
            research_request.social_check_states
        ).verification.state is SocialVerificationState.NO_OFFICIAL_PROFILE_VERIFIED

    def test_private_profile_is_unavailable_not_negative_evidence(self):
        research_request = request()
        db = FakeSession([None, research_request])

        result = audit_research_social_profiles(
            db,
            research_request,
            company(research_request),
            None,
            ["https://www.instagram.com/glowsalon/"],
            StubProvider([observation(state=SocialEnrichmentState.UNAVAILABLE)]),
        )

        assert result.social_audit_state is SocialAuditState.UNAVAILABLE
        assert len(db.added) == 1
        assert isinstance(db.added[0], ResearchSocialObservation)

    def test_missing_profile_url_is_unavailable(self):
        research_request = request()
        db = FakeSession([research_request])

        result = audit_research_social_profiles(
            db,
            research_request,
            company(research_request),
            None,
            [],
            StubProvider([]),
        )

        assert result.social_audit_state is SocialAuditState.UNAVAILABLE
        assert db.added == []

    def test_requires_a_completed_accepted_evidence_gate(self):
        research_request = request()
        research_request.evidence_gate_state = EvidenceGateState.NEEDS_REVIEW

        with pytest.raises(SocialAuditError, match="Accepted evidence"):
            audit_research_social_profiles(
                FakeSession([]),
                research_request,
                company(research_request),
                None,
                ["https://www.instagram.com/glowsalon/"],
                StubProvider([]),
            )


class TestSocialCapabilities:
    def test_non_social_scope_is_not_permitted(self):
        research_request = request()
        research_request.opportunity_model_selection = {
            "model_ids": ["web_conversion.mobile_performance"],
            "confirmed_by_user": True,
        }

        result = discover_social_profile_candidates(
            FakeSession([]), research_request, company(research_request), None, research_request.user_id
        )

        assert result.state is SocialCandidateDiscoveryState.NOT_PERMITTED

    def test_campaign_candidates_skip_bounded_search(self, monkeypatch):
        research_request = request()
        selection = campaign_selection(
            research_request, ["https://instagram.com/glowsalon/"]
        )
        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: pytest.fail("Tavily should not run"),
        )

        result = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            selection,
            research_request.user_id,
        )

        assert result.state is SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE
        assert str(result.candidates[0].profile_url).rstrip("/") == "https://instagram.com/glowsalon"

    def test_bounded_autodiscovery_normalizes_and_filters_candidates(self, monkeypatch):
        class Search:
            def __init__(self):
                self.queries = []

            def search(self, query, **_kwargs):
                self.queries.append(query)
                return [
                    type("Result", (), {"url": "https://instagram.com/glow_salon/"})(),
                    type("Result", (), {"url": "https://example.com/not-social"})(),
                    type("Result", (), {"url": "https://facebook.com/unrelated"})(),
                ]

        search = Search()
        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: search,
        )

        research_request = request()
        result = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            None,
            research_request.user_id,
        )

        assert result.state is SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE
        assert [(item.platform.value, item.handle) for item in result.candidates] == [
            ("instagram", "glow_salon")
        ]
        assert not any(query.startswith("site:instagram.com") for query in search.queries)
        reloaded = SocialCheckStates.model_validate(
            research_request.social_check_states
        )
        assert reloaded.discovery.candidates[0].handle == "glow_salon"

        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: pytest.fail("persisted discovery must avoid Tavily"),
        )
        retried = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            None,
            research_request.user_id,
        )
        assert retried.candidates == result.candidates

    def test_instagram_fallback_runs_once_merges_deduplicates_and_keeps_cap(self, monkeypatch):
        class Search:
            def __init__(self):
                self.queries = []

            def search(self, query, **_kwargs):
                self.queries.append(query)
                if query.startswith("site:instagram.com"):
                    return [
                        type("Result", (), {"url": "https://instagram.com/glow_salon/"})(),
                        type("Result", (), {"url": "https://instagram.com/glow_salon/"})(),
                        type("Result", (), {"url": "https://instagram.com/glow_salon_lahore/"})(),
                        type("Result", (), {"url": "https://instagram.com/glow_salon_official/"})(),
                        type("Result", (), {"url": "https://instagram.com/glow_salon_extra/"})(),
                    ]
                return []

        search = Search()
        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: search,
        )

        research_request = request()
        result = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            None,
            research_request.user_id,
        )

        fallback_queries = [
            query for query in search.queries if query.startswith("site:instagram.com")
        ]
        assert fallback_queries == ['site:instagram.com "Glow Salon" "Lahore"']
        assert [item.handle for item in result.candidates] == [
            "glow_salon",
            "glow_salon_lahore",
            "glow_salon_official",
        ]

    def test_completed_no_candidate_discovery_survives_retry(self, monkeypatch):
        class EmptySearch:
            def search(self, *_args, **_kwargs):
                return []

        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: EmptySearch(),
        )
        research_request = request()
        first = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            None,
            research_request.user_id,
        )
        monkeypatch.setattr(
            "app.integrations.search_provider.create_tavily_search_provider",
            lambda *_: pytest.fail("persisted empty discovery must avoid Tavily"),
        )
        second = discover_social_profile_candidates(
            FakeSession([]),
            research_request,
            company(research_request),
            None,
            research_request.user_id,
        )

        assert first.state is second.state is SocialCandidateDiscoveryState.NO_CANDIDATES

    def test_enrichment_rejects_non_platform_candidate_and_reuses_observation(self):
        research_request = request()
        owner = company(research_request)
        invalid = SocialCandidateDiscoveryResult(
            state=SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE,
            candidates=[
                SocialProfileCandidate(
                    profile_url="https://example.com/glowsalon",
                    platform="instagram",
                    handle="glowsalon",
                    source="bounded_search",
                )
            ],
            reason="test",
        )
        db = FakeSession([None])

        rejected = enrich_social_profile_candidates(
            db, research_request, owner, None, research_request.user_id, invalid, StubProvider([])
        )
        assert rejected.state is SocialEnrichmentResultState.NO_CANDIDATES

        candidates = SocialCandidateDiscoveryResult(
            state=SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE,
            candidates=[
                SocialProfileCandidate(
                    profile_url="https://instagram.com/glowsalon",
                    platform="instagram",
                    handle="glowsalon",
                    source="bounded_search",
                )
            ],
            reason="test",
        )
        provider = StubProvider([observation()])
        first = enrich_social_profile_candidates(
            db, research_request, owner, None, research_request.user_id, candidates, provider
        )
        second = enrich_social_profile_candidates(
            db, research_request, owner, None, research_request.user_id, candidates, provider
        )

        assert first.state is SocialEnrichmentResultState.OBSERVATIONS_AVAILABLE
        assert second.state is SocialEnrichmentResultState.ALREADY_AVAILABLE
        assert provider.calls == 1
        assert db.added[0].biography == "Beauty appointments in Lahore"

    def test_persisted_biography_reproduces_identity_match_after_reload(self):
        research_request = request()
        owner = company(research_request)
        candidates = SocialCandidateDiscoveryResult(
            state=SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE,
            candidates=[
                SocialProfileCandidate(
                    profile_url="https://instagram.com/glowsalon",
                    platform="instagram",
                    handle="glowsalon",
                    source="bounded_search",
                )
            ],
            reason="test",
        )
        db = FakeSession([None, None, None, None])
        enrich_social_profile_candidates(
            db,
            research_request,
            owner,
            None,
            research_request.user_id,
            candidates,
            StubProvider([observation()]),
        )

        result = verify_social_profiles_and_measure_activity(
            db,
            research_request,
            owner,
            None,
            research_request.user_id,
        )

        assert result.state is SocialVerificationState.EVIDENCE_FOUND
        assert result.verified_profile_count == 1

    def test_verification_reports_insufficient_history_without_applying_threshold(self):
        research_request = request()
        observed = observation()
        observed.recent_public_post_dates = [observed.latest_public_post_at]
        enrichment = type(
            "Enrichment",
            (),
            {"observations": [observed]},
        )()
        db = FakeSession([None, None])

        result = verify_social_profiles_and_measure_activity(
            db,
            research_request,
            company(research_request),
            None,
            research_request.user_id,
            enrichment,
        )

        assert result.state is SocialVerificationState.INSUFFICIENT_ACTIVITY_HISTORY
        signals = {item.signal_type for item in db.added if isinstance(item, ResearchEvidence)}
        assert signals == {
            "official_social_profile_confirmed",
            "social_dormancy_measured",
        }
        assert SocialCheckStates.model_validate(
            research_request.social_check_states
        ).verification.state is SocialVerificationState.INSUFFICIENT_ACTIVITY_HISTORY

    def test_missing_latest_post_persists_dormancy_unmeasurable_without_fake_evidence(self):
        research_request = request()
        observed = observation()
        observed.latest_public_post_at = None
        enrichment = type("Enrichment", (), {"observations": [observed]})()
        db = FakeSession([None, None])

        result = verify_social_profiles_and_measure_activity(
            db,
            research_request,
            company(research_request),
            None,
            research_request.user_id,
            enrichment,
        )

        assert result.state is SocialVerificationState.DORMANCY_UNMEASURABLE
        signals = {item.signal_type for item in db.added if isinstance(item, ResearchEvidence)}
        assert signals == {
            "official_social_profile_confirmed",
            "social_historic_activity_confirmed",
        }
