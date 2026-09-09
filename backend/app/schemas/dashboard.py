from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.outreach_attempt import OutreachChannel


DashboardActionType = Literal[
    "research_prospect",
    "collect_evidence",
    "prepare_outreach",
    "approve_outreach",
    "send_linkedin",
    "awaiting_gmail",
    "follow_up",
]

DashboardActivityType = Literal[
    "prospect_saved",
    "outreach_draft_created",
    "outreach_approved",
    "outreach_sent",
    "outreach_replied",
    "outreach_closed",
]


class PipelineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospects_saved: int
    needs_research: int
    ready_for_outreach: int
    contacted: int
    replied: int
    interested: int


class DashboardAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: DashboardActionType
    campaign_id: UUID
    campaign_title: str
    prospect_id: UUID
    prospect_name: str
    outreach_attempt_id: UUID | None = None
    channel: OutreachChannel | None = None
    reason: str
    reference_at: datetime | None = None


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: DashboardActivityType
    campaign_title: str
    prospect_id: UUID
    prospect_name: str
    channel: OutreachChannel | None = None
    occurred_at: datetime


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineSummary
    needs_attention: list[DashboardAction]
    follow_ups_due: list[DashboardAction]
    recent_activity: list[ActivityEvent]
    next_best_action: DashboardAction | None
