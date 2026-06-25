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


@api_endpoint(exposed=True, category="content")
async def create_content_item_api(
    template_id: str,
    name: str,
    parent_id: str,
    language: str = "en",
    fields: dict | None = None,
) -> dict:
    """Create a content item via POST /api/v1/content/create."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content/create"
    body: dict = {"templateId": template_id, "name": name, "parentId": parent_id, "language": language}
    if fields:
        body["fields"] = fields
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="content")
async def get_content_item_by_id_api(item_id: str, language: str = "en") -> dict:
    """Get a content item by ID via GET /api/v1/content/{itemId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content/{item_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"language": language}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="content")
async def get_content_item_by_path_api(
    item_path: str,
    language: str = "en",
    fail_on_not_found: bool = True,
) -> dict:
    """Get a content item by Sitecore path via GET /api/v1/content."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content"
    params: dict = {
        "item_path": item_path,
        "language": language,
        "failOnNotFound": str(fail_on_not_found).lower(),
    }
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params=params, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="content")
async def update_content_api(
    item_id: str,
    fields: dict | None = None,
    language: str = "en",
    create_new_version: bool = False,
    site_name: str | None = None,
) -> dict:
    """Update a content item via PUT /api/v1/content/{itemId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content/{item_id}"
    body: dict = {"language": language, "createNewVersion": create_new_version}
    if fields is not None:
        body["fields"] = fields
    if site_name:
        body["siteName"] = site_name
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.put(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="content")
async def delete_content_api(item_id: str, language: str = "en") -> dict:
    """Delete a content item via DELETE /api/v1/content/{itemId}.

    NOTE: Deletes ALL language versions regardless of the language parameter.
    The language param is accepted but does not scope deletion.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content/{item_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.delete(url, params={"language": language}, headers=_headers(token))
        if resp.status_code == 404:
            return {"success": False, "error": f"Content item '{item_id}' not found."}
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "delete_content HTTP %d (id=%s): %s",
            exc.response.status_code,
            item_id,
            exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("delete_content error: %s", exc)
        return {"success": False, "error": str(exc)}
    return {"success": True, "item_id": item_id}


@api_endpoint(exposed=True, category="content")
async def list_content_insert_options_api(item_id: str, language: str = "en") -> list:
    """Get allowed child templates for a content item via GET /api/v1/content/{itemId}/insert-options."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/content/{item_id}/insert-options"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"language": language}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()
