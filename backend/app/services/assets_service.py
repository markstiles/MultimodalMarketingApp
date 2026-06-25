import json
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


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@api_endpoint(exposed=True, category="assets")
async def search_assets_api(
    query: str = "",
    language: str = "en",
    asset_type: str = "",
) -> list:
    """Search for assets in the Sitecore media library via GET /api/v1/assets/search."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/assets/search"
    params: dict = {"language": language}
    if query:
        params["query"] = query
    if asset_type:
        params["type"] = asset_type
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params=params, headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="assets")
async def get_asset_info_api(asset_id: str) -> dict:
    """Get full details of a specific asset via GET /api/v1/assets/{assetId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/assets/{asset_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="assets")
async def upload_asset_api(
    file_content: bytes,
    filename: str,
    item_path: str,
    extension: str,
    site_name: str,
    language: str = "en",
) -> dict:
    """Upload a new asset via POST /api/v1/assets/upload (multipart/form-data).

    The upload_request field is a JSON string containing name, itemPath, language,
    extension, and siteName.
    """
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/assets/upload"
    upload_request = json.dumps({
        "name": filename,
        "itemPath": item_path,
        "language": language,
        "extension": extension,
        "siteName": site_name,
    })
    async with httpx.AsyncClient(timeout=60) as http:
        resp = await http.post(
            url,
            headers=_auth_headers(token),
            files={"file": (filename, file_content)},
            data={"upload_request": upload_request},
        )
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="assets")
async def update_asset_api(
    asset_id: str,
    fields: dict | None = None,
    language: str = "en",
    name: str | None = None,
) -> dict:
    """Update asset metadata via PUT /api/v1/assets/{assetId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/assets/{asset_id}"
    body: dict = {"language": language}
    if fields:
        body["fields"] = fields
    if name:
        body["name"] = name
    headers = {**_auth_headers(token), "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.put(url, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()
