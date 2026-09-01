from fastapi import APIRouter, Depends
from app.schemas.user import UserResponse
from app.api.dependencies.current_user import get_current_user
from app.models.user import User
router = APIRouter(tags=["Users"])

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Show the authenticated user's profile",
    responses={401: {"description": "Missing, invalid, or expired token"}},
)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


