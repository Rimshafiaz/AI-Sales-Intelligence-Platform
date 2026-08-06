from pydantic import ConfigDict
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ResearchRequestResponse(BaseModel):
    id: UUID
    company_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)
    
    
    