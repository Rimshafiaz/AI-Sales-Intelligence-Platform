import uuid
from datetime import UTC, datetime

import pytest
from crewai.tools import tool
from pydantic import ValidationError

from app.ai import social_research
from app.ai.agents import social_research_agent
from app.ai.tasks.social_research_task import create_social_research_task
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import SocialResearchOutput
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceSource, EvidenceType
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.social_audit import (
    SocialAuditState,
    SocialCandidateDiscoveryState,
    SocialEnrichmentResultState,
    SocialProfileCandidate,
    SocialVerificationState,
)
from app.schemas.social_research import (
    GroundedSocialEvidenceResult,
    GroundedSocialObservation,
    SelectedSocialModel,
    SocialIdentityState,
    SocialResearchHandoff,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)
REQUIRED = [
    EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
    EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED,
    EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED,
    EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED,
    EvidenceSignalType.SOCIAL_DORMANCY_MEASURED,
]


def evidence(signal, key):
    return BriefEvidence(
        key=key,
        signal_type=signal,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value="Canonical factual evidence.",
        numeric_value=15 if signal is EvidenceSignalType.SOCIAL_DORMANCY_MEASURED else None,
        source=EvidenceSource(
            provider="test",
            source_url="https://instagram.com/glowsalon",
            retrieved_at=NOW,
        ),
        captured_at=NOW,
    )


def state(evidence_items=(), observations=(), candidates=()):
    available = {item.signal_type for item in evidence_items}
    return GroundedSocialEvidenceResult(
        identity_state=SocialIdentityState.VERIFIED,
        selected_models=[
            SelectedSocialModel(
                model_id="social_presence.dormant_official_presence",
                required_evidence_signals=REQUIRED,
            )
        ],
        candidate_profiles=list(candidates),
        observations=list(observations),
        evidence=list(evidence_items),
        unresolved_requirements=[item for item in REQUIRED if item not in available],
        audit_state=SocialAuditState.NOT_RUN,
    )


def observation():
    return GroundedSocialObservation(
        key="social_observation:one",
        profile_url="https://instagram.com/glowsalon",
        platform="instagram",
        state="observed",
        display_name="Glow Salon",
        public_emails=["hello@glow.example"],
    )


def bound_context():
    user_id = uuid.uuid4()
    company = Company(id=uuid.uuid4(), user_id=user_id, name="Glow Salon")
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user_id,
        objective={
            "goal": "Find grounded social presence opportunities.",
            "offering": "Social media management",
            "location": "Lahore",
        },
    )
    return object(), request, company, None, user_id


def fake_tools(calls, trace):
    @tool("read_grounded_social_evidence")
    def read() -> str:
        """Read evidence."""
        calls.append("read")
        return "{}"

    @tool("discover_social_profile_candidates")
    def discover() -> str:
        """Discover candidates."""
        calls.append("discover")
        trace.discovery_state = SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE
        return "{}"

    @tool("enrich_social_profile_candidates")
    def enrich() -> str:
        """Enrich candidates."""
        calls.append("enrich")
        trace.enrichment_state = SocialEnrichmentResultState.OBSERVATIONS_AVAILABLE
        return "{}"

    @tool("verify_social_profiles_and_measure_activity")
    def verify() -> str:
        """Verify profiles."""
        calls.append("verify")
        trace.verification_state = SocialVerificationState.EVIDENCE_FOUND
        return "{}"

    return read, discover, enrich, verify


def invoke(task, name):
    return next(item for item in task.tools if item.name == name).run()


class TestSocialResearchAgent:
    def test_agent_uses_full_default_output_budget(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            social_research_agent,
            "Agent",
            lambda **kwargs: type("FakeAgent", (), kwargs)(),
        )
        monkeypatch.setattr(
            social_research_agent,
            "get_llm",
            lambda **kwargs: captured.append(kwargs) or object(),
        )

        agent = social_research_agent.create_social_research_agent(
            fake_tools([], social_research.SocialResearchToolTrace())
        )

        assert agent.tools
        assert captured == [{}]

    def test_truncated_structured_output_becomes_domain_error(self, monkeypatch):
        class BrokenCrew:
            def __init__(self, **_kwargs):
                pass

            def kickoff(self):
                SocialResearchOutput.model_validate_json(
                    '{"presence_status":"verified","findings":['
                )

        monkeypatch.setattr(social_research, "Crew", BrokenCrew)
        task = create_social_research_task(
            SocialResearchHandoff(
                seller_goal="Find grounded social opportunities.",
                offering="Social media management",
                company_name="Glow Salon",
                starting_state=state(),
            ),
            fake_tools([], social_research.SocialResearchToolTrace()),
        )

        with pytest.raises(
            social_research.SocialResearchError,
            match="did not return valid structured output",
        ) as caught:
            social_research._run_task(task)

        assert isinstance(caught.value.__cause__, ValidationError)

    @pytest.mark.parametrize(
        "actions",
        [
            ["enrich", "verify", "read"],
            ["verify", "read"],
            ["read", "discover", "enrich", "verify", "read"],
        ],
    )
    def test_agent_can_choose_distinct_bounded_paths(self, monkeypatch, actions):
        calls = []
        canonical = [
            evidence(EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED, "evidence:official"),
            evidence(EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED, "evidence:activity"),
        ]
        starting = (
            state(candidates=[SocialProfileCandidate(
                profile_url="https://instagram.com/glowsalon",
                platform="instagram",
                handle="glowsalon",
                source="campaign",
            )])
            if actions[0] == "enrich"
            else state(observations=[observation()])
            if actions[0] == "verify"
            else state()
        )
        states = iter([starting, state(canonical)])

        def build(*args):
            return fake_tools(calls, args[-1])

        monkeypatch.setattr(social_research, "build_social_research_tools", build)
        monkeypatch.setattr(
            social_research, "build_grounded_social_evidence", lambda *_: next(states)
        )

        def run(task):
            for action in actions:
                invoke(task, {
                    "read": "read_grounded_social_evidence",
                    "discover": "discover_social_profile_candidates",
                    "enrich": "enrich_social_profile_candidates",
                    "verify": "verify_social_profiles_and_measure_activity",
                }[action])
            return SocialResearchOutput(
                presence_status="verified",
                findings=[{
                    "statement": "An official social profile was deterministically verified.",
                    "claim_kind": "observed",
                    "evidence_keys": ["evidence:official"],
                }],
                evidence_gaps=[],
            )

        monkeypatch.setattr(social_research, "_run_task", run)

        result = social_research.run_social_research_agent(*bound_context())

        assert isinstance(result, SocialResearchOutput)
        assert calls == actions

    def test_no_official_profile_is_none_verified_without_fabricated_finding(self):
        trace = social_research.SocialResearchToolTrace(
            verification_state=SocialVerificationState.NO_OFFICIAL_PROFILE_VERIFIED
        )

        result = social_research.validate_social_research_output(
            SocialResearchOutput(
                presence_status="none_verified",
                findings=[],
                evidence_gaps=[
                    "No observed candidate matched the trusted business identity.",
                    "Business activity evidence is missing.",
                ],
            ),
            state(),
            trace,
        )

        assert result.findings == []

    @pytest.mark.parametrize(
        ("verification_state", "gap"),
        [
            (SocialVerificationState.INSUFFICIENT_ACTIVITY_HISTORY, "Public post history is insufficient."),
            (SocialVerificationState.DORMANCY_UNMEASURABLE, "The latest public post was unavailable."),
        ],
    )
    def test_incomplete_activity_remains_a_gap(self, verification_state, gap):
        trace = social_research.SocialResearchToolTrace(
            verification_state=verification_state
        )

        result = social_research.validate_social_research_output(
            SocialResearchOutput(
                presence_status="partially_verified",
                findings=[],
                evidence_gaps=[gap, "Business activity evidence is missing."],
            ),
            state(observations=[observation()]),
            trace,
        )

        assert gap in result.evidence_gaps

    def test_missing_business_activity_must_be_explicit(self):
        final = state(
            [evidence(EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED, "evidence:official")]
        )

        with pytest.raises(social_research.SocialResearchError, match="business activity"):
            social_research.validate_social_research_output(
                SocialResearchOutput(presence_status="verified"),
                final,
                social_research.SocialResearchToolTrace(),
            )

    def test_contact_observation_or_unknown_key_cannot_become_a_finding(self):
        with pytest.raises(social_research.SocialResearchError, match="unavailable evidence"):
            social_research.validate_social_research_output(
                SocialResearchOutput(
                    presence_status="partially_verified",
                    findings=[{
                        "statement": "A public email proves a social opportunity.",
                        "claim_kind": "observed",
                        "evidence_keys": ["social_observation:one"],
                    }],
                    evidence_gaps=["Business activity evidence is missing."],
                ),
                state(observations=[observation()]),
                social_research.SocialResearchToolTrace(),
            )

    def test_task_has_exact_tools_and_no_dormancy_threshold(self):
        tools = fake_tools([], social_research.SocialResearchToolTrace())
        handoff = SocialResearchHandoff(
            seller_goal="Find grounded social opportunities.",
            offering="Social media management",
            company_name="Glow Salon",
            starting_state=state(),
        )

        task = create_social_research_task(handoff, tools)

        assert {item.name for item in task.tools} == {
            "read_grounded_social_evidence",
            "discover_social_profile_candidates",
            "enrich_social_profile_candidates",
            "verify_social_profiles_and_measure_activity",
        }
        assert "60" not in task.description
