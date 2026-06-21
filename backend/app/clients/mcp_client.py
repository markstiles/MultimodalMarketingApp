import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_token_cache: dict[str, Any] = {}


async def _get_marketer_token() -> str:
    """Client-credentials OAuth token for the Marketer MCP."""
    now = time.monotonic()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    # Accept either the Automation credential names or the older Author app names
    client_id = (
        os.environ.get("SITECORE_CLIENT_ID_AUTOMATION")
        or os.environ.get("AUTHOR_APP_ID", "")
    )
    client_secret = (
        os.environ.get("SITECORE_CLIENT_SECRET_AUTOMATION")
        or os.environ.get("AUTHOR_APP_CLIENT_CREDENTIALS", "")
    )
    if not client_id or not client_secret:
        raise RuntimeError(
            "Marketer MCP credentials missing — set SITECORE_CLIENT_ID_AUTOMATION "
            "and SITECORE_CLIENT_SECRET_AUTOMATION (or AUTHOR_APP_ID / "
            "AUTHOR_APP_CLIENT_CREDENTIALS) in your .env"
        )

    token_url = os.environ.get(
        "MARKETER_MCP_TOKEN_URL",
        "https://auth.sitecorecloud.io/oauth/token",
    )
    # Automation credentials are scoped to the general XM Cloud API audience;
    # the Marketer MCP server accepts tokens issued for this audience.
    audience = os.environ.get(
        "MARKETER_MCP_AUDIENCE",
        "https://api.sitecorecloud.io",
    )

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": audience,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    logger.info("Marketer MCP token acquired (expires in %ds)", data.get("expires_in", 3600))
    return _token_cache["token"]


async def build_mcp_server_config() -> dict[str, Any]:
    """Build the server config dict for MultiServerMCPClient."""
    servers: dict[str, Any] = {}

    # Sitecore documentation MCP (Kapa.ai) — no authentication required
    docs_url = os.environ.get("SITECORE_DOCS_MCP_URL", "https://sitecore.mcp.kapa.ai")
    servers["sitecore_docs"] = {
        "url": docs_url,
        "transport": "streamable_http",
    }
    logger.info("Sitecore docs MCP configured: %s", docs_url)

    # Marketer MCP (OAuth)
    marketer_url = os.environ.get(
        "MARKETER_MCP_URL",
        "https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod",
    )
    try:
        token = await _get_marketer_token()
        servers["marketer"] = {
            "url": marketer_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {token}"},
        }
        logger.info("Marketer MCP configured: %s", marketer_url)
    except Exception as exc:
        logger.warning("Marketer MCP skipped (auth failed: %s)", exc)

    return servers
