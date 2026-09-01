from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.schemas.research_source import ResearchSourceResponse


class ResearchReportResponse(BaseModel):
    id: UUID
    research_request_id: UUID
    company_id: UUID
    opportunity_score: int
    contact_recommendation: str
    review_status: str
    approved_at: datetime | None = None
    report_data: dict[str, Any]
    generated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportDetailResponse(BaseModel):
    report: ResearchReportResponse
    sources: list[ResearchSourceResponse]
