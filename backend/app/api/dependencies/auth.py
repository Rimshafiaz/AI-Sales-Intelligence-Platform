from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from jwt import InvalidTokenError,PyJWKClientError
from app.core.security import verify_supabase_token

security = HTTPBearer()

async def get_verified_claims(credentials: HTTPAuthorizationCredentials = Depends(security))->dict:
    try:
        token = credentials.credentials
        claims = verify_supabase_token(token)
        return claims
    except (InvalidTokenError,PyJWKClientError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

