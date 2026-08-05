import jwt
from jwt import PyJWKClient

from app.core.config import settings


def verify_supabase_token(token: str) -> dict:
    jwks_client = PyJWKClient(settings.supabase_jwks_url)

    signing_key = jwks_client.get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256"],
        issuer=settings.supabase_jwt_issuer,
        audience=settings.supabase_jwt_audience,
        leeway=10,
    )

    return {
        "sub": claims["sub"],
        "email": claims.get("email"),
        "role": claims.get("role"),
    }