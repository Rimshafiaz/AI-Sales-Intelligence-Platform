import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet
import pytest

from app.integrations.gmail_oauth import GMAIL_METADATA_SCOPE
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
from app.services.outreach_attempts import OutreachAttemptError, check_gmail_reply


NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.commits = 0

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def commit(self):
        self.commits += 1

    def refresh(self, record):
        record.updated_at = NOW


class FakeGmailClient:
    def __init__(self, messages):
        self.messages = messages
        self.checked_thread_id = None

    def refresh_access_token(self, refresh_token):
        assert refresh_token == "private-refresh-token"
        return "access-token"

    def thread_metadata(self, access_token, thread_id):
        assert access_token == "access-token"
        self.checked_thread_id = thread_id
        return {"id": thread_id, "messages": self.messages}


def records(scopes=None, status=OutreachStatus.SENT):
    user = User(id=uuid.uuid4(), email="owner@example.com")
    attempt = OutreachAttempt(
        id=uuid.uuid4(),
        campaign_prospect_id=uuid.uuid4(),
        research_report_id=uuid.uuid4(),
        user_id=user.id,
        channel=OutreachChannel.EMAIL,
        send_method=OutreachSendMethod.GMAIL,
        recipient="prospect@example.com",
        subject="Relevant idea",
        body="Grounded message",
        offering="Website improvement",
        grounding_evidence_keys=["evidence:web"],
        contact_source_keys=["source:official"],
        status=status,
        provider_message_id="sent-message-1",
        provider_thread_id="thread-1",
        sent_at=NOW,
        edited_by_user=False,
    )
    key = Fernet.generate_key().decode()
    connection = GmailConnection(
        user_id=user.id,
        google_account_id="google-account-1",
        email="sender@gmail.com",
        encrypted_refresh_token=encrypt_refresh_token("private-refresh-token", key),
        granted_scopes=scopes if scopes is not None else [GMAIL_METADATA_SCOPE],
        status=GmailConnectionStatus.CONNECTED,
        connected_at=NOW,
    )
    return user, attempt, connection, key


def test_detects_first_incoming_message_after_the_sent_message(monkeypatch):
    user, attempt, connection, key = records()
    client = FakeGmailClient(
        [
            {"id": "sent-message-1", "internalDate": "1000", "labelIds": ["SENT"]},
            {"id": "draft-1", "internalDate": "2000", "labelIds": ["DRAFT"]},
            {"id": "sent-message-2", "internalDate": "3000", "labelIds": ["SENT"]},
            {"id": "reply-1", "internalDate": "4000", "labelIds": ["INBOX"]},
            {"id": "reply-2", "internalDate": "5000", "labelIds": []},
        ]
    )
    db = FakeSession([attempt, connection])
    monkeypatch.setattr(outreach_attempts, "configured_gmail_dependencies", lambda: (client, key))

    result = check_gmail_reply(db, attempt.id, user)

    assert result.status is OutreachStatus.REPLIED
    assert result.provider_reply_message_id == "reply-1"
    assert result.replied_at == datetime.fromtimestamp(4, UTC)
    assert client.checked_thread_id == "thread-1"
    assert db.commits == 1


def test_no_incoming_message_leaves_attempt_sent(monkeypatch):
    user, attempt, connection, key = records()
    client = FakeGmailClient(
        [
            {"id": "sent-message-1", "internalDate": "1000", "labelIds": ["SENT"]},
            {"id": "sent-message-2", "internalDate": "2000", "labelIds": ["SENT"]},
        ]
    )
    db = FakeSession([attempt, connection])
    monkeypatch.setattr(outreach_attempts, "configured_gmail_dependencies", lambda: (client, key))

    result = check_gmail_reply(db, attempt.id, user)

    assert result.status is OutreachStatus.SENT
    assert result.replied_at is None
    assert db.commits == 0


def test_missing_metadata_scope_requires_reconnection():
    user, attempt, connection, _ = records(scopes=[])
    db = FakeSession([attempt, connection])

    with pytest.raises(OutreachAttemptError, match="Reconnect Gmail"):
        check_gmail_reply(db, attempt.id, user)


def test_already_recorded_reply_is_idempotent():
    user, attempt, _, _ = records(status=OutreachStatus.REPLIED)
    attempt.provider_reply_message_id = "reply-1"
    attempt.replied_at = NOW
    db = FakeSession([attempt])

    result = check_gmail_reply(db, attempt.id, user)

    assert result is attempt
    assert db.commits == 0
