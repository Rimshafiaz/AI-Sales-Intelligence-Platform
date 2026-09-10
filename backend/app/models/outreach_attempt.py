import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.campaign_prospect import CampaignProspect
    from app.models.research_report import ResearchReport
    from app.models.user import User


class OutreachChannel(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    CONTACT_FORM = "contact_form"


class OutreachSendMethod(str, Enum):
    GMAIL = "gmail"
    MANUAL = "manual"


class OutreachStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    REPLIED = "replied"
    CLOSED = "closed"


class OutreachOutcome(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    BOUNCED = "bounced"
    NO_RESPONSE = "no_response"


class OutreachAttempt(Base):
    __tablename__ = "outreach_attempts"
    __table_args__ = (
        Index(
            "uq_outreach_attempt_active_contact",
            "campaign_prospect_id",
            "research_report_id",
            "channel",
            "recipient",
            unique=True,
            postgresql_where=text("status IN ('draft', 'approved', 'sending')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_prospects.id"), nullable=False, index=True
    )
    research_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_reports.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    channel: Mapped[OutreachChannel] = mapped_column(
        SAEnum(
            OutreachChannel,
            name="outreach_channel",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    send_method: Mapped[OutreachSendMethod] = mapped_column(
        SAEnum(
            OutreachSendMethod,
            name="outreach_send_method",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(String(2048), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    offering: Mapped[str] = mapped_column(String(300), nullable=False)
    grounding_evidence_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    contact_source_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    edited_by_user: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[OutreachStatus] = mapped_column(
        SAEnum(
            OutreachStatus,
            name="outreach_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=OutreachStatus.DRAFT,
        server_default=OutreachStatus.DRAFT.value,
        index=True,
    )
    outcome: Mapped[OutreachOutcome | None] = mapped_column(
        SAEnum(
            OutreachOutcome,
            name="outreach_outcome",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_reply_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    campaign_prospect: Mapped["CampaignProspect"] = relationship(
        "CampaignProspect", back_populates="outreach_attempts"
    )
    research_report: Mapped["ResearchReport"] = relationship("ResearchReport")
    user: Mapped["User"] = relationship("User")
