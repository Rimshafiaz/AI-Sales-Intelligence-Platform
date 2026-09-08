from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.opportunity_qualification import OpportunityQualification
from app.models.research_request import ResearchRequest
from app.schemas.opportunity_models import OpportunityModelId
from app.schemas.opportunity_qualification import OpportunityQualificationState


def upsert_opportunity_qualification(
    db: Session,
    research_request_id: UUID,
    opportunity_model_id: OpportunityModelId,
    state: OpportunityQualificationState,
    reason: str,
    supporting_evidence_keys: list[str],
    evaluated_at: datetime,
) -> OpportunityQualification:
    statement = select(OpportunityQualification).where(
        OpportunityQualification.research_request_id == research_request_id,
        OpportunityQualification.opportunity_model_id == opportunity_model_id,
    )
    qualification = db.scalar(statement)
    if qualification is None:
        qualification = OpportunityQualification(
            research_request_id=research_request_id,
            opportunity_model_id=opportunity_model_id,
            state=state.value,
            reason=reason,
            supporting_evidence_keys=supporting_evidence_keys,
            evaluated_at=evaluated_at,
        )
        db.add(qualification)
        return qualification

    qualification.state = state.value
    qualification.reason = reason
    qualification.supporting_evidence_keys = supporting_evidence_keys
    qualification.evaluated_at = evaluated_at
    return qualification


def list_opportunity_qualifications_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
    include_not_eligible: bool,
) -> list[OpportunityQualification]:
    statement = (
        select(OpportunityQualification)
        .join(ResearchRequest)
        .where(
            OpportunityQualification.research_request_id == research_request_id,
            ResearchRequest.user_id == user_id,
        )
        .order_by(
            OpportunityQualification.evaluated_at.desc(),
            OpportunityQualification.opportunity_model_id.asc(),
        )
    )
    if not include_not_eligible:
        statement = statement.where(
            OpportunityQualification.state != OpportunityQualificationState.NOT_ELIGIBLE.value
        )
    return list(db.scalars(statement))
