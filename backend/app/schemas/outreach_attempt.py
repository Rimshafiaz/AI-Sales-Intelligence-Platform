from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.outreach_attempt import (
    OutreachChannel,
    OutreachOutcome,
    OutreachSendMethod,
    OutreachStatus,
)


class OutreachAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_report_id: UUID
    channel: OutreachChannel
    recipient: str = Field(min_length=3, max_length=2048)


class OutreachDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, min_length=3, max_length=255)
    body: str = Field(min_length=3, max_length=5000)

    @field_validator("subject", "body", mode="before")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class OutreachOutcomeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: OutreachOutcome
    replied: bool = False


class OutreachAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_prospect_id: UUID
    research_report_id: UUID
    channel: OutreachChannel
    send_method: OutreachSendMethod
    recipient: str
    subject: str | None
    body: str
    offering: str
    grounding_evidence_keys: list[str]
    contact_source_keys: list[str]
    edited_by_user: bool
    status: OutreachStatus
    outcome: OutreachOutcome | None
    provider_message_id: str | None
    provider_thread_id: str | None
    failure_reason: str | None
    approved_at: datetime | None
    sent_at: datetime | None
    replied_at: datetime | None
    outcome_recorded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OutreachDraftOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_report_id: UUID
    channel: OutreachChannel
    recipient: str
    subject: str | None
    body: str
