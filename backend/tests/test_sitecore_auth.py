"""Unit tests for sitecore_auth.get_sitecore_automation_token()."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Reset the module-level token cache before each test."""
    import app.services.sitecore_auth as auth_module
    auth_module._token_cache.clear()
    yield
    auth_module._token_cache.clear()


@pytest.mark.anyio
async def test_token_acquired_and_cached(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "client-id")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "client-secret")

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok-abc", "expires_in": 3600}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch("app.services.sitecore_auth.httpx.AsyncClient", return_value=mock_http):
        from app.services.sitecore_auth import get_sitecore_automation_token
        token1 = await get_sitecore_automation_token()
        token2 = await get_sitecore_automation_token()

    assert token1 == "tok-abc"
    assert token2 == "tok-abc"
    # Second call used cache — only one HTTP post was made
    assert mock_http.post.call_count == 1


@pytest.mark.anyio
async def test_token_refreshed_after_expiry(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "client-id")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "client-secret")

    import app.services.sitecore_auth as auth_module

    # Seed an already-expired token
    auth_module._token_cache["token"] = "old-token"
    auth_module._token_cache["expires_at"] = time.monotonic() - 1  # already expired

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "new-token", "expires_in": 3600}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch("app.services.sitecore_auth.httpx.AsyncClient", return_value=mock_http):
        token = await auth_module.get_sitecore_automation_token()

    assert token == "new-token"
    assert mock_http.post.call_count == 1


@pytest.mark.anyio
async def test_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("SITECORE_CLIENT_ID_AUTOMATION", raising=False)
    monkeypatch.delenv("SITECORE_CLIENT_SECRET_AUTOMATION", raising=False)
    monkeypatch.delenv("AUTHOR_APP_ID", raising=False)
    monkeypatch.delenv("AUTHOR_APP_CLIENT_CREDENTIALS", raising=False)

    from app.services.sitecore_auth import get_sitecore_automation_token

    with pytest.raises(RuntimeError, match="SITECORE_CLIENT_ID_AUTOMATION"):
        await get_sitecore_automation_token()
