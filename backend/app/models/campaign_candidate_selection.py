import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.campaign_run import CampaignRun
    from app.models.company import Company
    from app.models.research_request import ResearchRequest


class CampaignCandidateSelection(Base):
    __tablename__ = "campaign_candidate_selections"
    __table_args__ = (
        UniqueConstraint(
            "campaign_run_id",
            "source_identity_key",
            name="uq_campaign_run_source_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid.uuid4,
    )
    campaign_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )
    source_identity_key: Mapped[str] = mapped_column(String(400), nullable=False)
    candidate_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    shortlist_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    campaign_run: Mapped["CampaignRun"] = relationship(
        "CampaignRun",
        back_populates="selections",
    )
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="campaign_candidate_selections",
    )
    research_request: Mapped["ResearchRequest | None"] = relationship(
        "ResearchRequest",
        back_populates="campaign_candidate_selection",
        uselist=False,
    )
