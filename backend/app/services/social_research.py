from uuid import UUID

from sqlalchemy.orm import Session

from app.models.research_request import ResearchRequest
from app.repositories.research_requests import save_specialist_output
from app.schemas.agent_outputs import SocialResearchOutput


def persist_social_research_output(
    db: Session,
    research_request: ResearchRequest,
    expected_user_id: UUID,
    output: SocialResearchOutput | dict,
    canonical_evidence_keys: set[str],
) -> ResearchRequest:
    validated = SocialResearchOutput.model_validate(output)
    if any(
        not set(finding.evidence_keys) <= canonical_evidence_keys
        for finding in validated.findings
    ):
        raise ValueError("Social research output cited unavailable evidence.")
    return save_specialist_output(
        db,
        research_request,
        expected_user_id,
        "social",
        validated.model_dump(mode="json"),
    )
