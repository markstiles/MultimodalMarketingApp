"""Unit tests for auth_verifier.get_user_id() and _verify_jwt()."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


def _fake_request(headers: dict) -> MagicMock:
    """Build a minimal mock of a FastAPI Request with the given headers."""
    req = MagicMock()
    req.headers = headers
    return req


def _mock_jwks_client(kid="key1"):
    """Return an async httpx mock that serves a minimal JWKS document."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"keys": [{"kid": kid, "kty": "RSA"}]}

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)
    return mock_http


# ── local mode ────────────────────────────────────────────────────────────────

async def test_local_mode_returns_header_value(monkeypatch):
    monkeypatch.setenv("RUNTIME_CONTEXT", "local")
    from app.clients.auth_verifier import get_user_id

    request = _fake_request({"X-Local-User-Id": "user-from-header"})
    result = await get_user_id(request)

    assert result == "user-from-header"


async def test_local_mode_defaults_to_local_user(monkeypatch):
    monkeypatch.setenv("RUNTIME_CONTEXT", "local")
    from app.clients.auth_verifier import get_user_id

    request = _fake_request({})  # no X-Local-User-Id header
    result = await get_user_id(request)

    assert result == "local-user"


# ── non-local mode ────────────────────────────────────────────────────────────

async def test_no_authorization_header_raises_401(monkeypatch):
    monkeypatch.setenv("RUNTIME_CONTEXT", "iframe")
    from app.clients.auth_verifier import get_user_id

    request = _fake_request({})
    with pytest.raises(HTTPException) as exc_info:
        await get_user_id(request)

    assert exc_info.value.status_code == 401


async def test_non_bearer_authorization_raises_401(monkeypatch):
    monkeypatch.setenv("RUNTIME_CONTEXT", "iframe")
    from app.clients.auth_verifier import get_user_id

    request = _fake_request({"Authorization": "Basic dXNlcjpwYXNz"})
    with pytest.raises(HTTPException) as exc_info:
        await get_user_id(request)

    assert exc_info.value.status_code == 401


# ── _verify_jwt ───────────────────────────────────────────────────────────────

async def test_verify_jwt_returns_sub_on_success(monkeypatch):
    monkeypatch.setenv("AUTH0_ISSUER_BASE_URL", "https://auth.example.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "my-audience")

    mock_jwt = MagicMock()
    mock_jwt.get_unverified_header.return_value = {"kid": "key1"}
    mock_jwt.decode.return_value = {"sub": "user-abc-123"}

    mock_http = _mock_jwks_client(kid="key1")

    with patch.dict(sys.modules, {"jwt": mock_jwt}), \
         patch("app.clients.auth_verifier.httpx.AsyncClient", return_value=mock_http):
        from app.clients.auth_verifier import _verify_jwt
        user_id = await _verify_jwt("fake.jwt.token")

    assert user_id == "user-abc-123"


async def test_verify_jwt_raises_401_when_jwks_fetch_fails(monkeypatch):
    monkeypatch.setenv("AUTH0_ISSUER_BASE_URL", "https://auth.example.com")

    mock_jwt = MagicMock()
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(side_effect=Exception("network error"))

    with patch.dict(sys.modules, {"jwt": mock_jwt}), \
         patch("app.clients.auth_verifier.httpx.AsyncClient", return_value=mock_http):
        from app.clients.auth_verifier import _verify_jwt
        with pytest.raises(HTTPException) as exc_info:
            await _verify_jwt("fake.jwt.token")

    assert exc_info.value.status_code == 401


async def test_verify_jwt_raises_401_when_decode_fails(monkeypatch):
    monkeypatch.setenv("AUTH0_ISSUER_BASE_URL", "https://auth.example.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "my-audience")

    mock_jwt = MagicMock()
    mock_jwt.get_unverified_header.return_value = {"kid": "key1"}
    mock_jwt.decode.side_effect = Exception("invalid token")

    mock_http = _mock_jwks_client(kid="key1")

    with patch.dict(sys.modules, {"jwt": mock_jwt}), \
         patch("app.clients.auth_verifier.httpx.AsyncClient", return_value=mock_http):
        from app.clients.auth_verifier import _verify_jwt
        with pytest.raises(HTTPException) as exc_info:
            await _verify_jwt("bad.token.here")

    assert exc_info.value.status_code == 401


async def test_verify_jwt_raises_401_when_kid_not_in_jwks(monkeypatch):
    monkeypatch.setenv("AUTH0_ISSUER_BASE_URL", "https://auth.example.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "my-audience")

    mock_jwt = MagicMock()
    mock_jwt.get_unverified_header.return_value = {"kid": "unknown-kid"}

    mock_http = _mock_jwks_client(kid="different-kid")  # JWKS has a different kid

    with patch.dict(sys.modules, {"jwt": mock_jwt}), \
         patch("app.clients.auth_verifier.httpx.AsyncClient", return_value=mock_http):
        from app.clients.auth_verifier import _verify_jwt
        with pytest.raises(HTTPException) as exc_info:
            await _verify_jwt("token.with.unknown.kid")

    assert exc_info.value.status_code == 401
