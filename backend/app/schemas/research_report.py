from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.research_source import ResearchSourceResponse


MAX_STRATEGY_LENGTH = 1_000
MAX_OUTREACH_EMAIL_LENGTH = 5_000
MAX_OUTREACH_LINKEDIN_LENGTH = 2_000
MAX_DECISION_MAKER_ROLE_LENGTH = 255
MAX_REVIEW_NOTE_LENGTH = 2_000


class ReportEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str | None = Field(default=None, max_length=MAX_STRATEGY_LENGTH)
    sales_angle: str | None = Field(default=None, max_length=MAX_STRATEGY_LENGTH)
    value_proposition: str | None = Field(default=None, max_length=MAX_STRATEGY_LENGTH)
    suggested_decision_makers: list[str] | None = Field(
        default=None,
        max_length=5,
    )
    cold_email: str | None = Field(default=None, max_length=MAX_OUTREACH_EMAIL_LENGTH)
    linkedin_message: str | None = Field(
        default=None,
        max_length=MAX_OUTREACH_LINKEDIN_LENGTH,
    )
    review_note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_LENGTH)

    @field_validator(
        "strategy",
        "sales_angle",
        "value_proposition",
        "cold_email",
        "linkedin_message",
        "review_note",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator("suggested_decision_makers", mode="before")
    @classmethod
    def strip_decision_maker_roles(cls, value: object) -> object:
        if not isinstance(value, list):
            return value

        stripped_roles = []
        for role in value:
            if not isinstance(role, str) or not role.strip():
                raise ValueError("Decision-maker roles cannot be blank.")
            stripped_roles.append(role.strip())

        return stripped_roles


class ResearchReportResponse(BaseModel):
    id: UUID
    research_request_id: UUID
    company_id: UUID
    opportunity_score: int
    contact_recommendation: str
    review_status: str
    approved_at: datetime | None = None
    review_note: str | None = None
    report_data: dict[str, Any]
    generated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportDetailResponse(BaseModel):
    report: ResearchReportResponse
    sources: list[ResearchSourceResponse]
