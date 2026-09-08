from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.evidence_gate import SourceAdmissionState


class ResearchSourceResponse(BaseModel):
    id: UUID
    url: str
    title: str | None
    excerpt: str | None
    source_type: str
    retrieved_at: datetime
    admission_state: SourceAdmissionState
    admission_reason: str | None

    model_config = ConfigDict(from_attributes=True)
