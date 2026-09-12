import uuid
from dataclasses import dataclass

from fastapi import Depends,HTTPException,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.services.users import get_or_create_user

from app.api.dependencies.auth import get_verified_claims


@dataclass(frozen=True)
class AuthenticatedIdentity:
    id: uuid.UUID
    email: str


def get_authenticated_identity(
    claims: dict = Depends(get_verified_claims),
) -> AuthenticatedIdentity:
    try:
        user_id = claims.get("sub")
        email = claims.get("email")
        if not user_id or not isinstance(email, str) or not email:
            raise ValueError("Missing user ID or email in token")
        return AuthenticatedIdentity(id=uuid.UUID(user_id), email=email)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication claim",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_user(
    claims: dict = Depends(get_verified_claims),
    db: Session = Depends(get_db)) ->User:
    try:
        return get_or_create_user(db,claims)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication claim",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
