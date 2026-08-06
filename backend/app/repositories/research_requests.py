from sqlalchemy.orm import Session
from uuid import UUID
from app.models.research_request import ResearchRequest, ResearchStatus


def create_research_request(
    db: Session,
    company_id: UUID,
    user_id: UUID,
) -> ResearchRequest:
    research_request = ResearchRequest(
        company_id=company_id,
        user_id=user_id,
        status=ResearchStatus.PENDING,
    )
    db.add(research_request)
    db.commit()
    db.refresh(research_request)
    return research_request
