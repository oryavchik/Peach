from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()

    if not settings.auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    try:
        jwks_client = jwt.PyJWKSet.from_json(settings.cognito_jwks)
        signing_key = None

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        for key in jwks_client.keys:
            if key.key_id == kid:
                signing_key = key.key
                break

        if signing_key is None:
            raise _unauthorized()

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
        )

        if payload.get("token_use") != "id":
            raise _unauthorized()

        return payload

    except HTTPException:
        raise
    except Exception:
        raise _unauthorized() from None


async def current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")

    claims = _decode_token(credentials.credentials)

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise _unauthorized()

    result = await session.execute(
        select(User).where(User.cognito_sub == sub)
    )
    user = result.scalar_one_or_none()

    email = claims.get("email")
    if not isinstance(email, str):
        email = ""

    name = claims.get("name")
    if not isinstance(name, str) or not name:
        name = email or "User"

    if user is None:
        user = User(
            cognito_sub=sub,
            email=email,
            name=name,
        )
        session.add(user)
        await session.flush()
    else:
        changed = False

        if email and user.email != email:
            user.email = email
            changed = True

        if name and user.name != name:
            user.name = name
            changed = True

        if changed:
            await session.flush()

    return user


CurrentUser = Annotated[User, Depends(current_user)]
