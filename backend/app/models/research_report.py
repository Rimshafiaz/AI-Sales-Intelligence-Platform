import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.research_request import ResearchRequest
    from app.models.user import User


class ReportReviewStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class ResearchReport(Base):
    __tablename__ = "research_reports"

    __table_args__ = (
        Index(
            "ix_research_reports_user_generated_at",
            "user_id",
            "generated_at",
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
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    report_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    opportunity_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    contact_recommendation: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    review_status: Mapped[ReportReviewStatus] = mapped_column(
        SAEnum(
            ReportReviewStatus,
            name="report_review_status",
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=ReportReviewStatus.DRAFT,
        server_default=ReportReviewStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
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
    )
    company: Mapped["Company"] = relationship(
        "Company",
    )
    user: Mapped["User"] = relationship(
        "User",
    )
