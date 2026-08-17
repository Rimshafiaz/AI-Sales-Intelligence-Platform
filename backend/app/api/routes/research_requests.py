from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.research_request import ResearchRequestResponse
from app.services.research_runner import run_research
from app.services.research_requests import (
    create_research_request_for_company,
    get_research_request_for_user,
)


router = APIRouter(tags=["Research Requests"])


@router.post(
    "/companies/{company_id}/research-requests",
    response_model=ResearchRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_research_request_endpoint(
    company_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = create_research_request_for_company(
        db=db,
        company_id=company_id,
        current_user=current_user,
    )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
    )
    background_tasks.add_task(
        run_research,
        research_request.id,
    )

    return research_request


@router.get(
    "/research-requests/{request_id}",
    response_model=ResearchRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def get_research_request_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    research_request = get_research_request_for_user(
        db=db,
        request_id=request_id,
        current_user=current_user,
    )

    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research request not found",
        )

    return research_request
