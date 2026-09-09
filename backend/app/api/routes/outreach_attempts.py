from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.outreach_attempt import OutreachAttempt
from app.schemas.outreach_attempt import (
    OutreachAttemptCreate,
    OutreachAttemptResponse,
    OutreachDraftOptionResponse,
    OutreachDraftUpdate,
    OutreachOutcomeUpdate,
)
from app.services.outreach_attempts import (
    OutreachAttemptError,
    approve_outreach_attempt,
    create_outreach_attempt,
    list_outreach_attempts,
    list_outreach_draft_options,
    outreach_attempt_response,
    record_manual_linkedin_send,
    record_manual_outcome,
    send_approved_email,
    update_outreach_draft,
)


router = APIRouter(tags=["Outreach"])


@router.get(
    "/campaigns/{campaign_id}/prospects/{prospect_id}/outreach-options",
    response_model=list[OutreachDraftOptionResponse],
)
def list_outreach_options_endpoint(
    campaign_id: UUID,
    prospect_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OutreachDraftOptionResponse]:
    try:
        return list_outreach_draft_options(db, campaign_id, prospect_id, current_user)
    except OutreachAttemptError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/campaigns/{campaign_id}/prospects/{prospect_id}/outreach-attempts",
    response_model=OutreachAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_outreach_attempt_endpoint(
    campaign_id: UUID,
    prospect_id: UUID,
    request: OutreachAttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    try:
        attempt = create_outreach_attempt(db, campaign_id, prospect_id, current_user, request)
    except OutreachAttemptError as error:
        code = status.HTTP_404_NOT_FOUND if str(error) == "Campaign prospect not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(error)) from error
    return outreach_attempt_response(attempt)


@router.get(
    "/campaigns/{campaign_id}/prospects/{prospect_id}/outreach-attempts",
    response_model=list[OutreachAttemptResponse],
)
def list_outreach_attempts_endpoint(
    campaign_id: UUID,
    prospect_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OutreachAttemptResponse]:
    try:
        attempts = list_outreach_attempts(db, campaign_id, prospect_id, current_user)
    except OutreachAttemptError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [outreach_attempt_response(attempt) for attempt in attempts]


@router.patch(
    "/outreach-attempts/{attempt_id}/draft",
    response_model=OutreachAttemptResponse,
)
def update_outreach_draft_endpoint(
    attempt_id: UUID,
    request: OutreachDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    return _run(attempt_id, current_user, update_outreach_draft, db, request)


@router.post(
    "/outreach-attempts/{attempt_id}/approve",
    response_model=OutreachAttemptResponse,
)
def approve_outreach_attempt_endpoint(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    return _run(attempt_id, current_user, approve_outreach_attempt, db)


@router.post(
    "/outreach-attempts/{attempt_id}/send-email",
    response_model=OutreachAttemptResponse,
)
def send_approved_email_endpoint(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    return _run(attempt_id, current_user, send_approved_email, db)


@router.post(
    "/outreach-attempts/{attempt_id}/manual-linkedin-send",
    response_model=OutreachAttemptResponse,
)
def record_manual_linkedin_send_endpoint(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    return _run(attempt_id, current_user, record_manual_linkedin_send, db)


@router.post(
    "/outreach-attempts/{attempt_id}/manual-outcome",
    response_model=OutreachAttemptResponse,
)
def record_manual_outcome_endpoint(
    attempt_id: UUID,
    request: OutreachOutcomeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachAttemptResponse:
    return _run(attempt_id, current_user, record_manual_outcome, db, request)


def _run(
    attempt_id: UUID,
    current_user: User,
    operation: Callable[..., OutreachAttempt],
    db: Session,
    *args: Any,
) -> OutreachAttemptResponse:
    try:
        attempt = operation(db, attempt_id, current_user, *args)
    except OutreachAttemptError as error:
        code = status.HTTP_404_NOT_FOUND if str(error) == "Outreach attempt not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=str(error)) from error
    return outreach_attempt_response(attempt)
