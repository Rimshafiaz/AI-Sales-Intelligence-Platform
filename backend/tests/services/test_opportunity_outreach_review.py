from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent_outputs import BriefReviewOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.services.opportunity_outreach_review import (
    OpportunityOutreachReviewError,
    build_opportunity_outreach_review_handoff,
    validate_review_output,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)
EVIDENCE_KEY = "research_evidence:mobile"


def _context(**changes):
    value = {
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
            "reason": "Measured mobile performance supports the model.",
            "supporting_evidence_keys": [EVIDENCE_KEY],
            "evaluated_at": NOW,
        }],
        "website_research": {
            "website_status": "verified",
            "findings": [{
                "statement": "Mobile performance was measured at 31/100.",
                "claim_kind": "derived_metric",
                "evidence_keys": [EVIDENCE_KEY],
            }],
            "evidence_gaps": [],
            "caveats": [],
        },
        "social_research": None,
        "evidence": [{
            "key": EVIDENCE_KEY,
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
        "available_verified_channels": ["email", "instagram"],
    }
    value.update(changes)
    return OpportunityOutreachHandoff.model_validate(value)


def _candidate(**changes):
    value = {
        "opportunity_summary": {
            "statement": "The measured mobile result supports a redesign opportunity.",
            "claim_kind": "inference",
            "evidence_keys": [EVIDENCE_KEY],
        },
        "pitch_angle": {
            "statement": "Offer a focused redesign around the measured mobile result.",
            "offering": "Website redesign",
            "evidence_keys": [EVIDENCE_KEY],
        },
        "personalization_basis": [{
            "statement": "Reference this prospect's measured mobile result.",
            "claim_kind": "observed",
            "evidence_keys": [EVIDENCE_KEY],
        }],
        "forbidden_claims": ["Do not claim lost revenue."],
        "outreach_drafts": [{
            "channel": "email",
            "subject": "A grounded redesign idea",
            "message": "I noticed the measured mobile result. Open to one redesign idea?",
            "offering": "Website redesign",
            "grounding": [{
                "claim": "Mobile performance was measured.",
                "evidence_keys": [EVIDENCE_KEY],
            }],
        }],
        "caveats": [],
    }
    value.update(changes)
    return value


def test_valid_candidate_builds_handoff_with_unchanged_trusted_context():
    context = _context()
    original = context.model_dump()

    handoff = build_opportunity_outreach_review_handoff(context, _candidate())

    assert handoff.context == context
    assert handoff.context is not context
    assert handoff.context.model_dump() == original
    assert handoff.context.qualifications == context.qualifications
    assert handoff.context.evidence == context.evidence
    assert handoff.context.website_research == context.website_research


@pytest.mark.parametrize(
    "context",
    [
        lambda: _context(aggregate_verdict="needs_review"),
        lambda: _context(website_research=None),
    ],
)
def test_nonqualified_or_missing_specialist_context_is_rejected(context):
    with pytest.raises(OpportunityOutreachReviewError):
        build_opportunity_outreach_review_handoff(context(), _candidate())


@pytest.mark.parametrize(
    "candidate",
    [
        lambda: _candidate(pitch_angle={"statement": "Missing required fields"}),
        lambda: _candidate(pitch_angle={
            "statement": "Substitute another service.",
            "offering": "Social media management",
            "evidence_keys": [EVIDENCE_KEY],
        }),
        lambda: _candidate(outreach_drafts=[{
            "channel": "phone",
            "message": "Call about a redesign.",
            "offering": "Website redesign",
            "grounding": [{"claim": "Measured result", "evidence_keys": [EVIDENCE_KEY]}],
        }]),
    ],
)
def test_invalid_or_mismatched_candidate_cannot_enter_review(candidate):
    with pytest.raises(OpportunityOutreachReviewError):
        build_opportunity_outreach_review_handoff(_context(), candidate())


def test_approval_and_issue_consistency_is_schema_enforced():
    assert BriefReviewOutput(approved=True, issues=[]).approved is True
    assert BriefReviewOutput(
        approved=False,
        issues=[{"issue_type": "generic_outreach", "reason": "Fails the swap test."}],
    ).approved is False

    with pytest.raises(ValidationError, match="approved review cannot contain issues"):
        BriefReviewOutput(
            approved=True,
            issues=[{"issue_type": "generic_outreach", "reason": "Still generic."}],
        )
    with pytest.raises(ValidationError, match="provide issues"):
        BriefReviewOutput(approved=False, issues=[])
    with pytest.raises(ValidationError):
        BriefReviewOutput(
            approved=False,
            issues=[{"issue_type": "unknown_issue", "reason": "Invalid taxonomy."}],
        )


@pytest.mark.parametrize(
    "field",
    [
        "opportunity_summary",
        "pitch_angle",
        "personalization_basis",
        "personalization_basis[0]",
        "forbidden_claims",
        "outreach_drafts",
        "outreach_drafts[email]",
        "caveats",
    ],
)
def test_valid_reviewable_field_references_are_accepted(field):
    handoff = build_opportunity_outreach_review_handoff(_context(), _candidate())
    output = validate_review_output(
        {
            "approved": False,
            "issues": [{
                "issue_type": "unsupported_claim",
                "reason": "The cited evidence does not establish this wording.",
                "field": field,
            }],
        },
        handoff,
    )
    assert output.issues[0].field == field


@pytest.mark.parametrize(
    "field",
    [
        "qualifications",
        "evidence",
        "objective.offering",
        "personalization_basis[1]",
        "outreach_drafts[instagram]",
        "outreach_drafts[tiktok]",
        "outreach_drafts[email].message",
    ],
)
def test_invalid_or_out_of_scope_field_references_are_rejected(field):
    handoff = build_opportunity_outreach_review_handoff(_context(), _candidate())
    with pytest.raises(OpportunityOutreachReviewError, match="not reviewable"):
        validate_review_output(
            {
                "approved": False,
                "issues": [{
                    "issue_type": "unsupported_claim",
                    "reason": "Invalid field reference.",
                    "field": field,
                }],
            },
            handoff,
        )
