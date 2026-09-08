import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.campaign_candidate_selection import CampaignCandidateSelection
    from app.models.user import User
    from app.models.research_request import ResearchRequest


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "identity_key",
            name="uq_companies_user_identity_key",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    website: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    identity_key: Mapped[str | None] = mapped_column(
        String(400),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone = True),
        server_default = func.now(),
        nullable = False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone = True),
        server_default = func.now(),
        onupdate = func.now(),
        nullable = False
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="companies",
    )
    research_requests: Mapped[list["ResearchRequest"]] = relationship(
        "ResearchRequest",
        back_populates="company",
    )
    campaign_candidate_selections: Mapped[list["CampaignCandidateSelection"]] = (
        relationship(
            "CampaignCandidateSelection",
            back_populates="company",
        )
    )
