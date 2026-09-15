from uuid import UUID

from sqlalchemy.orm import Session

from app.models.research_request import ResearchRequest
from app.repositories.research_requests import save_specialist_output
from app.schemas.agent_outputs import WebsiteResearchOutput


def persist_website_research_output(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    output: WebsiteResearchOutput | dict,
) -> ResearchRequest:
    validated = WebsiteResearchOutput.model_validate(output)
    return save_specialist_output(
        db,
        research_request,
        expected_user_id,
        "website",
        validated.model_dump(mode="json"),
    )
