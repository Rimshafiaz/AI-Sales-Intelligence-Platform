import uuid
from sqlalchemy.orm import Session
from app.models.user import User

def get_or_create_user(
    db:Session,
    claims: dict)->User:
    user_id=claims.get("sub")
    email=claims.get("email")

    if not user_id or not email:
        raise ValueError("Missing user ID or email in token")
    user_id = uuid.UUID(user_id)
    user = db.get(User,user_id)
    if user:
        return user

    user = User(
        id=user_id,
        email=email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
    
