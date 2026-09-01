from fastapi import APIRouter, Depends, HTTPException, status,Response
from app.schemas.company import CompanyResponse,CompanyCreate
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.companies import create_company,list_companies_for_user,get_company_by_id,delete_company_for_user
from app.api.dependencies.current_user import get_current_user
from app.models.user import User
import uuid


router = APIRouter(prefix="/companies",tags=["Companies"])

@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company to research",
    responses={422: {"description": "Blank name or malformed website"}},
)
async def create_company_endpoint(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = create_company(
        current_user=current_user,
        company_data=company_data,
        db=db,
    )
    return company

@router.get(
    "",
    response_model=list[CompanyResponse],
    summary="List the current user's companies",
)
async def list_companies_endpoint(
    db:Session=Depends(get_db),
    current_user:User=Depends(get_current_user),):
    companies = list_companies_for_user(db,current_user.id)
    return companies

@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Show one owned company",
    responses={404: {"description": "Company unknown or owned by another user"}},
)
async def get_company_endpoint(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = get_company_by_id(db,company_id,current_user.id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company

@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unused company",
    responses={
        404: {"description": "Company unknown or owned by another user"},
        409: {"description": "Company still has reports (retention policy)"},
    },
)
async def delete_company_endpoint(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
)->Response:
    try:
        company = delete_company_for_user(db,company_id,current_user.id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)