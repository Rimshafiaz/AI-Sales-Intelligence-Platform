from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.models.research_request import ResearchRequest, ResearchStatus


def create_research_request(
    db: Session,
    company_id: UUID,
    user_id: UUID,
) -> ResearchRequest:
    research_request = ResearchRequest(
        company_id=company_id,
        user_id=user_id,
        status=ResearchStatus.PENDING,
    )
    db.add(research_request)
    db.commit()
    db.refresh(research_request)
    return research_request

def get_research_request_for_user(
    db: Session,
    request_id: UUID,
    user_id: UUID,
) -> ResearchRequest | None:
    statement = select(ResearchRequest).where(
        ResearchRequest.id == request_id,
        ResearchRequest.user_id == user_id,
    )
    return db.scalar(statement)


def mark_research_request_running(
    db: Session,
    request_id: UUID,
) -> ResearchRequest | None:
    statement = select(ResearchRequest).where(
        ResearchRequest.id == request_id,
    )
    request = db.scalar(statement)
    if request is None:
        return None
    request.status = ResearchStatus.RUNNING
    request.started_at = datetime.now(timezone.utc)
    request.error_message = None
    db.commit()
    db.refresh(request)
    return request


def mark_research_request_complete(
    db: Session,
    request_id: UUID,
) -> ResearchRequest | None:
    statement = select(ResearchRequest).where(
        ResearchRequest.id == request_id,
    )
    request = db.scalar(statement)
    if request is None:
        return None
    request.status = ResearchStatus.COMPLETED
    request.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


def mark_research_request_failed(
    db: Session,
    request_id: UUID,
    safe_error_message: str,
) -> ResearchRequest | None:
    statement = select(ResearchRequest).where(
        ResearchRequest.id == request_id,
    )
    request = db.scalar(statement)
    if request is None:
        return None
    request.status = ResearchStatus.FAILED
    request.finished_at = datetime.now(timezone.utc)
    request.error_message = safe_error_message
    db.commit()
    db.refresh(request)
    return request

def get_research_request_by_id(db: Session, request_id: UUID) -> ResearchRequest | None:
    statement = select(ResearchRequest).where(ResearchRequest.id == request_id)
    return db.scalar(statement)