from pydantic.functional_validators import field_validator
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from datetime import datetime
from pydantic import ConfigDict

class CompanyCreate(BaseModel):
    name: str = Field(...,max_length=255)
    website: HttpUrl

    @field_validator("name",mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Company name cannot be blank.")

        return value

    @field_validator("website")
    @classmethod
    def normalize_website(cls, value: HttpUrl) -> str:
        website = str(value).rstrip("/")
        return website

class CompanyResponse(BaseModel):
    id: UUID
    name: str
    website: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
