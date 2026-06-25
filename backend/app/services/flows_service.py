import logging
import os

import httpx

from app.services._api_endpoint import api_endpoint
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


def _get_agents_base_url() -> str:
    return os.environ.get(
        "SITECORE_AGENTS_API_BASE_URL",
        "https://edge-platform.sitecorecloud.io/stream/ai-agent-api",
    ).rstrip("/")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@api_endpoint(exposed=True, category="flows")
async def list_flow_definitions_by_page_api(page_id: str, language: str = "en") -> list:
    """List all flow definitions (A/B tests and personalizations) for a page.

    Calls GET /api/v1/flows/by-page/{pageId}.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/flows/by-page/{page_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"language": language}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="flows")
async def get_flow_definition_api(flow_id: str) -> dict:
    """Get a specific flow definition by ID.

    Calls GET /api/v1/flows/{flowId}.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/flows/{flow_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="flows")
async def get_variant_api(flow_id: str, variant_id: str, language: str = "en") -> dict:
    """Get variant details for a specific flow.

    Calls GET /api/v1/flows/{flowId}/variants/{variantId}.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/flows/{flow_id}/variants/{variant_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"language": language}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="flows")
async def setup_variant_api(
    flow_id: str,
    variant_id: str,
    page_id: str,
    component_id: str,
    variant_strategy: str,
    language: str = "en",
    page_version: int | None = None,
    swapped_component: dict | None = None,
) -> dict:
    """Set up a variant for a flow (A/B test or personalization).

    Calls POST /api/v1/flows/{flowId}/variants/{variantId}.

    variant_strategy must be one of: HIDE, SWAP, COPY.
    swapped_component is required when variant_strategy is SWAP.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/flows/{flow_id}/variants/{variant_id}"
    body: dict = {
        "page_id": page_id,
        "component_id": component_id,
        "variant_strategy": variant_strategy,
        "language": language,
    }
    if page_version is not None:
        body["page_version"] = page_version
    if swapped_component is not None:
        body["swapped_component"] = swapped_component
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()
