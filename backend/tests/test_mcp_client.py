"""Unit tests for mcp_client._get_marketer_token() and build_mcp_server_config()."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Reset the module-level token cache before and after each test."""
    import app.clients.mcp_client as mcp_module
    mcp_module._token_cache.clear()
    yield
    mcp_module._token_cache.clear()


def _mock_http_client(token="mcp-token", expires_in=3600):
    """Return an AsyncMock httpx client that returns an OAuth token response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": token, "expires_in": expires_in}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_response)
    return mock_http


# ── _get_marketer_token ───────────────────────────────────────────────────────

async def test_token_acquired_and_cached(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    mock_http = _mock_http_client("mcp-tok")
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import _get_marketer_token
        t1 = await _get_marketer_token()
        t2 = await _get_marketer_token()

    assert t1 == "mcp-tok"
    assert t2 == "mcp-tok"
    assert mock_http.post.call_count == 1  # second call hit the cache


async def test_token_refreshed_after_expiry(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    import app.clients.mcp_client as mcp_module
    mcp_module._token_cache["token"] = "old-token"
    mcp_module._token_cache["expires_at"] = time.monotonic() - 1  # already expired

    mock_http = _mock_http_client("new-token")
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        token = await mcp_module._get_marketer_token()

    assert token == "new-token"
    assert mock_http.post.call_count == 1


async def test_token_not_refreshed_when_still_valid(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    import app.clients.mcp_client as mcp_module
    mcp_module._token_cache["token"] = "valid-token"
    mcp_module._token_cache["expires_at"] = time.monotonic() + 3600  # expires in 1h

    mock_http = _mock_http_client("should-not-be-called")
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        token = await mcp_module._get_marketer_token()

    assert token == "valid-token"
    assert mock_http.post.call_count == 0


async def test_missing_credentials_raises(monkeypatch):
    for var in ("SITECORE_CLIENT_ID_AUTOMATION", "SITECORE_CLIENT_SECRET_AUTOMATION",
                "AUTHOR_APP_ID", "AUTHOR_APP_CLIENT_CREDENTIALS"):
        monkeypatch.delenv(var, raising=False)

    from app.clients.mcp_client import _get_marketer_token
    with pytest.raises(RuntimeError, match="credentials missing"):
        await _get_marketer_token()


async def test_fallback_to_author_app_credentials(monkeypatch):
    monkeypatch.delenv("SITECORE_CLIENT_ID_AUTOMATION", raising=False)
    monkeypatch.delenv("SITECORE_CLIENT_SECRET_AUTOMATION", raising=False)
    monkeypatch.setenv("AUTHOR_APP_ID", "author-id")
    monkeypatch.setenv("AUTHOR_APP_CLIENT_CREDENTIALS", "author-secret")

    mock_http = _mock_http_client("author-tok")
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import _get_marketer_token
        token = await _get_marketer_token()

    assert token == "author-tok"
    call_data = mock_http.post.call_args[1]["data"]
    assert call_data["client_id"] == "author-id"
    assert call_data["client_secret"] == "author-secret"


async def test_token_url_env_override(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")
    monkeypatch.setenv("MARKETER_MCP_TOKEN_URL", "https://custom-auth.example.com/token")

    mock_http = _mock_http_client()
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import _get_marketer_token
        await _get_marketer_token()

    assert mock_http.post.call_args[0][0] == "https://custom-auth.example.com/token"


async def test_audience_sent_in_token_request(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")
    monkeypatch.delenv("MARKETER_MCP_AUDIENCE", raising=False)

    mock_http = _mock_http_client()
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import _get_marketer_token
        await _get_marketer_token()

    data = mock_http.post.call_args[1]["data"]
    assert data["audience"] == "https://api.sitecorecloud.io"
    assert data["grant_type"] == "client_credentials"


# ── build_mcp_server_config ───────────────────────────────────────────────────

async def test_docs_server_always_included(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    mock_http = _mock_http_client()
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import build_mcp_server_config
        config = await build_mcp_server_config()

    assert "sitecore_docs" in config
    assert "headers" not in config["sitecore_docs"]


async def test_marketer_server_included_on_auth_success(monkeypatch):
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    mock_http = _mock_http_client("marketer-bearer-tok")
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import build_mcp_server_config
        config = await build_mcp_server_config()

    assert "marketer" in config
    assert config["marketer"]["headers"]["Authorization"] == "Bearer marketer-bearer-tok"
    assert config["marketer"]["transport"] == "streamable_http"


async def test_marketer_server_skipped_on_auth_failure(monkeypatch):
    for var in ("SITECORE_CLIENT_ID_AUTOMATION", "SITECORE_CLIENT_SECRET_AUTOMATION",
                "AUTHOR_APP_ID", "AUTHOR_APP_CLIENT_CREDENTIALS"):
        monkeypatch.delenv(var, raising=False)

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "marketer" not in config


async def test_docs_url_env_override(monkeypatch):
    monkeypatch.setenv("SITECORE_DOCS_MCP_URL", "https://custom-docs.example.com")
    monkeypatch.setenv("SITECORE_CLIENT_ID_AUTOMATION", "cid")
    monkeypatch.setenv("SITECORE_CLIENT_SECRET_AUTOMATION", "csecret")

    mock_http = _mock_http_client()
    with patch("app.clients.mcp_client.httpx.AsyncClient", return_value=mock_http):
        from app.clients.mcp_client import build_mcp_server_config
        config = await build_mcp_server_config()

    assert config["sitecore_docs"]["url"] == "https://custom-docs.example.com"
