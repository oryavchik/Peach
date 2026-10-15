"""Local signing keys for tests; never contact the configured Cognito pool."""

import json
import os
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_private_key.public_key()))
_public_jwk.update(kid="test-key", use="sig", alg="RS256")
os.environ["COGNITO_REGION"] = "us-east-1"
os.environ["COGNITO_USER_POOL_ID"] = "test-pool"
os.environ["COGNITO_CLIENT_ID"] = "test-client"
os.environ["COGNITO_JWKS"] = json.dumps({"keys": [_public_jwk]})


def make_token(sub: str = "alice-sub", email: str = "alice@example.com") -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "name": email,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/test-pool",
            "aud": "test-client",
            "token_use": "id",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        _private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}
