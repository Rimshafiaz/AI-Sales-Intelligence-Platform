from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class IndustrySummary(BaseModel):
    industry: str
    report_count: int


class ActivityEvent(BaseModel):
    event_type: Literal[
        "research_requested",
        "research_completed",
        "research_failed",
        "report_generated",
        "report_approved",
    ]
    company_name: str
    status: str | None
    occurred_at: datetime


class DashboardSummaryResponse(BaseModel):
    reports_generated: int
    companies_researched: int
    industries_researched: int
    most_researched_industries: list[IndustrySummary]
    average_opportunity_score: float | None
    recent_activity: list[ActivityEvent]
