from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.opportunity_models import EvidenceSignalType, EvidenceType


class ResearchEvidenceResponse(BaseModel):
    id: UUID
    research_request_id: UUID
    signal_type: EvidenceSignalType
    evidence_type: EvidenceType
    supporting_value: str
    numeric_value: float | None = None
    source_provider: str
    source_identity_key: str
    source_record_id: str | None = None
    source_url: str
    retrieved_at: datetime
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)
