from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.ai import opportunity_outreach
from app.ai.tasks.opportunity_outreach_task import create_opportunity_outreach_task
from app.schemas.agent_outputs import OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.services.opportunity_outreach import OpportunityOutreachError


NOW = datetime(2026, 9, 15, tzinfo=UTC)


def _handoff(family="web", verdict="qualified"):
    if family == "web":
        model_id = "web_conversion.mobile_performance"
        signal = "website_mobile_performance_measured"
        key = "research_evidence:mobile"
        offering = "Website redesign"
        website = {
            "website_status": "verified",
            "findings": [{
                "statement": "Mobile performance was measured at 31/100.",
                "claim_kind": "derived_metric",
                "evidence_keys": [key],
            }],
            "evidence_gaps": [],
            "caveats": [],
        }
        social = None
    else:
        model_id = "social_presence.dormant_official_presence"
        signal = "social_dormancy_measured"
        key = "research_evidence:dormancy"
        offering = "Social media management"
        website = None
        social = {
            "presence_status": "verified",
            "findings": [{
                "statement": "Official social activity dormancy was measured.",
                "claim_kind": "derived_metric",
                "evidence_keys": [key],
            }],
            "evidence_gaps": [],
            "caveats": [],
        }
    return OpportunityOutreachHandoff(
        objective={
            "goal": "Prepare grounded outreach for qualified prospects.",
            "offering": offering,
            "desired_outcome": "Prepare one relevant outreach draft.",
        },
        prospect={
            "business_name": "Glow Salon",
            "location": "Lahore",
            "official_website": "https://glow.example",
            "identity_verified": True,
        },
        aggregate_verdict=verdict,
        qualifications=[{
            "opportunity_model_id": model_id,
            "state": "likely",
            "reason": "Canonical evidence satisfies the selected model.",
            "supporting_evidence_keys": [key],
            "evaluated_at": NOW,
        }],
        website_research=website,
        social_research=social,
        evidence=[{
            "key": key,
            "signal_type": signal,
            "evidence_type": "observed",
            "supporting_value": "Canonical prospect-specific measurement.",
            "numeric_value": 31,
            "source": {
                "provider": "test",
                "provider_record_id": key,
                "retrieved_at": NOW,
            },
            "captured_at": NOW,
        }],
        available_verified_channels=["email"],
    )


def _output(handoff, evidence_key=None):
    key = evidence_key or handoff.evidence[0].key
    offering = handoff.objective.offering
    angle = (
        "Offer a focused redesign around the measured mobile result."
        if offering == "Website redesign"
        else "Offer a focused content cadence around the measured social dormancy."
    )
    return OpportunityOutreachOutput(
        opportunity_summary={
            "statement": "This qualified measurement is relevant to the seller's offering.",
            "claim_kind": "inference",
            "evidence_keys": [key],
        },
        pitch_angle={
            "statement": angle,
            "offering": offering,
            "evidence_keys": [key],
        },
        personalization_basis=[{
            "statement": "Reference this prospect's canonical measured result.",
            "claim_kind": "observed",
            "evidence_keys": [key],
        }],
        forbidden_claims=["Do not claim lost revenue or customers."],
        outreach_drafts=[{
            "channel": "email",
            "subject": "A grounded idea for Glow Salon",
            "message": f"I noticed the measured result. Open to one idea for {offering}?",
            "offering": offering,
            "grounding": [{
                "claim": "A canonical measurement exists.",
                "evidence_keys": [key],
            }],
        }],
    )


@pytest.mark.parametrize("family", ["web", "social"])
def test_grounded_family_aligned_output_runs_without_tools(monkeypatch, family):
    handoff = _handoff(family)
    qualifications_before = deepcopy(handoff.qualifications)
    monkeypatch.setattr(opportunity_outreach, "_run_task", lambda task: _output(handoff))

    result = opportunity_outreach.run_opportunity_outreach_agent(handoff)

    assert isinstance(result, OpportunityOutreachOutput)
    assert result.pitch_angle.offering == handoff.objective.offering
    assert result.pitch_angle.evidence_keys == [handoff.evidence[0].key]
    assert handoff.qualifications == qualifications_before


def test_agent_and_task_have_no_tools():
    task = create_opportunity_outreach_task(_handoff())

    assert task.tools == []
    assert task.agent.tools == []
    assert "no tools" in task.description.casefold()


def test_nonqualified_handoff_cannot_execute(monkeypatch):
    handoff = _handoff(verdict="needs_review")
    called = False

    def run(_task):
        nonlocal called
        called = True
        return _output(handoff)

    monkeypatch.setattr(opportunity_outreach, "_run_task", run)
    with pytest.raises(OpportunityOutreachError, match="QUALIFIED"):
        opportunity_outreach.run_opportunity_outreach_agent(handoff)
    assert called is False


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("unknown_evidence", "unavailable evidence"),
        ("wrong_offering", "stated offering"),
        ("unsupported_channel", "verified contact path"),
        ("duplicate_channel", "one outreach draft"),
    ],
)
def test_orchestrator_rejects_invalid_llm_output(monkeypatch, change, message):
    handoff = _handoff()
    output = _output(handoff).model_dump()
    if change == "unknown_evidence":
        output["opportunity_summary"]["evidence_keys"] = ["fabricated:key"]
    elif change == "wrong_offering":
        output["pitch_angle"]["offering"] = "Social media management"
    elif change == "unsupported_channel":
        output["outreach_drafts"][0].update(channel="phone", subject=None)
    else:
        output["outreach_drafts"] *= 2
    monkeypatch.setattr(opportunity_outreach, "_run_task", lambda _task: output)

    with pytest.raises(OpportunityOutreachError, match=message):
        opportunity_outreach.run_opportunity_outreach_agent(handoff)


def test_identity_only_personalization_is_rejected(monkeypatch):
    handoff = _handoff()
    identity_key = "research_evidence:identity"
    handoff.evidence.append(
        type(handoff.evidence[0]).model_validate(
            {
                **handoff.evidence[0].model_dump(),
                "key": identity_key,
                "signal_type": "business_identity_confirmed",
            }
        )
    )
    output = _output(handoff).model_dump()
    output["personalization_basis"][0]["evidence_keys"] = [identity_key]
    monkeypatch.setattr(opportunity_outreach, "_run_task", lambda _task: output)

    with pytest.raises(OpportunityOutreachError, match="identity alone"):
        opportunity_outreach.run_opportunity_outreach_agent(handoff)
