import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRequest(Base):
    __tablename__ = "research_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
         ForeignKey("companies.id"),
        nullable=False,
        index = True,
    )
    user_id: Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index = True,
    )
    status: Mapped[ResearchStatus] = mapped_column(
        SAEnum(
            ResearchStatus,
            name="research_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=ResearchStatus.PENDING,
        server_default=ResearchStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    created_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    started_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message:Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    company:Mapped["Company"] = relationship(
        "Company",
        back_populates="research_requests",
    )
    user:Mapped["User"] = relationship(
        "User",
        back_populates="research_requests",
    )
