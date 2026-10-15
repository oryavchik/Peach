from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app import auth
from app.config import get_settings
from tests.tokens import make_token


def test_configured_jwks_verifies_test_token():
    assert auth._decode_token(make_token())["sub"] == "alice-sub"


def test_missing_jwks_downloads_key_from_configured_issuer(monkeypatch):
    settings = get_settings()
    original_keys = settings.cognito_jwks
    import jwt

    key = jwt.PyJWKSet.from_json(original_keys).keys[0].key
    client = Mock()
    client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key)
    factory = Mock(return_value=client)
    monkeypatch.setattr(settings, "cognito_jwks", "")
    monkeypatch.setattr(auth, "_jwks_client", factory)
    assert auth._decode_token(make_token())["sub"] == "alice-sub"
    factory.assert_called_once_with(settings.cognito_issuer)


def test_bad_token_is_rejected():
    with pytest.raises(HTTPException) as error:
        auth._decode_token("invalid")
    assert error.value.status_code == 401
