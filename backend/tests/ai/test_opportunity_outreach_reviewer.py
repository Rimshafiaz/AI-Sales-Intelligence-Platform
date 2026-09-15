from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.ai import opportunity_outreach_review
from app.ai.tasks.opportunity_outreach_review_task import (
    create_opportunity_outreach_review_task,
)
from app.schemas.agent_outputs import BriefReviewOutput
from app.schemas.opportunity_outreach_review import OpportunityOutreachReviewHandoff
from app.services.opportunity_outreach_review import (
    OpportunityOutreachReviewError,
    build_opportunity_outreach_review_handoff,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)
KEY = "research_evidence:mobile"


def _handoff():
    return build_opportunity_outreach_review_handoff(
        {
            "objective": {
                "goal": "Find qualified redesign prospects.",
                "offering": "Website redesign",
                "desired_outcome": "Prepare grounded outreach.",
            },
            "prospect": {
                "business_name": "Glow Salon",
                "location": "Lahore",
                "official_website": "https://glow.example",
                "identity_verified": True,
            },
            "aggregate_verdict": "qualified",
            "qualifications": [{
                "opportunity_model_id": "web_conversion.mobile_performance",
                "state": "likely",
                "reason": "The measured result supports the selected model.",
                "supporting_evidence_keys": [KEY],
                "evaluated_at": NOW,
            }],
            "website_research": {
                "website_status": "verified",
                "findings": [{
                    "statement": "Mobile performance was measured at 31/100.",
                    "claim_kind": "derived_metric",
                    "evidence_keys": [KEY],
                }],
                "evidence_gaps": [],
                "caveats": [],
            },
            "social_research": None,
            "evidence": [{
                "key": KEY,
                "signal_type": "website_mobile_performance_measured",
                "evidence_type": "observed",
                "supporting_value": "PageSpeed measured 31/100 on mobile.",
                "numeric_value": 31,
                "source": {
                    "provider": "pagespeed",
                    "provider_record_id": "mobile",
                    "retrieved_at": NOW,
                },
                "captured_at": NOW,
            }],
            "available_verified_channels": ["email"],
        },
        {
            "opportunity_summary": {
                "statement": "The measured mobile result supports a redesign opportunity.",
                "claim_kind": "inference",
                "evidence_keys": [KEY],
            },
            "pitch_angle": {
                "statement": "Offer a focused redesign around the measured result.",
                "offering": "Website redesign",
                "evidence_keys": [KEY],
            },
            "personalization_basis": [{
                "statement": "Reference this prospect's measured mobile result.",
                "claim_kind": "observed",
                "evidence_keys": [KEY],
            }],
            "forbidden_claims": ["Do not claim lost customers or revenue."],
            "outreach_drafts": [{
                "channel": "email",
                "subject": "A grounded redesign idea",
                "message": "I noticed the measured mobile result. Open to one redesign idea?",
                "offering": "Website redesign",
                "grounding": [{
                    "claim": "Mobile performance was measured.",
                    "evidence_keys": [KEY],
                }],
            }],
            "caveats": [],
        },
    )


def test_reviewer_and_task_have_no_tools():
    task = create_opportunity_outreach_review_task(_handoff())

    assert task.tools == []
    assert task.agent.tools == []
    assert "no tools" in task.description.casefold()


def test_grounded_candidate_can_be_approved(monkeypatch):
    handoff = _handoff()
    original = deepcopy(handoff.model_dump())
    monkeypatch.setattr(
        opportunity_outreach_review,
        "_run_task",
        lambda _task: BriefReviewOutput(approved=True, issues=[]),
    )

    output = opportunity_outreach_review.run_opportunity_outreach_reviewer(handoff)

    assert output == BriefReviewOutput(approved=True, issues=[])
    assert handoff.model_dump() == original


@pytest.mark.parametrize(
    ("issue_type", "field"),
    [
        ("unsupported_claim", "opportunity_summary"),
        ("qualification_contradiction", "pitch_angle"),
        ("generic_outreach", "outreach_drafts[email]"),
        ("weak_personalization", "personalization_basis[0]"),
        ("duplicate_insight", "personalization_basis"),
        ("overstated_evidence", "outreach_drafts[email]"),
        ("unsupported_channel", "outreach_drafts[email]"),
        ("irrelevant_finding", "opportunity_summary"),
    ],
)
def test_semantic_issue_taxonomy_passes_deterministic_acceptance(
    monkeypatch, issue_type, field
):
    handoff = _handoff()
    monkeypatch.setattr(
        opportunity_outreach_review,
        "_run_task",
        lambda _task: {
            "approved": False,
            "issues": [{
                "issue_type": issue_type,
                "reason": "The candidate has a concrete semantic review problem.",
                "field": field,
            }],
        },
    )

    output = opportunity_outreach_review.run_opportunity_outreach_reviewer(handoff)

    assert output.approved is False
    assert output.issues[0].issue_type == issue_type


@pytest.mark.parametrize(
    "invalid_output",
    [
        {
            "approved": True,
            "issues": [{
                "issue_type": "generic_outreach",
                "reason": "Approval cannot retain an issue.",
            }],
        },
        {"approved": False, "issues": []},
        {
            "approved": False,
            "issues": [{
                "issue_type": "unsupported_claim",
                "reason": "Invalid field path.",
                "field": "qualifications",
            }],
        },
        {
            "approved": False,
            "issues": [{
                "issue_type": "unsupported_claim",
                "reason": "Do not rewrite output.",
            }],
            "rewritten_outreach": "Replacement copy",
        },
    ],
)
def test_malformed_or_mutating_reviewer_output_is_rejected(
    monkeypatch, invalid_output
):
    monkeypatch.setattr(
        opportunity_outreach_review,
        "_run_task",
        lambda _task: invalid_output,
    )

    with pytest.raises(OpportunityOutreachReviewError):
        opportunity_outreach_review.run_opportunity_outreach_reviewer(_handoff())


def test_orchestrator_revalidates_the_trusted_handoff(monkeypatch):
    handoff = _handoff().model_dump()
    handoff["context"]["qualifications"][0]["state"] = "not_eligible"
    corrupted = OpportunityOutreachReviewHandoff.model_validate(handoff)
    called = False

    def run(_task):
        nonlocal called
        called = True

    monkeypatch.setattr(opportunity_outreach_review, "_run_task", run)
    with pytest.raises(OpportunityOutreachReviewError):
        opportunity_outreach_review.run_opportunity_outreach_reviewer(corrupted)
    assert called is False
