import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.research_request import ResearchRequest


class ResearchSocialObservation(Base):
    __tablename__ = "research_social_observations"
    __table_args__ = (
        UniqueConstraint(
            "research_request_id",
            "profile_identity_key",
            name="uq_research_social_observation_request_profile",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid.uuid4,
    )
    research_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_requests.id"),
        nullable=False,
        index=True,
    )
    profile_identity_key: Mapped[str] = mapped_column(String(400), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    provider_profile_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_private: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latest_public_post_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    recent_public_post_dates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    research_request: Mapped["ResearchRequest"] = relationship(
        "ResearchRequest",
        back_populates="social_observations",
    )
