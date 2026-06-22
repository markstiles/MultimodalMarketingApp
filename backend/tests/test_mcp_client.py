"""Unit tests for mcp_client.build_mcp_server_config()."""
import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ── build_mcp_server_config ───────────────────────────────────────────────────

async def test_docs_mcp_included_when_configured(monkeypatch):
    monkeypatch.setenv("SITECORE_DOCS_MCP_URL", "https://sitecore.mcp.kapa.ai")
    monkeypatch.setenv("SITECORE_DOCS_MCP_API_KEY", "test-key")

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "sitecore_docs" in config
    assert config["sitecore_docs"]["url"] == "https://sitecore.mcp.kapa.ai"
    assert config["sitecore_docs"]["headers"]["Authorization"] == "Bearer test-key"
    assert config["sitecore_docs"]["transport"] == "streamable_http"


async def test_docs_mcp_skipped_when_url_missing(monkeypatch):
    monkeypatch.delenv("SITECORE_DOCS_MCP_URL", raising=False)
    monkeypatch.setenv("SITECORE_DOCS_MCP_API_KEY", "test-key")

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "sitecore_docs" not in config


async def test_docs_mcp_skipped_when_key_missing(monkeypatch):
    monkeypatch.setenv("SITECORE_DOCS_MCP_URL", "https://sitecore.mcp.kapa.ai")
    monkeypatch.delenv("SITECORE_DOCS_MCP_API_KEY", raising=False)

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "sitecore_docs" not in config


async def test_docs_mcp_skipped_when_both_missing(monkeypatch):
    monkeypatch.delenv("SITECORE_DOCS_MCP_URL", raising=False)
    monkeypatch.delenv("SITECORE_DOCS_MCP_API_KEY", raising=False)

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "sitecore_docs" not in config
    assert config == {}


async def test_marketer_mcp_no_longer_present(monkeypatch):
    """Marketer MCP has been removed; build_mcp_server_config must never return it."""
    monkeypatch.setenv("SITECORE_DOCS_MCP_URL", "https://sitecore.mcp.kapa.ai")
    monkeypatch.setenv("SITECORE_DOCS_MCP_API_KEY", "test-key")

    from app.clients.mcp_client import build_mcp_server_config
    config = await build_mcp_server_config()

    assert "marketer" not in config
