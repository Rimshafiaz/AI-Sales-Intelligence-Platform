from sqlalchemy.orm import Session
from app.models.company import Company
import uuid
from sqlalchemy import select
from uuid import UUID

def create_company(db: Session,user_id:uuid.UUID,name:str,website:str | None = None) -> Company:
    company = Company(user_id=user_id,name=name,website=website)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company

def list_companies_for_user(
    db: Session,
    user_id: uuid.UUID,
) -> list[Company]:
    statement = (
        select(Company)
        .where(Company.user_id == user_id)
        .order_by(Company.created_at.desc())
    )
    return db.scalars(statement).all()

def get_company_by_id(
    db: Session,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Company | None:
    statement = select(Company).where(
        Company.id == company_id,
        Company.user_id == user_id,
    )
    return db.scalar(statement)
def update_company_website(db: Session, company_id: UUID, website: str) -> Company | None:
    statement = select(Company).where(
        Company.id == company_id,
    )
    company = db.scalar(statement)
    if company is None:
        return None
    if company.website is not None:
        return company
    company.website = website
    db.commit()
    db.refresh(company)
    return company

def delete_company(db: Session,company: Company):
    db.delete(company)
    db.commit()

