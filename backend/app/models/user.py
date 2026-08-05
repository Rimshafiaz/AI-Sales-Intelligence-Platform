import uuid
from datetime import datetime
from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, DateTime, func

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid = True),
        primary_key = True,
        nullable = False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable = True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable = False,
        unique = True,
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