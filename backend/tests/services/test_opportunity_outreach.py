from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.schemas.agent_outputs import OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.schemas.prospect_evidence_brief import (
    BriefContactPath,
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    ContactEvidenceState,
    ContactPathType,
    OutreachChannel,
    ProspectEvidenceBriefContext,
)
from app.services.aggregate_verdict import AggregateVerdict
from app.services.opportunity_outreach import (
    OpportunityOutreachError,
    build_opportunity_outreach_handoff,
    validate_opportunity_outreach_output,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)
MOBILE_KEY = "research_evidence:mobile"
IDENTITY_KEY = "research_evidence:identity"


def _evidence(key=MOBILE_KEY, signal="website_mobile_performance_measured"):
    return BriefEvidence(
        key=key,
        signal_type=signal,
        evidence_type="observed",
        supporting_value="Measured mobile performance was 31/100.",
        numeric_value=31,
        source={
            "provider": "test",
            "provider_record_id": key,
            "retrieved_at": NOW,
        },
        captured_at=NOW,
    )


def _context(state="likely", contacts=None):
    evidence = [
        _evidence(),
        _evidence(IDENTITY_KEY, "business_identity_confirmed"),
    ]
    return ProspectEvidenceBriefContext(
        objective=BriefObjective(
            goal="Find qualified website redesign prospects.",
            offering="Website redesign",
            desired_outcome="Prepare grounded outreach.",
        ),
        prospect=BriefProspect(
            business_name="Glow Salon",
            location="Lahore",
            official_website="https://glow.example",
            identity_verified=True,
        ),
        qualifications=[
            BriefQualification(
                opportunity_model_id="web_conversion.mobile_performance",
                state=state,
                reason="Measured mobile performance supports the model.",
                supporting_evidence_keys=[MOBILE_KEY],
                evaluated_at=NOW,
            )
        ],
        evidence=evidence,
        contacts=contacts or [],
    )


def _request(specialist_outputs=None):
    return SimpleNamespace(
        opportunity_model_selection={
            "model_ids": ["web_conversion.mobile_performance"],
            "confirmed_by_user": True,
        },
        specialist_outputs=specialist_outputs
        or {
            "website": {
                "website_status": "verified",
                "findings": [
                    {
                        "statement": "Mobile performance was measured.",
                        "claim_kind": "observed",
                        "evidence_keys": [MOBILE_KEY],
                    }
                ],
                "evidence_gaps": [],
                "caveats": [],
            }
        },
    )


def _build(monkeypatch, state="likely", contacts=None, request=None):
    context = _context(state, contacts)
    monkeypatch.setattr(
        "app.services.opportunity_outreach.build_prospect_evidence_brief_handoffs",
        lambda *_: SimpleNamespace(
            evidence_quality_review=SimpleNamespace(context=context)
        ),
    )
    return build_opportunity_outreach_handoff(
        object(), request or _request(), object(), None
    )


def _valid_output(**changes):
    value = {
        "opportunity_summary": {
            "statement": "The measured mobile performance makes this a relevant redesign prospect.",
            "claim_kind": "observed",
            "evidence_keys": [MOBILE_KEY],
        },
        "pitch_angle": {
            "statement": "Offer a focused website redesign based on the measured mobile result.",
            "offering": "Website redesign",
            "evidence_keys": [MOBILE_KEY],
        },
        "personalization_basis": [
            {
                "statement": "Reference the prospect's measured mobile result.",
                "claim_kind": "observed",
                "evidence_keys": [MOBILE_KEY],
            }
        ],
        "forbidden_claims": ["Do not claim lost revenue."],
        "outreach_drafts": [],
        "caveats": [],
    }
    value.update(changes)
    return value


def test_builder_gates_aggregate_and_requires_grounded_specialist(monkeypatch):
    handoff = _build(monkeypatch)
    assert handoff.aggregate_verdict is AggregateVerdict.QUALIFIED
    assert handoff.website_research is not None

    for state in ("insufficient_evidence", "not_eligible"):
        with pytest.raises(OpportunityOutreachError, match="QUALIFIED"):
            _build(monkeypatch, state=state)

    with pytest.raises(OpportunityOutreachError, match="Required website"):
        _build(monkeypatch, request=_request({"social": {}}))
    with pytest.raises(OpportunityOutreachError, match="unavailable canonical evidence"):
        bad = _request()
        bad.specialist_outputs["website"]["findings"][0]["evidence_keys"] = ["observation:raw"]
        _build(monkeypatch, request=bad)


def test_builder_requires_selected_social_specialist(monkeypatch):
    social_key = "research_evidence:dormancy"
    context = _context()
    context.evidence.append(_evidence(social_key, "social_dormancy_measured"))
    context.qualifications = [
        BriefQualification(
            opportunity_model_id="social_presence.dormant_official_presence",
            state="likely",
            reason="Canonical dormancy evidence supports the selected model.",
            supporting_evidence_keys=[social_key],
            evaluated_at=NOW,
        )
    ]
    monkeypatch.setattr(
        "app.services.opportunity_outreach.build_prospect_evidence_brief_handoffs",
        lambda *_: SimpleNamespace(
            evidence_quality_review=SimpleNamespace(context=context)
        ),
    )
    request = SimpleNamespace(
        opportunity_model_selection={
            "model_ids": ["social_presence.dormant_official_presence"],
            "confirmed_by_user": True,
        },
        specialist_outputs={},
    )
    with pytest.raises(OpportunityOutreachError, match="Required social"):
        build_opportunity_outreach_handoff(object(), request, object(), None)

    request.specialist_outputs = {
        "social": {
            "presence_status": "verified",
            "findings": [{
                "statement": "Dormancy was measured from canonical activity evidence.",
                "claim_kind": "observed",
                "evidence_keys": [social_key],
            }],
            "evidence_gaps": [],
            "caveats": [],
        }
    }
    assert build_opportunity_outreach_handoff(
        object(), request, object(), None
    ).social_research is not None


def test_validator_enforces_grounding_offering_and_personalization(monkeypatch):
    handoff = _build(monkeypatch)
    assert isinstance(
        validate_opportunity_outreach_output(_valid_output(), handoff),
        OpportunityOutreachOutput,
    )

    bad = _valid_output()
    bad["pitch_angle"]["evidence_keys"] = ["unknown:key"]
    with pytest.raises(OpportunityOutreachError, match="unavailable evidence"):
        validate_opportunity_outreach_output(bad, handoff)

    with pytest.raises(OpportunityOutreachError, match="stated offering"):
        validate_opportunity_outreach_output(
            _valid_output(pitch_angle={
                "statement": "Offer social media management.",
                "offering": "Social media management",
                "evidence_keys": [MOBILE_KEY],
            }),
            handoff,
        )

    duplicate = _valid_output()
    duplicate["personalization_basis"] *= 2
    with pytest.raises(OpportunityOutreachError, match="duplicates"):
        validate_opportunity_outreach_output(duplicate, handoff)

    identity_only = _valid_output()
    identity_only["personalization_basis"][0]["evidence_keys"] = [IDENTITY_KEY]
    with pytest.raises(OpportunityOutreachError, match="identity alone"):
        validate_opportunity_outreach_output(identity_only, handoff)

    social_key = "research_evidence:social"
    mixed = OpportunityOutreachHandoff.model_validate(
        {
            **handoff.model_dump(),
            "evidence": [
                *handoff.model_dump()["evidence"],
                _evidence(social_key, "social_dormancy_measured").model_dump(),
            ],
        }
    )
    wrong_family = _valid_output()
    wrong_family["pitch_angle"]["evidence_keys"] = [MOBILE_KEY, social_key]
    with pytest.raises(OpportunityOutreachError, match="outside the qualified service family"):
        validate_opportunity_outreach_output(wrong_family, mixed)

    with pytest.raises(Exception):
        validate_opportunity_outreach_output(
            {**_valid_output(), "qualifications": []}, handoff
        )


def test_verified_channels_are_exact_and_drafts_are_unique(monkeypatch):
    contacts = [
        BriefContactPath(
            contact_type=contact_type,
            value=value,
            state=ContactEvidenceState.VERIFIED,
            source_keys=[MOBILE_KEY],
        )
        for contact_type, value in (
            (ContactPathType.EMAIL, "owner@glow.example"),
            (ContactPathType.INSTAGRAM, "https://instagram.com/glow"),
            (ContactPathType.FACEBOOK, "https://facebook.com/glow"),
            (ContactPathType.LINKEDIN, "https://linkedin.com/company/glow"),
            (ContactPathType.SOCIAL_PROFILE, "https://tiktok.com/@glow"),
        )
    ]
    handoff = _build(monkeypatch, contacts=contacts)
    assert set(handoff.available_verified_channels) == {
        OutreachChannel.EMAIL,
        OutreachChannel.INSTAGRAM,
        OutreachChannel.FACEBOOK,
        OutreachChannel.LINKEDIN,
    }
    draft = {
        "channel": "email",
        "subject": "A measured mobile redesign idea",
        "message": "I noticed the measured mobile result and have one focused redesign idea.",
        "offering": "Website redesign",
        "grounding": [{"claim": "Measured mobile result", "evidence_keys": [MOBILE_KEY]}],
    }
    assert validate_opportunity_outreach_output(
        _valid_output(outreach_drafts=[draft]), handoff
    )
    with pytest.raises(OpportunityOutreachError, match="one outreach draft"):
        validate_opportunity_outreach_output(
            _valid_output(outreach_drafts=[draft, draft]), handoff
        )

    unsupported = {**draft, "channel": "phone", "subject": None}
    with pytest.raises(OpportunityOutreachError, match="verified contact path"):
        validate_opportunity_outreach_output(
            _valid_output(outreach_drafts=[unsupported]), handoff
        )


def test_handoff_schema_rejects_nonqualified_validation_context(monkeypatch):
    handoff = _build(monkeypatch)
    unsafe = OpportunityOutreachHandoff(
        **{**handoff.model_dump(), "aggregate_verdict": "needs_review"}
    )
    with pytest.raises(OpportunityOutreachError, match="QUALIFIED"):
        validate_opportunity_outreach_output(_valid_output(), unsafe)
