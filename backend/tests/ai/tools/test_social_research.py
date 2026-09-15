import uuid
from datetime import UTC, datetime

import pytest

from app.ai.tools import social_research
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest, ResearchStatus
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.social_audit import (
    SocialAuditState,
    SocialCandidateDiscoveryResult,
    SocialCandidateDiscoveryState,
    SocialCandidateEnrichmentResult,
    SocialEnrichmentResultState,
    SocialProfileCandidate,
    SocialVerificationResult,
    SocialVerificationState,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)


class FakeSession:
    def __init__(self):
        self.evidence = []
        self.observations = []

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return iter(
            self.evidence
            if entity.__name__ == "ResearchEvidence"
            else self.observations
        )


def context(model_id="social_presence.dormant_official_presence", campaign_urls=()):
    user_id = uuid.uuid4()
    company = Company(id=uuid.uuid4(), user_id=user_id, name="Glow Salon")
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user_id,
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
        social_audit_state=SocialAuditState.NOT_RUN,
        opportunity_model_selection={
            "model_ids": [model_id],
            "confirmed_by_user": True,
        },
        objective={
            "location": "Lahore",
            "resolved_target": {
                "business_name": "Glow Salon",
                "website": "https://glow.example",
                "identity_state": "verified",
                "source": {
                    "provider": "official_website",
                    "source_url": "https://glow.example/about",
                    "retrieved_at": NOW.isoformat(),
                },
            },
        },
    )
    selection = CampaignCandidateSelection(
        id=uuid.uuid4(),
        campaign_run_id=uuid.uuid4(),
        company_id=company.id,
        source_identity_key="places:glow",
        candidate_snapshot={"social_profile_urls": list(campaign_urls)},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    request.campaign_candidate_selection_id = selection.id
    return FakeSession(), request, company, selection, user_id


def tools_by_name(tools):
    return {item.name: item for item in tools}


def candidate_result():
    return SocialCandidateDiscoveryResult(
        state=SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE,
        candidates=[
            SocialProfileCandidate(
                profile_url="https://instagram.com/glowsalon",
                platform="instagram",
                handle="glowsalon",
                source="bounded_search",
            )
        ],
        reason="Bounded candidate found.",
    )


class TestBoundSocialResearchTools:
    def test_tools_have_no_llm_controlled_arguments(self):
        bound = social_research.build_social_research_tools(*context())

        assert {item.name for item in bound} == {
            "read_grounded_social_evidence",
            "discover_social_profile_candidates",
            "enrich_social_profile_candidates",
            "verify_social_profiles_and_measure_activity",
        }
        assert all(not item.args_schema.model_fields for item in bound)

    def test_factory_rejects_another_user_context(self):
        db, request, company, selection, _ = context()

        with pytest.raises(ValueError, match="not available"):
            social_research.build_social_research_tools(
                db, request, company, selection, uuid.uuid4()
            )

    def test_reader_exposes_only_social_scope_and_canonical_requirements(self):
        db, request, company, selection, user_id = context(
            campaign_urls=("https://instagram.com/glowsalon",)
        )

        result = social_research.build_grounded_social_evidence(
            db, request, company, selection, user_id
        )

        assert [item.model_id for item in result.selected_models] == [
            "social_presence.dormant_official_presence"
        ]
        assert result.candidate_profiles[0].handle == "glowsalon"
        assert {item.signal_type.value for item in result.evidence} == {
            "business_identity_confirmed"
        }
        assert "social_dormancy_measured" in {
            item.value for item in result.unresolved_requirements
        }

    def test_non_social_scope_returns_not_permitted_from_discovery(self):
        bound = tools_by_name(
            social_research.build_social_research_tools(
                *context("web_conversion.mobile_performance")
            )
        )

        result = SocialCandidateDiscoveryResult.model_validate_json(
            bound["discover_social_profile_candidates"].run()
        )

        assert result.state is SocialCandidateDiscoveryState.NOT_PERMITTED

    def test_enrichment_can_only_use_the_bound_discovery_result(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            social_research,
            "discover_candidates",
            lambda *_: candidate_result(),
        )

        def enrich(*args):
            calls.append(args[5])
            return SocialCandidateEnrichmentResult(
                state=SocialEnrichmentResultState.OBSERVATIONS_AVAILABLE,
                reason="Observed.",
            )

        monkeypatch.setattr(social_research, "enrich_candidates", enrich)
        bound = tools_by_name(social_research.build_social_research_tools(*context()))

        before_discovery = SocialCandidateEnrichmentResult.model_validate_json(
            bound["enrich_social_profile_candidates"].run()
        )
        bound["discover_social_profile_candidates"].run()
        after_discovery = SocialCandidateEnrichmentResult.model_validate_json(
            bound["enrich_social_profile_candidates"].run()
        )

        assert before_discovery.state is SocialEnrichmentResultState.NO_CANDIDATES
        assert after_discovery.state is SocialEnrichmentResultState.OBSERVATIONS_AVAILABLE
        assert calls == [candidate_result()]

    def test_verification_delegates_only_bound_owned_context(self, monkeypatch):
        received = []

        def verify(*args):
            received.append(args)
            return SocialVerificationResult(
                state=SocialVerificationState.EVIDENCE_FOUND,
                reason="Canonical evidence persisted.",
            )

        monkeypatch.setattr(social_research, "verify_profiles", verify)
        context_values = context()
        bound = tools_by_name(
            social_research.build_social_research_tools(*context_values)
        )

        result = SocialVerificationResult.model_validate_json(
            bound["verify_social_profiles_and_measure_activity"].run()
        )

        assert result.state is SocialVerificationState.EVIDENCE_FOUND
        assert received == [context_values]
