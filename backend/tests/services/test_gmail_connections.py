import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet

from app.integrations.gmail_oauth import GMAIL_SEND_SCOPE, GmailOAuthClient
from app.models.gmail_connection import GmailConnection, GmailConnectionStatus, GmailOAuthState
from app.models.user import User
from app.services import gmail_connections
from app.services.gmail_connections import GmailConnectionError
from app.services.gmail_token_vault import (
    GmailTokenVaultError,
    decrypt_refresh_token,
    encrypt_refresh_token,
    valid_encryption_key,
)


NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeOAuthClient:
    def authorization_url(self, state, login_hint=None):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code(self, code):
        return {
            "access_token": "temporary-access-token",
            "refresh_token": "private-refresh-token",
            "scope": f"openid email {GMAIL_SEND_SCOPE}",
        }

    def user_info(self, access_token):
        return {"sub": "google-account-1", "email": "owner@gmail.com", "email_verified": True}

    def revoke(self, refresh_token):
        return False


class FakeSession:
    def __init__(self, scalar_results=None):
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.commits = 0

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.commits += 1

    def refresh(self, record):
        record.created_at = record.created_at or NOW
        record.updated_at = record.updated_at or NOW


def test_authorization_url_requests_offline_send_access():
    url = GmailOAuthClient("client", "secret", "https://app.example/callback").authorization_url(
        "safe-state", "owner@example.com"
    )
    query = parse_qs(urlsplit(url).query)

    assert query["access_type"] == ["offline"]
    assert query["state"] == ["safe-state"]
    assert GMAIL_SEND_SCOPE in query["scope"][0]


def test_token_vault_encrypts_and_rejects_the_wrong_key():
    key = Fernet.generate_key().decode()
    encrypted = encrypt_refresh_token("private-token", key)

    assert encrypted != "private-token"
    assert decrypt_refresh_token(encrypted, key) == "private-token"
    assert valid_encryption_key(key) is True
    assert valid_encryption_key("not-a-fernet-key") is False
    with pytest.raises(GmailTokenVaultError):
        decrypt_refresh_token(encrypted, Fernet.generate_key().decode())


def test_connection_uses_hashed_single_use_state_and_encrypted_token(monkeypatch):
    key = Fernet.generate_key().decode()
    owner = User(id=uuid.uuid4(), email="owner@example.com")
    db = FakeSession()
    monkeypatch.setattr(gmail_connections, "_configured_dependencies", lambda: (FakeOAuthClient(), key))
    monkeypatch.setattr(gmail_connections.secrets, "token_urlsafe", lambda size: "raw-oauth-state-value")

    authorization = gmail_connections.start_gmail_connection(db, owner)
    state = db.added[0]

    assert "raw-oauth-state-value" in str(authorization.authorization_url)
    assert state.state_hash != "raw-oauth-state-value"

    db.scalar_results = [state, None]
    connection = gmail_connections.complete_gmail_connection(
        db, "raw-oauth-state-value", "authorization-code", None
    )

    assert state.consumed_at is not None
    assert connection.status is GmailConnectionStatus.CONNECTED
    assert connection.email == "owner@gmail.com"
    assert connection.encrypted_refresh_token != "private-refresh-token"
    assert decrypt_refresh_token(connection.encrypted_refresh_token, key) == "private-refresh-token"


def test_expired_or_consumed_state_is_rejected(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(gmail_connections, "_configured_dependencies", lambda: (FakeOAuthClient(), key))

    with pytest.raises(GmailConnectionError, match="invalid or expired"):
        gmail_connections.complete_gmail_connection(
            FakeSession(scalar_results=[None]), "invalid-state-value", "code", None
        )


def test_disconnect_clears_local_token_even_if_google_revocation_fails(monkeypatch):
    key = Fernet.generate_key().decode()
    owner = User(id=uuid.uuid4(), email="owner@example.com")
    connection = GmailConnection(
        user_id=owner.id,
        google_account_id="google-account-1",
        email="owner@gmail.com",
        encrypted_refresh_token=encrypt_refresh_token("private-refresh-token", key),
        granted_scopes=[GMAIL_SEND_SCOPE],
        status=GmailConnectionStatus.CONNECTED,
        connected_at=NOW - timedelta(days=1),
    )
    db = FakeSession(scalar_results=[connection])
    monkeypatch.setattr(gmail_connections, "_configured_dependencies", lambda: (FakeOAuthClient(), key))

    result = gmail_connections.disconnect_gmail(db, owner)

    assert result.disconnected is True
    assert result.google_revocation_succeeded is False
    assert connection.encrypted_refresh_token is None
    assert connection.status is GmailConnectionStatus.DISCONNECTED
