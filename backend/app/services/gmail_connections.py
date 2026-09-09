import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.gmail_oauth import (
    GMAIL_OAUTH_SCOPES,
    GMAIL_SEND_SCOPE,
    GmailOAuthClient,
    GmailOAuthProviderError,
)
from app.models.gmail_connection import GmailConnection, GmailConnectionStatus, GmailOAuthState
from app.models.user import User
from app.schemas.gmail_connection import (
    GmailAuthorizationResponse,
    GmailConnectionResponse,
    GmailDisconnectResponse,
)
from app.services.gmail_token_vault import (
    GmailTokenVaultError,
    decrypt_refresh_token,
    encrypt_refresh_token,
    valid_encryption_key,
)


OAUTH_STATE_TTL_MINUTES = 10


class GmailConnectionError(ValueError):
    pass


def start_gmail_connection(db: Session, current_user: User) -> GmailAuthorizationResponse:
    client, _ = configured_gmail_dependencies()
    raw_state = secrets.token_urlsafe(32)
    state = GmailOAuthState(
        user_id=current_user.id,
        state_hash=_state_hash(raw_state),
        expires_at=datetime.now(UTC) + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
    )
    db.add(state)
    db.commit()
    return GmailAuthorizationResponse(
        authorization_url=client.authorization_url(raw_state, current_user.email)
    )


def complete_gmail_connection(
    db: Session,
    raw_state: str,
    code: str | None,
    provider_error: str | None,
) -> GmailConnection:
    client, encryption_key = configured_gmail_dependencies()
    now = datetime.now(UTC)
    state = db.scalar(
        select(GmailOAuthState)
        .where(
            GmailOAuthState.state_hash == _state_hash(raw_state),
            GmailOAuthState.consumed_at.is_(None),
            GmailOAuthState.expires_at >= now,
        )
        .with_for_update()
    )
    if state is None:
        raise GmailConnectionError("The Gmail connection request is invalid or expired.")
    state.consumed_at = now
    db.commit()
    if provider_error or not code:
        raise GmailConnectionError("Google authorization was not completed.")

    try:
        tokens = client.exchange_code(code)
        scope_values = set(str(tokens.get("scope", "")).split())
        if scope_values and GMAIL_SEND_SCOPE not in scope_values:
            raise GmailConnectionError("Gmail send permission was not granted.")
        identity = client.user_info(tokens["access_token"])
    except GmailOAuthProviderError as error:
        raise GmailConnectionError(str(error)) from error

    connection = db.scalar(select(GmailConnection).where(GmailConnection.user_id == state.user_id))
    refresh_token = tokens.get("refresh_token")
    if not isinstance(refresh_token, str):
        if connection is None or connection.google_account_id != identity["sub"]:
            raise GmailConnectionError("Google did not issue an offline refresh token.")
    else:
        try:
            encrypted_token = encrypt_refresh_token(refresh_token, encryption_key)
        except GmailTokenVaultError as error:
            raise GmailConnectionError(str(error)) from error

    if connection is None:
        connection = GmailConnection(user_id=state.user_id)
        db.add(connection)
    connection.google_account_id = identity["sub"]
    connection.email = identity["email"]
    if isinstance(refresh_token, str):
        connection.encrypted_refresh_token = encrypted_token
    connection.granted_scopes = sorted(scope_values or set(GMAIL_OAUTH_SCOPES))
    connection.status = GmailConnectionStatus.CONNECTED
    connection.connected_at = now
    connection.disconnected_at = None
    connection.last_error = None
    db.commit()
    db.refresh(connection)
    return connection


def get_gmail_connection_status(db: Session, current_user: User) -> GmailConnectionResponse:
    configured = _is_configured()
    connection = db.scalar(select(GmailConnection).where(GmailConnection.user_id == current_user.id))
    return GmailConnectionResponse(
        configured=configured,
        status=connection.status if connection else None,
        email=connection.email if connection else None,
        granted_scopes=connection.granted_scopes if connection else [],
        connected_at=connection.connected_at if connection else None,
        disconnected_at=connection.disconnected_at if connection else None,
    )


def disconnect_gmail(db: Session, current_user: User) -> GmailDisconnectResponse:
    client, encryption_key = configured_gmail_dependencies()
    connection = db.scalar(select(GmailConnection).where(GmailConnection.user_id == current_user.id))
    if connection is None or connection.status is GmailConnectionStatus.DISCONNECTED:
        raise GmailConnectionError("No connected Gmail account was found.")
    revoked = False
    if connection.encrypted_refresh_token:
        try:
            token = decrypt_refresh_token(connection.encrypted_refresh_token, encryption_key)
        except GmailTokenVaultError as error:
            raise GmailConnectionError(str(error)) from error
        revoked = client.revoke(token)
    connection.encrypted_refresh_token = None
    connection.status = GmailConnectionStatus.DISCONNECTED
    connection.disconnected_at = datetime.now(UTC)
    connection.last_error = None if revoked else "Google revocation could not be confirmed."
    db.commit()
    return GmailDisconnectResponse(
        disconnected=True,
        google_revocation_succeeded=revoked,
    )


def configured_gmail_dependencies() -> tuple[GmailOAuthClient, str]:
    if not _is_configured():
        raise GmailConnectionError("Gmail integration is not configured.")
    client_secret = settings.google_oauth_client_secret.get_secret_value()
    encryption_key = settings.gmail_token_encryption_key.get_secret_value()
    return (
        GmailOAuthClient(
            client_id=settings.google_oauth_client_id,
            client_secret=client_secret,
            redirect_uri=settings.google_oauth_redirect_uri,
        ),
        encryption_key,
    )


def _is_configured() -> bool:
    if not (
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.gmail_token_encryption_key
    ):
        return False
    return valid_encryption_key(settings.gmail_token_encryption_key.get_secret_value())


def _state_hash(raw_state: str) -> str:
    return hashlib.sha256(raw_state.encode()).hexdigest()
