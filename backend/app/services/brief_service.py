import logging
import os

import httpx

from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)

_AGENT_API_BASE = "https://edge-platform.sitecorecloud.io/stream/ai-agent-api"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def list_brief_types() -> list[dict]:
    """Return all available brief types from GET /api/v1/brief/brief-types."""
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/brief-types"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", data) if isinstance(data, dict) else data


async def generate_brief(brief_type_id: str, brand_id: str, prompt: str) -> dict:
    """AI-generate brief field content via POST /api/v1/brief/generate.

    Does NOT save the result — call create_brief() to persist.
    Returns the generated fields dict keyed by field name.
    """
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/generate"
    body = {"briefTypeId": brief_type_id, "brandId": brand_id, "prompt": prompt}
    async with httpx.AsyncClient(timeout=60) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


async def create_brief(
    name: str,
    brief_type_id: str,
    fields: dict | None = None,
    locale: str = "en-us",
) -> dict:
    """Create and save a brief draft via POST /api/v1/brief.

    Args:
        name: Display name for the brief
        brief_type_id: ID from list_brief_types()
        fields: Optional dict of {fieldName: {type, value}} pairs
        locale: Locale code in xx-XX format (default en-us)

    Returns the created brief with its id, name, status, and locale.
    """
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief"
    body: dict = {"name": name, "locale": locale, "briefTypeId": brief_type_id}
    if fields:
        body["fields"] = fields
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


async def get_brief(brief_id: str) -> dict:
    """Retrieve a saved brief by ID via GET /api/v1/brief/{brief_id}."""
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/{brief_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    if resp.status_code == 404:
        raise ValueError(
            f"Brief '{brief_id}' not found (404). "
            "The ID may be from a different tool — use find_campaign_brief to list "
            "briefs accessible via the Agents API, then copy the id from that response."
        )
    resp.raise_for_status()
    return resp.json()


async def update_brief(brief_id: str, name: str | None = None, fields: dict | None = None) -> dict:
    """Partially update a brief via PUT /api/v1/brief/{brief_id}.

    Only the provided fields are updated; existing fields are preserved.
    """
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/{brief_id}"
    body: dict = {}
    if name is not None:
        body["name"] = name
    if fields is not None:
        body["fields"] = fields
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.put(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


async def list_briefs(
    name: str | None = None,
    status: str | None = None,
    type_id: str | None = None,
) -> list[dict]:
    """List briefs via GET /api/v1/brief with optional filters."""
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief"
    params: dict = {}
    if name:
        params["name"] = name
    if status:
        params["status"] = status
    if type_id:
        params["type_id"] = type_id
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params=params, headers=_headers(token))
    resp.raise_for_status()
    data = resp.json()

    # Log response shape at INFO so mismatches are visible in backend logs
    if isinstance(data, dict):
        logger.info("list_briefs response keys: %s", list(data.keys()))
        for key in ("items", "data", "results", "briefs"):
            if key in data:
                items = data[key]
                break
        else:
            # No recognised wrapper key — treat the dict itself as the response
            items = data
    else:
        items = data  # top-level array

    if isinstance(items, list) and items and isinstance(items[0], dict):
        logger.info("list_briefs first item keys: %s", list(items[0].keys()))

    return items


def brief_fields_to_text(fields: dict) -> str:
    """Convert brief fields dict to plain text for context injection."""
    lines = []
    for key, val in fields.items():
        if isinstance(val, dict):
            value = val.get("value") or val.get("text") or ""
        else:
            value = str(val)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
