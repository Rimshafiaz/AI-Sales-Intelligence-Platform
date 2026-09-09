import uuid
from datetime import UTC, datetime, timedelta

from app.models.campaign_prospect import (
    CampaignProspect,
    CampaignProspectNextAction,
    CampaignProspectState,
)
from app.models.outreach_attempt import (
    OutreachAttempt,
    OutreachChannel,
    OutreachSendMethod,
    OutreachStatus,
)
from app.models.user import User
from app.services import dashboard


NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def prospect(next_action: CampaignProspectNextAction) -> CampaignProspect:
    return CampaignProspect(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        campaign_run_id=uuid.uuid4(),
        source_identity_key=f"source:{uuid.uuid4()}",
        candidate_index=0,
        candidate_snapshot={"company_name": "Glow Salon"},
        shortlist_snapshot={},
        evidence_snapshot=[],
        workflow_state=(
            CampaignProspectState.READY_FOR_OUTREACH
            if next_action is CampaignProspectNextAction.PREPARE_OUTREACH
            else CampaignProspectState.SAVED
        ),
        next_action=next_action,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=1),
    )


def outreach(
    prospect_record: CampaignProspect,
    channel: OutreachChannel,
    status: OutreachStatus,
) -> OutreachAttempt:
    return OutreachAttempt(
        id=uuid.uuid4(),
        campaign_prospect_id=prospect_record.id,
        research_report_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        channel=channel,
        send_method=(
            OutreachSendMethod.GMAIL
            if channel is OutreachChannel.EMAIL
            else OutreachSendMethod.MANUAL
        ),
        recipient="owner@example.com",
        subject="A relevant idea" if channel is OutreachChannel.EMAIL else None,
        body="Evidence-grounded message",
        offering="Website redesign",
        grounding_evidence_keys=["evidence:mobile"],
        contact_source_keys=["source:official"],
        status=status,
        edited_by_user=False,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=1),
    )


def test_builds_operational_dashboard_and_prioritizes_research(monkeypatch):
    owner = User(id=uuid.uuid4(), email="owner@example.com")
    research_prospect = prospect(CampaignProspectNextAction.RESEARCH_PROSPECT)
    outreach_prospect = prospect(CampaignProspectNextAction.PREPARE_OUTREACH)
    draft = outreach(outreach_prospect, OutreachChannel.EMAIL, OutreachStatus.DRAFT)
    approved_linkedin = outreach(outreach_prospect, OutreachChannel.LINKEDIN, OutreachStatus.APPROVED)
    approved_email = outreach(outreach_prospect, OutreachChannel.EMAIL, OutreachStatus.APPROVED)
    sent = outreach(outreach_prospect, OutreachChannel.LINKEDIN, OutreachStatus.SENT)
    sent.sent_at = NOW - timedelta(days=7)
    captured = {}

    monkeypatch.setattr(dashboard, "pipeline_counts_for_user", lambda *args: (6, 4, 2, 3, 1, 1))
    monkeypatch.setattr(
        dashboard,
        "list_actionable_prospects",
        lambda *args: [(research_prospect, "Lahore salons"), (outreach_prospect, "Lahore salons")],
    )
    monkeypatch.setattr(
        dashboard,
        "list_actionable_outreach",
        lambda *args: [
            (draft, outreach_prospect, "Lahore salons"),
            (approved_linkedin, outreach_prospect, "Lahore salons"),
            (approved_email, outreach_prospect, "Lahore salons"),
        ],
    )
    def due_rows(*args):
        captured["sent_before"] = args[2]
        return [(sent, outreach_prospect, "Lahore salons")]

    monkeypatch.setattr(dashboard, "list_follow_ups_due", due_rows)
    monkeypatch.setattr(dashboard, "list_recent_prospects", lambda *args: [])
    monkeypatch.setattr(dashboard, "list_recent_outreach", lambda *args: [])

    result = dashboard.get_dashboard_summary_for_user(object(), owner, NOW)

    assert result.pipeline.prospects_saved == 6
    assert result.next_best_action.action_type == "research_prospect"
    assert [action.action_type for action in result.needs_attention] == [
        "research_prospect",
        "approve_outreach",
        "send_linkedin",
        "awaiting_gmail",
    ]
    assert result.follow_ups_due[0].reason == "No reply has been recorded 7 days after sending."
    assert captured["sent_before"] == NOW - timedelta(days=5)


def test_returns_an_empty_operational_dashboard(monkeypatch):
    owner = User(id=uuid.uuid4(), email="owner@example.com")
    monkeypatch.setattr(dashboard, "pipeline_counts_for_user", lambda *args: (0, 0, 0, 0, 0, 0))
    monkeypatch.setattr(dashboard, "list_actionable_prospects", lambda *args: [])
    monkeypatch.setattr(dashboard, "list_actionable_outreach", lambda *args: [])
    monkeypatch.setattr(dashboard, "list_follow_ups_due", lambda *args: [])
    monkeypatch.setattr(dashboard, "list_recent_prospects", lambda *args: [])
    monkeypatch.setattr(dashboard, "list_recent_outreach", lambda *args: [])

    result = dashboard.get_dashboard_summary_for_user(object(), owner, NOW)

    assert result.next_best_action is None
    assert result.needs_attention == []
    assert result.follow_ups_due == []
    assert result.recent_activity == []
