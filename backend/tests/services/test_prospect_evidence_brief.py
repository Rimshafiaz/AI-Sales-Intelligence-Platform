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
    BriefContactPath,
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    BriefSource,
    PitchAngle,
    ProspectEvidenceBrief,
)
from app.services import prospect_evidence_brief
from app.services.aggregate_verdict import AggregateVerdict
from app.services.prospect_evidence_brief import build_prospect_evidence_brief_context


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
        "contacts": [BriefContactPath(
            contact_type="email",
            value="owner@glowsalon.example",
            state="observed",
            source_keys=[evidence.key],
        )],
        "pitch_angle": None,
        "outreach_drafts": [],
        "caveats": [],
        "evidence": [evidence],
        "sources": [],
    }


class TestV1ProspectEvidenceBriefCompatibility:
    def test_old_persisted_shape_still_parses(self):
        brief = ProspectEvidenceBrief.model_validate(brief_payload())
        assert brief.schema_version == 1
        assert brief.verdict.state is OpportunityQualificationState.LIKELY

    def test_rejects_nonlikely_legacy_pitch(self):
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

    def test_preserves_offering_and_evidence_grounding(self):
        payload = brief_payload()
        payload["pitch_angle"] = PitchAngle(
            statement="Improve the measured mobile experience.",
            offering="Paid advertising management",
            evidence_keys=["research_evidence:mobile-score"],
        )
        with pytest.raises(ValidationError, match="user's stated offering"):
            ProspectEvidenceBrief(**payload)

        payload = brief_payload()
        payload["findings"] = [{
            "statement": "The mobile experience was measured at 31/100.",
            "claim_kind": BriefClaimKind.DERIVED_METRIC,
            "evidence_keys": ["not-in-the-context"],
        }]
        with pytest.raises(ValidationError, match="Finding references evidence"):
            ProspectEvidenceBrief(**payload)

    def test_has_no_universal_score_field(self):
        assert "opportunity_score" not in ProspectEvidenceBrief.model_fields


def test_extracts_normalized_contacts_from_accepted_source(monkeypatch):
    request = ResearchRequest(
        id=uuid.uuid4(), company_id=uuid.uuid4(), user_id=uuid.uuid4()
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
        prospect_evidence_brief, "list_social_observations_for_user", lambda *_: []
    )
    contacts = prospect_evidence_brief._brief_contacts(
        object(), request, None, None, [brief_evidence()], [source]
    )
    assert {(item.contact_type.value, item.value) for item in contacts} == {
        ("email", "hello@activfit.example"),
        ("facebook", "https://facebook.com/activfit.pk"),
    }


def test_builds_trusted_context_from_canonical_state(monkeypatch):
    request_id = uuid.uuid4()
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
    evidence_key = f"research_evidence:{measurement.id}"
    request = ResearchRequest(
        id=request_id,
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
        opportunity_model_selection={
            "model_ids": ["web_conversion.mobile_performance"],
            "confirmed_by_user": True,
        },
        specialist_outputs={
            "website": {
                "website_status": "verified",
                "findings": [{
                    "statement": "Mobile performance was measured.",
                    "claim_kind": "derived_metric",
                    "evidence_keys": [evidence_key],
                }],
                "evidence_gaps": [],
                "caveats": [],
            }
        },
        objective={
            "goal": "Find salons worth pitching for website improvements.",
            "offering": "Website redesign and booking setup",
            "desired_outcome": "Decide whether to contact this salon.",
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
    qualification = SimpleNamespace(
        opportunity_model_id="web_conversion.mobile_performance",
        state=OpportunityQualificationState.LIKELY.value,
        reason="The measured mobile score is below the threshold.",
        supporting_evidence_keys=[evidence_key],
        evaluated_at=NOW,
    )
    monkeypatch.setattr(
        prospect_evidence_brief, "list_research_evidence_for_user", lambda *_: [measurement]
    )
    monkeypatch.setattr(
        prospect_evidence_brief,
        "list_opportunity_qualifications_for_user",
        lambda *_args, **_kwargs: [qualification],
    )
    monkeypatch.setattr(
        prospect_evidence_brief, "list_research_sources_for_user", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        prospect_evidence_brief, "list_social_observations_for_user", lambda *_args, **_kwargs: []
    )

    context = build_prospect_evidence_brief_context(
        object(),
        request,
        Company(id=request.company_id, user_id=request.user_id, name="Glow Salon"),
        None,
    )
    assert context.aggregate_verdict is AggregateVerdict.QUALIFIED
    assert context.website_research is not None
    assert context.qualifications[0].supporting_evidence_keys == [evidence_key]
