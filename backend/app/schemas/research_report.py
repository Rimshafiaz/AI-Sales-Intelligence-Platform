from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ResearchReportResponse(BaseModel):
    id: UUID
    research_request_id: UUID
    company_id: UUID
    opportunity_score: int | None
    contact_recommendation: str | None
    report_data: dict[str, Any]
    generated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
