from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
from app.api.dependencies.current_user import get_current_user
from app.schemas.research_request import ResearchRequestResponse
from app.services.research_requests import create_research_request_for_company
from app.db.session import get_db
from app.models.user import User
from uuid import UUID


router = APIRouter(prefix="/companies/{company_id}",tags=["research-requests"])



@router.post("/research-requests",response_model=ResearchRequestResponse,status_code=status.HTTP_202_ACCEPTED)
async def create_research_request_endpoint(company_id:UUID,db:Session= Depends(get_db),current_user:User = Depends(get_current_user)):
    research_request = create_research_request_for_company(                                                                             
          db=db, 
          company_id=company_id,
          current_user=current_user                                                                                                                         
      )
    if research_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return research_request