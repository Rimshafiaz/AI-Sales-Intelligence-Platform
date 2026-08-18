from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class CompanyDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industry: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    company_size: str | None = Field(default=None, max_length=100)
    keywords: str | None = Field(default=None, max_length=255)

    @field_validator("industry", "region", "company_size", "keywords", mode="before")
    @classmethod
    def normalize_criteria(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None

        return value

    @model_validator(mode="after")
    def require_search_criteria(self) -> Self:
        if not any(
            [self.industry, self.region, self.company_size, self.keywords]
        ):
            raise ValueError(
                "Provide at least one discovery criterion: industry, region, "
                "company_size, or keywords."
            )

        return self


class DiscoveredCompanyCandidate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=1_000)
    match_explanation: str = Field(min_length=1, max_length=1_000)
    supporting_source_urls: list[HttpUrl] = Field(min_length=1, max_length=5)

    @field_validator(
        "company_name",
        "industry",
        "short_description",
        "match_explanation",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None

        return value


class CompanyDiscoveryResponse(BaseModel):
    candidates: list[DiscoveredCompanyCandidate] = Field(max_length=5)
