import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.schemas.evidence_gate import SourceAdmissionState


if TYPE_CHECKING:
    from app.models.research_request import ResearchRequest


class ResearchSource(Base):
    __tablename__ = "research_sources"

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
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    excerpt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    admission_state: Mapped[SourceAdmissionState] = mapped_column(
        String(30),
        default=SourceAdmissionState.PENDING,
        server_default=SourceAdmissionState.PENDING.value,
        nullable=False,
        index=True,
    )
    admission_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    research_request: Mapped["ResearchRequest"] = relationship(
        "ResearchRequest",
        back_populates="sources",
    )
