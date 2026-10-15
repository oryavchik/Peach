"""Cognito verification without importing API sessions or database models."""

from functools import lru_cache

import jwt

from app.config import get_settings


@lru_cache
def jwks_client(issuer: str):
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=3)


def verify_cognito_token(authorization: str) -> str:
    settings = get_settings()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not settings.auth_configured:
        raise ValueError("Sign in before parsing an agenda")
    try:
        if settings.cognito_jwks:
            keys = jwt.PyJWKSet.from_json(settings.cognito_jwks).keys
            kid = jwt.get_unverified_header(token).get("kid")
            key = next(key.key for key in keys if key.key_id == kid)
        else:
            key = jwks_client(settings.cognito_issuer).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
        if (
            claims.get("token_use") != "id"
            or not isinstance(claims["sub"], str)
            or not claims["sub"]
        ):
            raise ValueError("Invalid token")
        return claims["sub"]
    except Exception:
        raise ValueError("Your session is invalid or expired. Sign in again.") from None
