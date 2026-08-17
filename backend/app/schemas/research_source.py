from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchSourceResponse(BaseModel):
    id: UUID
    url: str
    title: str | None
    excerpt: str | None
    source_type: str
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)
