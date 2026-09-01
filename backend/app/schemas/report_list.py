from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportSummary(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    opportunity_score: int
    contact_recommendation: str
    review_status: str
    generated_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    total: int
    page: int
    page_size: int
