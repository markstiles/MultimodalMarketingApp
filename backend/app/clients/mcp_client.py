import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


async def build_mcp_server_config() -> dict[str, Any]:
    """Build the server config dict for MultiServerMCPClient.

    Currently supports the Sitecore documentation MCP (kapa.ai) as the only
    MCP server. Both SITECORE_DOCS_MCP_URL and SITECORE_DOCS_MCP_API_KEY must
    be set to enable it; omitting either skips the server entirely.
    """
    servers: dict[str, Any] = {}

    docs_url = os.environ.get("SITECORE_DOCS_MCP_URL", "")
    docs_api_key = os.environ.get("SITECORE_DOCS_MCP_API_KEY", "")
    if docs_url and docs_api_key:
        servers["sitecore_docs"] = {
            "url": docs_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {docs_api_key}"},
        }
        logger.info("Sitecore docs MCP configured: %s", docs_url)
    else:
        logger.info(
            "Sitecore docs MCP skipped — set SITECORE_DOCS_MCP_URL and "
            "SITECORE_DOCS_MCP_API_KEY to enable"
        )

    return servers
