import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.campaign_candidate_selection import CampaignCandidateSelection


class CampaignRunStatus(str, Enum):
    COMPLETED = "completed"


class CampaignRun(Base):
    __tablename__ = "campaign_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[CampaignRunStatus] = mapped_column(
        SAEnum(
            CampaignRunStatus,
            name="campaign_run_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=CampaignRunStatus.COMPLETED,
        server_default=CampaignRunStatus.COMPLETED.value,
    )
    criteria_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_selection_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    discovered_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="runs")
    selections: Mapped[list["CampaignCandidateSelection"]] = relationship(
        "CampaignCandidateSelection",
        back_populates="campaign_run",
    )
