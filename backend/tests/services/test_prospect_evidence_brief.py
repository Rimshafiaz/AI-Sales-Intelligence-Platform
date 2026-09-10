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
    BusinessContextHandoff,
    BriefClaimKind,
    BriefContactPath,
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    BriefSource,
    DigitalPresenceHandoff,
    EvidenceQualityReviewHandoff,
    OpportunityDiagnosisHandoff,
    PitchAngle,
    ProspectEvidenceBrief,
    ProspectEvidenceBriefContext,
    ProspectEvidenceBriefHandoffs,
    PublicTractionHandoff,
    StrategyOutreachHandoff,
)
from app.schemas.agent_outputs import BriefFindingsOutput, BriefReviewerOutput, BriefStrategyOutput
from app.ai.crew import assemble_prospect_evidence_brief
from app.services.prospect_evidence_brief_review import (
    ProspectEvidenceBriefReviewError,
    require_approved_prospect_evidence_brief,
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
        "contacts": [
            BriefContactPath(
                contact_type="email",
                value="owner@glowsalon.example",
                state="observed",
                source_keys=[evidence.key],
            )
        ],
        "pitch_angle": None,
        "outreach_drafts": [],
        "caveats": [],
        "evidence": [evidence],
        "sources": [],
    }


def brief_handoffs():
    payload = brief_payload()
    context = ProspectEvidenceBriefContext(
        objective=payload["objective"],
        prospect=payload["prospect"],
        qualifications=[payload["verdict"]],
        evidence=payload["evidence"],
        sources=[],
        contacts=payload["contacts"],
    )
    return ProspectEvidenceBriefHandoffs(
        business_context=BusinessContextHandoff(
            objective=context.objective,
            prospect=context.prospect,
            evidence=context.evidence,
            sources=context.sources,
        ),
        digital_presence=DigitalPresenceHandoff(
            objective=context.objective,
            prospect=context.prospect,
            evidence=context.evidence,
        ),
        public_traction=PublicTractionHandoff(
            objective=context.objective,
            prospect=context.prospect,
            sources=context.sources,
            evidence=context.evidence,
        ),
        opportunity_diagnosis=OpportunityDiagnosisHandoff(
            objective=context.objective,
            prospect=context.prospect,
            qualifications=context.qualifications,
            evidence=context.evidence,
        ),
        strategy_outreach=StrategyOutreachHandoff(
            objective=context.objective,
            prospect=context.prospect,
            qualifications=context.qualifications,
            evidence=context.evidence,
            contacts=context.contacts,
        ),
        evidence_quality_review=EvidenceQualityReviewHandoff(context=context),
    )


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
    def test_extracts_email_and_social_contact_from_accepted_source(self, monkeypatch):
        request = ResearchRequest(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
        source = BriefSource(
            key="research_source:facebook",
            provider="web_search",
            source_url="https://facebook.com/activfit.pk",
            retrieved_at=NOW,
            title="Activfit Lahore",
            excerpt="Business enquiries: hello@activfit.example",
        )
        monkeypatch.setattr(
            prospect_evidence_brief,
            "list_social_observations_for_user",
            lambda *_: [],
        )

        contacts = prospect_evidence_brief._brief_contacts(
            object(), request, None, None, [brief_evidence()], [source]
        )

        assert {(item.contact_type.value, item.value) for item in contacts} == {
            ("email", "hello@activfit.example"),
            ("facebook", "https://facebook.com/activfit.pk"),
        }

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


class TestProspectEvidenceBriefAssemblyAndReview:
    def test_discards_unknown_llm_fields_before_final_brief_assembly(self):
        output = BriefFindingsOutput.model_validate(
            {
                "findings": [
                    {
                        "statement": "Mobile performance was measured at 31/100.",
                        "claim_kind": "derived_metric",
                        "evidence_keys": ["research_evidence:mobile-score"],
                        "identity": "Unsupported agent-generated context.",
                    }
                ]
            }
        )

        assert output.findings[0].model_dump() == {
            "statement": "Mobile performance was measured at 31/100.",
            "claim_kind": "derived_metric",
            "evidence_keys": ["research_evidence:mobile-score"],
        }

    def test_assembles_fixed_context_with_goal_specific_strategy(self):
        handoffs = brief_handoffs()
        findings = [
            BriefFindingsOutput(
                findings=[
                    {
                        "statement": "Mobile performance was measured at 31/100.",
                        "claim_kind": "derived_metric",
                        "evidence_keys": ["research_evidence:mobile-score"],
                    }
                ]
            )
        ]
        strategy = BriefStrategyOutput(
            pitch_angle={
                "statement": "A mobile-focused booking improvement may be relevant.",
                "offering": "Website redesign and booking setup",
                "evidence_keys": ["research_evidence:mobile-score"],
            },
            outreach_drafts=[
                {
                    "channel": "email",
                    "subject": "A quick mobile booking idea",
                    "message": "I noticed your mobile score was measured at 31/100.",
                    "offering": "Website redesign and booking setup",
                    "grounding": [
                        {
                            "claim": "Mobile performance was measured at 31/100.",
                            "evidence_keys": ["research_evidence:mobile-score"],
                        }
                    ],
                }
            ],
        )

        brief = assemble_prospect_evidence_brief(handoffs, findings, strategy)

        assert brief.objective == handoffs.business_context.objective
        assert brief.prospect == handoffs.business_context.prospect
        assert brief.verdict == handoffs.opportunity_diagnosis.qualifications[0]
        assert brief.pitch_angle is not None
        assert brief.outreach_drafts[0].offering == brief.objective.offering

    def test_discards_agent_content_outside_the_brief_evidence(self):
        handoffs = brief_handoffs()
        findings = [
            BriefFindingsOutput(
                findings=[
                    {
                        "statement": "An unavailable measurement suggests a problem.",
                        "claim_kind": "inference",
                        "evidence_keys": ["unavailable-evidence"],
                    }
                ]
            )
        ]
        strategy = BriefStrategyOutput(
            pitch_angle={
                "statement": "Improve an unavailable measurement.",
                "offering": "Website redesign and booking setup",
                "evidence_keys": ["unavailable-evidence"],
            },
            outreach_drafts=[
                {
                    "channel": "email",
                    "subject": "A quick idea for Glow Salon",
                    "message": "I noticed an unavailable measurement.",
                    "offering": "Website redesign and booking setup",
                    "grounding": [
                        {
                            "claim": "An unavailable measurement exists.",
                            "evidence_keys": ["unavailable-evidence"],
                        }
                    ],
                }
            ],
        )

        brief = assemble_prospect_evidence_brief(handoffs, findings, strategy)

        assert brief.findings == []
        assert brief.pitch_angle is None
        assert brief.outreach_drafts == []

    def test_reviewer_rejection_blocks_the_brief(self):
        handoffs = brief_handoffs()
        brief = ProspectEvidenceBrief(**brief_payload())

        with pytest.raises(ProspectEvidenceBriefReviewError, match="reviewer rejected"):
            require_approved_prospect_evidence_brief(
                handoffs,
                brief,
                BriefReviewerOutput(approved=False, issues=["The finding is generic."]),
            )

    def test_commercial_claim_blocks_even_when_reviewer_approves(self):
        handoffs = brief_handoffs()
        payload = brief_payload()
        payload["findings"] = [
            {
                "statement": "The business needs a website redesign.",
                "claim_kind": "inference",
                "evidence_keys": ["research_evidence:mobile-score"],
            }
        ]
        brief = ProspectEvidenceBrief(**payload)

        with pytest.raises(ProspectEvidenceBriefReviewError, match="unsupported commercial claim"):
            require_approved_prospect_evidence_brief(
                handoffs,
                brief,
                BriefReviewerOutput(approved=True),
            )
