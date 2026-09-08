import uuid
from datetime import UTC, datetime

import pytest

from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.models.research_social_observation import ResearchSocialObservation
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSource
from app.schemas.social_audit import SocialAuditState
from app.schemas.social_enrichment import (
    SocialEnrichmentState,
    SocialPlatform,
    SocialProfileObservation,
)
from app.services.social_audit import SocialAuditError, audit_research_social_profiles


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.added = []
        self.committed = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

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

    def enrich(self, targets):
        self.targets = targets
        return self.observations


def request():
    return ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
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

        result = audit_research_social_profiles(
            db,
            research_request,
            company(research_request),
            None,
            ["https://www.instagram.com/glowsalon/"],
            StubProvider([observation(name="Different Salon")]),
        )

        assert result.social_audit_state is SocialAuditState.COMPLETED
        assert "0 matched" in result.social_audit_reason
        assert len(db.added) == 1
        assert isinstance(db.added[0], ResearchSocialObservation)

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
