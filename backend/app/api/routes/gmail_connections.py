from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import (
    AuthenticatedIdentity,
    get_authenticated_identity,
    get_current_user,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.gmail_connection import (
    GmailAuthorizationResponse,
    GmailConnectionResponse,
    GmailDisconnectResponse,
)
from app.services.gmail_connections import (
    GmailConnectionError,
    complete_gmail_connection,
    disconnect_gmail,
    get_gmail_connection_status,
    start_gmail_connection,
)


router = APIRouter(prefix="/integrations/gmail", tags=["Integrations"])


@router.get("", response_model=GmailConnectionResponse)
def gmail_connection_status_endpoint(
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> GmailConnectionResponse:
    return get_gmail_connection_status(db, current_user)


@router.post("/connect", response_model=GmailAuthorizationResponse)
def start_gmail_connection_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GmailAuthorizationResponse:
    try:
        return start_gmail_connection(db, current_user)
    except GmailConnectionError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/callback", include_in_schema=False)
def gmail_callback_endpoint(
    state: str = Query(min_length=20, max_length=512),
    code: str | None = Query(default=None, max_length=4096),
    error: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        complete_gmail_connection(db, state, code, error)
    except GmailConnectionError:
        return RedirectResponse(_frontend_redirect("error"), status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(_frontend_redirect("connected"), status_code=status.HTTP_303_SEE_OTHER)


@router.delete("", response_model=GmailDisconnectResponse)
def disconnect_gmail_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GmailDisconnectResponse:
    try:
        return disconnect_gmail(db, current_user)
    except GmailConnectionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def _frontend_redirect(result: str) -> str:
    parts = urlsplit(settings.gmail_oauth_frontend_redirect_url)
    query = dict(parse_qsl(parts.query))
    query["gmail"] = result
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
