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


@api_endpoint(exposed=True, category="components")
async def list_components_api(site_name: str) -> dict:
    """List all components available for a site via GET /api/v1/components."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/components"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"site_name": site_name}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="components")
async def get_component_api(component_id: str) -> dict:
    """Get details of a single component via GET /api/v1/components/{componentId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/components/{component_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="components")
async def create_component_datasource_api(
    component_id: str,
    site_name: str,
    data_fields: dict,
    language: str = "en",
) -> dict:
    """Create a datasource item for a component via POST /api/v1/components/{componentId}/datasources."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/components/{component_id}/datasources"
    body: dict = {"siteName": site_name, "dataFields": data_fields, "language": language}
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="components")
async def search_component_datasources_api(component_id: str, term: str) -> dict:
    """Search available datasources for a component via GET /api/v1/components/{componentId}/datasources/search."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/components/{component_id}/datasources/search"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"term": term}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()
