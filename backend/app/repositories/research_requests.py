from uuid import UUID
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.models.research_request import ResearchRequest, ResearchStatus
from app.schemas.evidence_gate import EvidenceGateResponse
from app.schemas.website_audit import WebsiteAuditResult
from app.schemas.website_audit import WebsiteCheckExecution, WebsiteCheckExecutions
from app.schemas.opportunity_models import OpportunityModelSelection
from app.schemas.social_audit import SocialAuditResult


def create_research_request(
    db: Session,
    company_id: UUID,
    user_id: UUID,
    objective: dict | None = None,
    model_selection: OpportunityModelSelection | None = None,
) -> ResearchRequest:
    research_request = ResearchRequest(
        company_id=company_id,
        user_id=user_id,
        status=ResearchStatus.PENDING,
        objective=objective,
        opportunity_model_selection=(
            model_selection.model_dump(mode="json") if model_selection else None
        ),
    )
    db.add(research_request)
    db.commit()
    db.refresh(research_request)
    return research_request


def save_specialist_output(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    namespace: str,
    output: dict,
) -> ResearchRequest:
    if research_request.user_id != expected_user_id:
        raise ValueError("Research request is not available to this user.")
    research_request.specialist_outputs = {
        **(research_request.specialist_outputs or {}),
        namespace: output,
    }
    db.commit()
    db.refresh(research_request)
    return research_request


def save_website_check_execution(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    capability: Literal["mobile_performance", "conversion_paths"],
    execution: WebsiteCheckExecution,
) -> ResearchRequest:
    if research_request.user_id != expected_user_id:
        raise ValueError("Research request is not available to this user.")
    states = WebsiteCheckExecutions.model_validate(research_request.website_check_states or {})
    states = states.model_copy(update={capability: execution})
    research_request.website_check_states = states.model_dump(mode="json")
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


def save_evidence_gate_result(
    db: Session,
    request_id: UUID,
    result: EvidenceGateResponse,
) -> ResearchRequest | None:
    request = get_research_request_by_id(db, request_id)
    if request is None:
        return None
    request.evidence_gate_state = result.state
    request.evidence_gate_reason = result.reason
    request.evidence_gated_at = result.evaluated_at
    db.commit()
    db.refresh(request)
    return request


def save_website_audit_result(
    db: Session,
    request_id: UUID,
    result: WebsiteAuditResult,
) -> ResearchRequest | None:
    request = get_research_request_by_id(db, request_id)
    if request is None:
        return None
    request.website_audit_state = result.state
    request.website_audit_reason = result.reason
    request.website_audited_at = result.audited_at
    db.commit()
    db.refresh(request)
    return request


def save_social_audit_result(
    db: Session,
    request_id: UUID,
    result: SocialAuditResult,
) -> ResearchRequest | None:
    request = get_research_request_by_id(db, request_id)
    if request is None:
        return None
    request.social_audit_state = result.state
    request.social_audit_reason = result.reason
    request.social_audited_at = result.audited_at
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
