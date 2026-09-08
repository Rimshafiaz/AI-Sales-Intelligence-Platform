from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportSummary(BaseModel):
    id: UUID
    research_request_id: UUID
    company_id: UUID
    company_name: str
    report_kind: str
    opportunity_score: int | None = None
    contact_recommendation: str | None = None
    review_status: str
    generated_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    total: int
    page: int
    page_size: int
