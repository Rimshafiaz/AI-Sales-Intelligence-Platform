from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)


class CompanyDiscoveryRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "industry": "fintech",
                    "region": "San Francisco",
                    "company_size": "50-200",
                    "keywords": "payment infrastructure",
                }
            ]
        },
    )

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

    @field_serializer("website")
    def serialize_website(self, value: HttpUrl | None) -> str | None:
        return str(value).rstrip("/") if value is not None else None

    @field_serializer("supporting_source_urls")
    def serialize_supporting_source_urls(self, value: list[HttpUrl]) -> list[str]:
        return [str(url).rstrip("/") for url in value]

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


class DiscoveredCompanyCandidateOutput(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=1_000)
    match_explanation: str = Field(min_length=1, max_length=1_000)
    supporting_source_urls: list[str] = Field(default_factory=list, max_length=5)

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


class CompanyDiscoveryTaskOutput(BaseModel):
    candidates: list[DiscoveredCompanyCandidateOutput] = Field(
        default_factory=list,
        max_length=5,
    )


def company_discovery_response_from_task_output(
    output: CompanyDiscoveryTaskOutput,
) -> CompanyDiscoveryResponse:
    validated_candidates: list[DiscoveredCompanyCandidate] = []

    for raw_candidate in output.candidates:
        try:
            validated_candidates.append(
                DiscoveredCompanyCandidate(
                    company_name=raw_candidate.company_name,
                    website=raw_candidate.website,
                    industry=raw_candidate.industry,
                    short_description=raw_candidate.short_description,
                    match_explanation=raw_candidate.match_explanation,
                    supporting_source_urls=raw_candidate.supporting_source_urls,
                )
            )
        except ValidationError:
            continue

    return CompanyDiscoveryResponse(candidates=validated_candidates)
