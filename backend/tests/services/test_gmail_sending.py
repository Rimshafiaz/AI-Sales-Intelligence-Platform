import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet
import pytest

from app.integrations.gmail_oauth import GmailSendRejectedError, GmailSendUncertainError
from app.models.campaign_prospect import (
    CampaignProspect,
    CampaignProspectNextAction,
    CampaignProspectState,
)
from app.models.gmail_connection import GmailConnection, GmailConnectionStatus
from app.models.outreach_attempt import (
    OutreachAttempt,
    OutreachChannel,
    OutreachSendMethod,
    OutreachStatus,
)
from app.models.user import User
from app.services import outreach_attempts
from app.services.gmail_token_vault import encrypt_refresh_token
from app.services.outreach_attempts import OutreachAttemptError, send_approved_email


NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results, prospect=None):
        self.scalar_results = list(scalar_results)
        self.prospect = prospect
        self.commits = 0

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def get(self, model, record_id):
        return self.prospect

    def commit(self):
        self.commits += 1

    def refresh(self, record):
        record.updated_at = NOW


class SuccessfulGmailClient:
    def __init__(self):
        self.sent = None

    def refresh_access_token(self, refresh_token):
        assert refresh_token == "private-refresh-token"
        return "short-lived-access-token"

    def send_email(self, access_token, sender, recipient, subject, body):
        self.sent = (access_token, sender, recipient, subject, body)
        return "gmail-message-1", "gmail-thread-1"


class RejectedGmailClient(SuccessfulGmailClient):
    def send_email(self, access_token, sender, recipient, subject, body):
        raise GmailSendRejectedError("Gmail rejected the email.")


class UncertainGmailClient(SuccessfulGmailClient):
    def send_email(self, access_token, sender, recipient, subject, body):
        raise GmailSendUncertainError(
            "Gmail delivery could not be confirmed. Do not resend this attempt."
        )


def records(status=OutreachStatus.APPROVED):
    user = User(id=uuid.uuid4(), email="saleslens@example.com")
    prospect = CampaignProspect(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        campaign_run_id=uuid.uuid4(),
        source_identity_key="source:prospect",
        candidate_index=0,
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
        workflow_state=CampaignProspectState.READY_FOR_OUTREACH,
        next_action=CampaignProspectNextAction.PREPARE_OUTREACH,
    )
    attempt = OutreachAttempt(
        id=uuid.uuid4(),
        campaign_prospect_id=prospect.id,
        research_report_id=uuid.uuid4(),
        user_id=user.id,
        channel=OutreachChannel.EMAIL,
        send_method=OutreachSendMethod.GMAIL,
        recipient="prospect@example.com",
        subject="A relevant website observation",
        body="I noticed an evidence-backed conversion issue.",
        offering="Website conversion improvement",
        grounding_evidence_keys=["evidence:conversion"],
        contact_source_keys=["source:official"],
        status=status,
        edited_by_user=False,
    )
    key = Fernet.generate_key().decode()
    connection = GmailConnection(
        user_id=user.id,
        google_account_id="google-account-1",
        email="sender@gmail.com",
        encrypted_refresh_token=encrypt_refresh_token("private-refresh-token", key),
        granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
        status=GmailConnectionStatus.CONNECTED,
        connected_at=NOW,
    )
    return user, prospect, attempt, connection, key


def test_sends_one_approved_email_and_records_gmail_identifiers(monkeypatch):
    user, prospect, attempt, connection, key = records()
    client = SuccessfulGmailClient()
    db = FakeSession([attempt, connection, 0], prospect)
    monkeypatch.setattr(outreach_attempts, "configured_gmail_dependencies", lambda: (client, key))

    result = send_approved_email(db, attempt.id, user)

    assert client.sent == (
        "short-lived-access-token",
        "sender@gmail.com",
        "prospect@example.com",
        "A relevant website observation",
        "I noticed an evidence-backed conversion issue.",
    )
    assert result.status is OutreachStatus.SENT
    assert result.provider_message_id == "gmail-message-1"
    assert result.provider_thread_id == "gmail-thread-1"
    assert result.sent_at is not None
    assert prospect.workflow_state is CampaignProspectState.CONTACTED
    assert prospect.next_action is CampaignProspectNextAction.NO_ACTION


@pytest.mark.parametrize("attempt_status", [OutreachStatus.DRAFT, OutreachStatus.SENT])
def test_unapproved_or_already_sent_email_cannot_be_sent(attempt_status):
    user, _, attempt, _, _ = records(attempt_status)
    db = FakeSession([attempt])

    with pytest.raises(OutreachAttemptError, match="Only an approved email can be sent"):
        send_approved_email(db, attempt.id, user)


def test_missing_owner_scoped_gmail_connection_blocks_sending():
    user, _, attempt, _, _ = records()
    db = FakeSession([attempt, None])

    with pytest.raises(OutreachAttemptError, match="Connect Gmail"):
        send_approved_email(db, attempt.id, user)


def test_provider_rejection_marks_attempt_failed(monkeypatch):
    user, prospect, attempt, connection, key = records()
    db = FakeSession([attempt, connection, 0], prospect)
    monkeypatch.setattr(
        outreach_attempts,
        "configured_gmail_dependencies",
        lambda: (RejectedGmailClient(), key),
    )

    result = send_approved_email(db, attempt.id, user)

    assert result.status is OutreachStatus.FAILED
    assert result.failure_reason == "Gmail rejected the email."
    assert result.provider_message_id is None


def test_uncertain_delivery_stays_blocked_from_resending(monkeypatch):
    user, prospect, attempt, connection, key = records()
    db = FakeSession([attempt, connection, 0], prospect)
    monkeypatch.setattr(
        outreach_attempts,
        "configured_gmail_dependencies",
        lambda: (UncertainGmailClient(), key),
    )

    result = send_approved_email(db, attempt.id, user)

    assert result.status is OutreachStatus.SENDING
    assert "Do not resend" in result.failure_reason


def test_daily_limit_blocks_email_before_gmail_is_called(monkeypatch):
    user, prospect, attempt, connection, key = records()
    client = SuccessfulGmailClient()
    db = FakeSession([attempt, connection, outreach_attempts.settings.gmail_send_limit_per_day], prospect)
    monkeypatch.setattr(outreach_attempts, "configured_gmail_dependencies", lambda: (client, key))

    with pytest.raises(OutreachAttemptError, match="daily send limit"):
        send_approved_email(db, attempt.id, user)
    assert client.sent is None
