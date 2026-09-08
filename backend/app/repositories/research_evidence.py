from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest
from app.models.user import User
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceSource, EvidenceType


def upsert_research_evidence(
    db: Session,
    research_request_id: UUID,
    signal_type: EvidenceSignalType,
    evidence_type: EvidenceType,
    supporting_value: str,
    numeric_value: float | None,
    source: EvidenceSource,
    source_identity_key: str,
    captured_at: datetime,
) -> ResearchEvidence:
    statement = select(ResearchEvidence).where(
        ResearchEvidence.research_request_id == research_request_id,
        ResearchEvidence.signal_type == signal_type.value,
        ResearchEvidence.source_identity_key == source_identity_key,
    )
    evidence = db.scalar(statement)
    if evidence is None:
        evidence = ResearchEvidence(
            research_request_id=research_request_id,
            signal_type=signal_type.value,
            evidence_type=evidence_type.value,
            supporting_value=supporting_value,
            numeric_value=numeric_value,
            source_provider=source.provider,
            source_identity_key=source_identity_key,
            source_record_id=source.provider_record_id,
            source_url=str(source.source_url),
            retrieved_at=source.retrieved_at,
            captured_at=captured_at,
        )
        db.add(evidence)
        return evidence

    evidence.evidence_type = evidence_type.value
    evidence.supporting_value = supporting_value
    evidence.numeric_value = numeric_value
    evidence.source_provider = source.provider
    evidence.source_record_id = source.provider_record_id
    evidence.source_url = str(source.source_url)
    evidence.retrieved_at = source.retrieved_at
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
