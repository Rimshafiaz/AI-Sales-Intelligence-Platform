from app.repositories.companies import create_company as create_company_repository
from app.repositories.companies import get_company_by_id as get_company_by_id_repository
from app.repositories.companies import list_companies_for_user as list_companies_for_user_repository, delete_company
from app.schemas.company import CompanyCreate
from app.models.user import User
from app.models.company import Company
from sqlalchemy.orm import Session
import uuid


def create_company(
    current_user: User,
    company_data: CompanyCreate,
    db: Session,
) -> Company:
    return create_company_repository(
        db=db,
        user_id=current_user.id,
        name=company_data.name,
        website=str(company_data.website) if company_data.website else None,
    )

def get_company_by_id(db:Session,company_id:uuid.UUID,user_id:uuid.UUID)->Company | None:
    return get_company_by_id_repository(db, company_id, user_id)

def list_companies_for_user(db:Session,user_id:uuid.UUID)->list[Company]:
    return list_companies_for_user_repository(db, user_id)

def delete_company_for_user(db:Session,company_id:uuid.UUID,user_id:uuid.UUID)->bool:
    company = get_company_by_id(db,company_id,user_id)
    if company is None:
        return False
    delete_company(db,company)
    return True
    