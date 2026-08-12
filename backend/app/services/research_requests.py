from sqlalchemy.orm import Session
from uuid import UUID
from app.repositories.research_requests import (
    create_research_request,
    get_research_request_for_user as get_research_request_for_user_repository,
)
from app.repositories.companies import get_company_by_id
from app.models.research_request import ResearchRequest
from app.models.user import User


def create_research_request_for_company(
    db: Session,
    company_id: UUID,
    current_user: User,
) -> ResearchRequest | None:
    company=get_company_by_id(db=db,company_id=company_id,user_id=current_user.id)
    if not company:
        return None
    request=create_research_request(
        db=db,
        company_id=company_id,
        user_id=current_user.id,
    )
    return request


def get_research_request_for_user(
    db: Session,
    request_id: UUID,
    current_user: User,
) -> ResearchRequest | None:
    return get_research_request_for_user_repository(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
    )
