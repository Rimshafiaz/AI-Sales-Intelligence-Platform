from pydantic.functional_validators import field_validator
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from datetime import datetime
from pydantic import ConfigDict

class CompanyCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Stripe", "website": "https://stripe.com"},
                {"name": "Some Startup Inc."},
            ]
        }
    )

    name: str = Field(..., max_length=255, description="Company display name; website is optional and can be resolved during research.")
    website: HttpUrl | None = None

    @field_validator("name",mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Company name cannot be blank.")

        return value

    @field_validator("website",mode="after")
    @classmethod
    def normalize_website(cls, value: HttpUrl | None) -> str | None:
        if value is None:
            return None
        website = str(value).rstrip("/")
        return website

class CompanyResponse(BaseModel):
    id: UUID
    name: str
    website: str | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
