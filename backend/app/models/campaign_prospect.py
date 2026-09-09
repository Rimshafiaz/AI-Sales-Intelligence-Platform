import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.campaign_run import CampaignRun
    from app.models.outreach_attempt import OutreachAttempt


class CampaignProspectState(str, Enum):
    SAVED = "saved"
    NEEDS_RESEARCH = "needs_research"
    READY_FOR_OUTREACH = "ready_for_outreach"
    CONTACTED = "contacted"
    CLOSED = "closed"


class CampaignProspectNextAction(str, Enum):
    RESEARCH_PROSPECT = "research_prospect"
    COLLECT_EVIDENCE = "collect_evidence"
    PREPARE_OUTREACH = "prepare_outreach"
    NO_ACTION = "no_action"


class CampaignProspect(Base):
    __tablename__ = "campaign_prospects"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "source_identity_key",
            name="uq_campaign_prospect_campaign_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    campaign_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_runs.id"), nullable=False, index=True
    )
    source_identity_key: Mapped[str] = mapped_column(String(400), nullable=False)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    shortlist_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    workflow_state: Mapped[CampaignProspectState] = mapped_column(
        SAEnum(
            CampaignProspectState,
            name="campaign_prospect_state",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=CampaignProspectState.SAVED,
        server_default=CampaignProspectState.SAVED.value,
        index=True,
    )
    next_action: Mapped[CampaignProspectNextAction] = mapped_column(
        SAEnum(
            CampaignProspectNextAction,
            name="campaign_prospect_next_action",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=CampaignProspectNextAction.RESEARCH_PROSPECT,
        server_default=CampaignProspectNextAction.RESEARCH_PROSPECT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="prospects")
    campaign_run: Mapped["CampaignRun"] = relationship("CampaignRun")
    outreach_attempts: Mapped[list["OutreachAttempt"]] = relationship(
        "OutreachAttempt",
        back_populates="campaign_prospect",
    )
