from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.gmail_connection import GmailConnectionStatus


class GmailAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_url: HttpUrl


class GmailConnectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    status: GmailConnectionStatus | None
    email: str | None
    granted_scopes: list[str]
    reply_tracking_enabled: bool
    connected_at: datetime | None
    disconnected_at: datetime | None


class GmailDisconnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disconnected: bool
    google_revocation_succeeded: bool
