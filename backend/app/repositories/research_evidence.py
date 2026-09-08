from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest
from app.models.user import User
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceType


def upsert_mobile_performance_evidence(
    db: Session,
    research_request_id: UUID,
    supporting_value: str,
    numeric_value: float,
    source_url: str,
    retrieved_at: datetime,
    captured_at: datetime,
) -> ResearchEvidence:
    statement = select(ResearchEvidence).where(
        ResearchEvidence.research_request_id == research_request_id,
        ResearchEvidence.signal_type == EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED.value,
        ResearchEvidence.source_provider == "pagespeed_insights",
    )
    evidence = db.scalar(statement)
    if evidence is None:
        evidence = ResearchEvidence(
            research_request_id=research_request_id,
            signal_type=EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED.value,
            evidence_type=EvidenceType.OBSERVED.value,
            supporting_value=supporting_value,
            numeric_value=numeric_value,
            source_provider="pagespeed_insights",
            source_url=source_url,
            retrieved_at=retrieved_at,
            captured_at=captured_at,
        )
        db.add(evidence)
        return evidence

    evidence.supporting_value = supporting_value
    evidence.numeric_value = numeric_value
    evidence.source_url = source_url
    evidence.retrieved_at = retrieved_at
    evidence.captured_at = captured_at
    return evidence


def list_research_evidence_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
) -> list[ResearchEvidence]:
    statement = (
        select(ResearchEvidence)
        .join(ResearchRequest, ResearchEvidence.research_request_id == ResearchRequest.id)
        .where(
            ResearchEvidence.research_request_id == research_request_id,
            ResearchRequest.user_id == user_id,
        )
        .order_by(ResearchEvidence.captured_at.desc())
    )
    return list(db.scalars(statement))
