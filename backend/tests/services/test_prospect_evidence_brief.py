import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSignalType
from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.schemas.prospect_evidence_brief import (
    BriefClaimKind,
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    PitchAngle,
    ProspectEvidenceBrief,
)
from app.services import prospect_evidence_brief
from app.services.prospect_evidence_brief import build_prospect_evidence_brief_handoffs


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def brief_evidence():
    return BriefEvidence(
        key="research_evidence:mobile-score",
        signal_type=EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
        evidence_type="observed",
        supporting_value="PageSpeed measured 31/100 on mobile.",
        numeric_value=31,
        source={
            "provider": "pagespeed_insights",
            "source_url": "https://glowsalon.example",
            "retrieved_at": NOW,
        },
        captured_at=NOW,
    )


def brief_payload():
    evidence = brief_evidence()
    objective = BriefObjective(
        goal="Find salons worth pitching for website improvements.",
        offering="Website redesign and booking setup",
        desired_outcome="Decide whether to contact this salon.",
    )
    verdict = BriefQualification(
        opportunity_model_id="web_conversion.mobile_performance",
        state=OpportunityQualificationState.LIKELY,
        reason="The measured mobile score is below the threshold.",
        supporting_evidence_keys=[evidence.key],
        evaluated_at=NOW,
    )
    return {
        "objective": objective,
        "prospect": BriefProspect(
            business_name="Glow Salon",
            location="Lahore",
            official_website="https://glowsalon.example",
            identity_verified=True,
        ),
        "verdict": verdict,
        "evidence_quality": "high",
        "findings": [],
        "contacts": [],
        "pitch_angle": None,
        "outreach_drafts": [],
        "caveats": [],
        "evidence": [evidence],
        "sources": [],
    }


class TestProspectEvidenceBriefSchema:
    def test_rejects_a_pitch_angle_when_qualification_is_not_likely(self):
        payload = brief_payload()
        payload["verdict"] = payload["verdict"].model_copy(
            update={"state": OpportunityQualificationState.INSUFFICIENT_EVIDENCE}
        )
        payload["pitch_angle"] = PitchAngle(
            statement="Improve the measured mobile experience.",
            offering="Website redesign and booking setup",
            evidence_keys=["research_evidence:mobile-score"],
        )

        with pytest.raises(ValidationError, match="Only a likely qualification"):
            ProspectEvidenceBrief(**payload)

    def test_rejects_pitch_angle_that_changes_the_users_offering(self):
        payload = brief_payload()
        payload["pitch_angle"] = PitchAngle(
            statement="Improve the measured mobile experience.",
            offering="Paid advertising management",
            evidence_keys=["research_evidence:mobile-score"],
        )

        with pytest.raises(ValidationError, match="user's stated offering"):
            ProspectEvidenceBrief(**payload)

    def test_rejects_outreach_that_changes_the_users_offering(self):
        payload = brief_payload()
        payload["outreach_drafts"] = [
            {
                "channel": "email",
                "subject": "A quick idea for Glow Salon",
                "message": "I noticed the measured mobile performance issue.",
                "offering": "Paid advertising management",
                "grounding": [
                    {
                        "claim": "Mobile performance measured 31/100.",
                        "evidence_keys": ["research_evidence:mobile-score"],
                    }
                ],
            }
        ]

        with pytest.raises(ValidationError, match="Outreach must use the user's stated offering"):
            ProspectEvidenceBrief(**payload)

    def test_rejects_findings_without_available_evidence(self):
        payload = brief_payload()
        payload["findings"] = [
            {
                "statement": "The mobile experience was measured at 31/100.",
                "claim_kind": BriefClaimKind.DERIVED_METRIC,
                "evidence_keys": ["not-in-the-context"],
            }
        ]

        with pytest.raises(ValidationError, match="Finding references evidence"):
            ProspectEvidenceBrief(**payload)

    def test_has_no_universal_score_field(self):
        assert "opportunity_score" not in ProspectEvidenceBrief.model_fields


class TestProspectEvidenceBriefHandoffs:
    def test_builds_goal_specific_handoffs_from_accepted_facts(self, monkeypatch):
        request_id = uuid.uuid4()
        request = ResearchRequest(
            id=request_id,
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status=ResearchStatus.COMPLETED,
            evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
            objective={
                "mode": "known_prospect",
                "goal": "Find salons worth pitching for website improvements.",
                "offering": "Website redesign and booking setup",
                "desired_outcome": "Decide whether to contact this salon.",
                "location": "Lahore",
                "resolved_target": {
                    "business_name": "Glow Salon",
                    "website": "https://glowsalon.example",
                    "identity_state": "verified",
                    "source": {
                        "provider": "tavily",
                        "source_url": "https://glowsalon.example/about",
                        "retrieved_at": NOW,
                    },
                },
            },
        )
        measurement = ResearchEvidence(
            id=uuid.uuid4(),
            research_request_id=request_id,
            signal_type=EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED.value,
            evidence_type="observed",
            supporting_value="PageSpeed measured 31/100 on mobile.",
            numeric_value=31,
            source_provider="pagespeed_insights",
            source_identity_key="pagespeed:https://glowsalon.example",
            source_url="https://glowsalon.example",
            retrieved_at=NOW,
            captured_at=NOW,
        )
        qualification = SimpleNamespace(
            opportunity_model_id="web_conversion.mobile_performance",
            state=OpportunityQualificationState.LIKELY.value,
            reason="The measured mobile score is below the threshold.",
            supporting_evidence_keys=[f"research_evidence:{measurement.id}"],
            evaluated_at=NOW,
        )
        monkeypatch.setattr(
            prospect_evidence_brief,
            "list_research_evidence_for_user",
            lambda *_: [measurement],
        )
        monkeypatch.setattr(
            prospect_evidence_brief,
            "list_opportunity_qualifications_for_user",
            lambda *_args, **_kwargs: [qualification],
        )
        monkeypatch.setattr(
            prospect_evidence_brief,
            "list_research_sources_for_user",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            prospect_evidence_brief,
            "list_social_observations_for_user",
            lambda *_args, **_kwargs: [],
        )

        handoffs = build_prospect_evidence_brief_handoffs(
            object(),
            request,
            Company(id=request.company_id, user_id=request.user_id, name="Glow Salon"),
            None,
        )

        assert handoffs.strategy_outreach.objective.offering == "Website redesign and booking setup"
        assert handoffs.opportunity_diagnosis.qualifications[0].state is OpportunityQualificationState.LIKELY
        assert handoffs.digital_presence.evidence[0].signal_type is EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED
