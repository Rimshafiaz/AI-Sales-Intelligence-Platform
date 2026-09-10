import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_prospect import CampaignProspect
from app.models.campaign_run import CampaignRun
from app.models.outreach_attempt import (
    OutreachAttempt,
    OutreachChannel,
    OutreachOutcome,
    OutreachSendMethod,
    OutreachStatus,
)
from app.models.research_report import ReportKind, ResearchReport
from app.models.research_request import ResearchRequest
from app.models.user import User
from app.schemas.outreach_attempt import (
    OutreachAttemptCreate,
    OutreachDraftUpdate,
    OutreachOutcomeUpdate,
)
from app.services.outreach_attempts import (
    OutreachAttemptError,
    approve_outreach_attempt,
    create_outreach_attempt,
    list_outreach_draft_options,
    record_manual_linkedin_send,
    record_manual_outcome,
    update_outreach_draft,
)


NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, scalar_results=None, get_results=None, scalars_results=None):
        self.scalar_results = list(scalar_results or [])
        self.get_results = list(get_results or [])
        self.scalars_results = list(scalars_results or [])
        self.added = []
        self.committed = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def scalars(self, statement):
        return FakeScalars(self.scalars_results.pop(0))

    def get(self, model, record_id):
        return self.get_results.pop(0)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def refresh(self, value):
        value.created_at = value.created_at or NOW
        value.updated_at = value.updated_at or NOW


def brief_payload(channel="email"):
    recipients = {
        "email": ("owner@glowsalon.example", "email"),
        "linkedin": ("https://linkedin.com/company/glow-salon", "linkedin"),
        "facebook": ("https://facebook.com/glowsalon", "facebook"),
    }
    recipient, contact_type = recipients[channel]
    return {
        "objective": {
            "goal": "Find salons worth pitching for website improvements.",
            "offering": "Website redesign and booking setup",
            "desired_outcome": "Decide whether to contact this salon.",
        },
        "prospect": {
            "business_name": "Glow Salon",
            "location": "Lahore",
            "official_website": "https://glowsalon.example",
            "identity_verified": True,
        },
        "verdict": {
            "opportunity_model_id": "web_conversion.mobile_performance",
            "state": "likely",
            "reason": "The measured mobile score is below the threshold.",
            "supporting_evidence_keys": ["evidence:mobile"],
            "evaluated_at": NOW.isoformat(),
        },
        "qualifications": [
            {
                "opportunity_model_id": "web_conversion.mobile_performance",
                "state": "likely",
                "reason": "The measured mobile score is below the threshold.",
                "supporting_evidence_keys": ["evidence:mobile"],
                "evaluated_at": NOW.isoformat(),
            }
        ],
        "aggregate_verdict": "qualified",
        "aggregate_headline": "Qualified opportunity",
        "evidence_quality": "high",
        "findings": [],
        "contacts": [
            {
                "contact_type": contact_type,
                "value": recipient,
                "state": "verified",
                "source_keys": ["source:official"],
            }
        ],
        "pitch_angle": {
            "statement": "Improve the measured mobile experience.",
            "offering": "Website redesign and booking setup",
            "evidence_keys": ["evidence:mobile"],
        },
        "outreach_drafts": [
            {
                "channel": channel,
                "subject": "A mobile website idea for Glow Salon" if channel == "email" else None,
                "message": "I noticed the measured mobile performance result and have a relevant idea.",
                "offering": "Website redesign and booking setup",
                "grounding": [
                    {
                        "claim": "The mobile performance result was measured.",
                        "evidence_keys": ["evidence:mobile"],
                    }
                ],
            }
        ],
        "caveats": [],
        "evidence": [
            {
                "key": "evidence:mobile",
                "signal_type": "website_mobile_performance_measured",
                "evidence_type": "observed",
                "supporting_value": "PageSpeed measured 31/100 on mobile.",
                "numeric_value": 31,
                "source": {
                    "provider": "pagespeed_insights",
                    "source_url": "https://glowsalon.example",
                    "retrieved_at": NOW.isoformat(),
                },
                "captured_at": NOW.isoformat(),
            }
        ],
        "sources": [
            {
                "key": "source:official",
                "provider": "official_website",
                "source_url": "https://glowsalon.example/contact",
                "retrieved_at": NOW.isoformat(),
            }
        ],
    }


def linked_records(channel="email"):
    owner = User(id=uuid.uuid4(), email="owner@example.com")
    campaign_id = uuid.uuid4()
    prospect = CampaignProspect(
        id=uuid.uuid4(),
        campaign_id=campaign_id,
        campaign_run_id=uuid.uuid4(),
        source_identity_key="open_places:overture:glow-salon",
        candidate_index=0,
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=owner.id,
        campaign_candidate_selection_id=uuid.uuid4(),
    )
    report = ResearchReport(
        id=uuid.uuid4(),
        research_request_id=request.id,
        company_id=request.company_id,
        user_id=owner.id,
        report_data=brief_payload(channel),
        report_kind=ReportKind.PROSPECT_EVIDENCE_BRIEF,
        generated_at=NOW,
    )
    selection = CampaignCandidateSelection(
        id=request.campaign_candidate_selection_id,
        campaign_run_id=prospect.campaign_run_id,
        company_id=request.company_id,
        source_identity_key=prospect.source_identity_key,
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    run = CampaignRun(id=prospect.campaign_run_id, campaign_id=campaign_id)
    return owner, campaign_id, prospect, request, report, selection, run


def attempt(channel=OutreachChannel.EMAIL, status=OutreachStatus.DRAFT):
    return OutreachAttempt(
        id=uuid.uuid4(),
        campaign_prospect_id=uuid.uuid4(),
        research_report_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        channel=channel,
        send_method=OutreachSendMethod.GMAIL if channel is OutreachChannel.EMAIL else OutreachSendMethod.MANUAL,
        recipient="owner@example.com" if channel is OutreachChannel.EMAIL else "https://linkedin.com/company/example",
        subject="Hello" if channel is OutreachChannel.EMAIL else None,
        body="Grounded message",
        offering="Website redesign",
        grounding_evidence_keys=["evidence:mobile"],
        contact_source_keys=["source:official"],
        status=status,
        edited_by_user=False,
    )


def test_creates_gmail_draft_only_from_matching_grounded_brief():
    owner, campaign_id, prospect, request, report, selection, run = linked_records()
    db = FakeSession(
        scalar_results=[prospect, report, None],
        get_results=[request, selection, run],
    )

    saved = create_outreach_attempt(
        db,
        campaign_id,
        prospect.id,
        owner,
        OutreachAttemptCreate(
            research_report_id=report.id,
            channel=OutreachChannel.EMAIL,
            recipient="OWNER@glowsalon.example",
        ),
    )

    assert saved.status is OutreachStatus.DRAFT
    assert saved.send_method is OutreachSendMethod.GMAIL
    assert saved.recipient == "owner@glowsalon.example"
    assert saved.grounding_evidence_keys == ["evidence:mobile"]
    assert saved.contact_source_keys == ["source:official"]
    assert saved.provider_message_id is None
    assert db.committed is True


def test_creates_and_records_a_manual_facebook_attempt():
    owner, campaign_id, prospect, request, report, selection, run = linked_records("facebook")
    db = FakeSession(
        scalar_results=[prospect, report, None],
        get_results=[request, selection, run],
    )
    saved = create_outreach_attempt(
        db,
        campaign_id,
        prospect.id,
        owner,
        OutreachAttemptCreate(
            research_report_id=report.id,
            channel=OutreachChannel.FACEBOOK,
            recipient="https://facebook.com/glowsalon",
        ),
    )
    db.scalar_results.extend([saved, saved])

    approve_outreach_attempt(db, saved.id, owner)
    sent = record_manual_linkedin_send(db, saved.id, owner)

    assert sent.send_method is OutreachSendMethod.MANUAL
    assert sent.status is OutreachStatus.SENT
    assert sent.sent_at is not None


def test_rejects_a_whitespace_only_draft_body():
    with pytest.raises(ValidationError):
        OutreachDraftUpdate(subject="Valid subject", body="   ")


def test_rejects_a_brief_linked_to_another_prospect():
    owner, campaign_id, prospect, request, report, selection, run = linked_records()
    selection.source_identity_key = "another-business"
    db = FakeSession(scalar_results=[prospect, report], get_results=[request, selection, run])

    with pytest.raises(OutreachAttemptError, match="does not belong"):
        create_outreach_attempt(
            db,
            campaign_id,
            prospect.id,
            owner,
            OutreachAttemptCreate(
                research_report_id=report.id,
                channel=OutreachChannel.EMAIL,
                recipient="owner@glowsalon.example",
            ),
        )


def test_lists_only_source_backed_options_from_the_latest_usable_brief():
    owner, campaign_id, prospect, request, report, selection, run = linked_records()
    older_report = ResearchReport(
        id=uuid.uuid4(),
        research_request_id=report.research_request_id,
        company_id=report.company_id,
        user_id=owner.id,
        report_data=report.report_data,
        report_kind=ReportKind.PROSPECT_EVIDENCE_BRIEF,
        generated_at=NOW,
    )
    db = FakeSession(
        scalar_results=[prospect],
        scalars_results=[[report, older_report], []],
    )

    options = list_outreach_draft_options(db, campaign_id, prospect.id, owner)

    assert len(options) == 1
    assert options[0].research_report_id == report.id
    assert options[0].recipient == "owner@glowsalon.example"


def test_editing_an_approved_draft_resets_approval_and_marks_user_edit():
    record = attempt(status=OutreachStatus.APPROVED)
    record.approved_at = NOW
    owner = User(id=record.user_id, email="owner@example.com")
    db = FakeSession(scalar_results=[record])

    updated = update_outreach_draft(
        db,
        record.id,
        owner,
        OutreachDraftUpdate(subject="Updated subject", body="Updated grounded wording"),
    )

    assert updated.status is OutreachStatus.DRAFT
    assert updated.approved_at is None
    assert updated.edited_by_user is True


def test_email_cannot_be_marked_sent_without_gmail():
    record = attempt(status=OutreachStatus.APPROVED)
    owner = User(id=record.user_id, email="owner@example.com")
    db = FakeSession(scalar_results=[record])

    with pytest.raises(OutreachAttemptError, match="Gmail provider"):
        record_manual_linkedin_send(db, record.id, owner)


def test_linkedin_requires_approval_then_records_manual_send_and_reply():
    record = attempt(channel=OutreachChannel.LINKEDIN)
    owner = User(id=record.user_id, email="owner@example.com")
    db = FakeSession(scalar_results=[record, record, record])

    approved = approve_outreach_attempt(db, record.id, owner)
    sent = record_manual_linkedin_send(db, record.id, owner)
    replied = record_manual_outcome(
        db,
        record.id,
        owner,
        OutreachOutcomeUpdate(outcome=OutreachOutcome.INTERESTED, replied=True),
    )

    assert approved.approved_at is not None
    assert sent.sent_at is not None
    assert replied.status is OutreachStatus.REPLIED
    assert replied.outcome is OutreachOutcome.INTERESTED
    assert replied.replied_at is not None


def test_linkedin_cannot_record_interest_without_a_reply():
    record = attempt(channel=OutreachChannel.LINKEDIN, status=OutreachStatus.SENT)
    owner = User(id=record.user_id, email="owner@example.com")
    db = FakeSession(scalar_results=[record])

    with pytest.raises(OutreachAttemptError, match="require a recorded reply"):
        record_manual_outcome(
            db,
            record.id,
            owner,
            OutreachOutcomeUpdate(outcome=OutreachOutcome.INTERESTED, replied=False),
        )
