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


# ---------------------------------------------------------------------------
# Personalization
# ---------------------------------------------------------------------------

@api_endpoint(exposed=True, category="personalization")
async def get_personalization_versions_api(page_id: str, language: str = "en") -> list:
    """List all personalization variants for a page via GET /api/v2/personalization/by-page/{pageId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v2/personalization/by-page/{page_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, params={"language": language}, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="personalization")
async def create_personalization_version_api(
    page_id: str,
    name: str,
    variant_name: str,
    audience_name: str,
    condition_groups: list,
    language: str = "en",
) -> dict:
    """Create a personalization variant via POST /api/v2/personalization/{pageId}/versions."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v2/personalization/{page_id}/versions"
    body: dict = {
        "name": name,
        "variant_name": variant_name,
        "audience_name": audience_name,
        "condition_groups": condition_groups,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="personalization")
async def update_personalization_version_api(
    page_id: str,
    variant_id: str,
    variant_name: str,
    audience_name: str,
    condition_groups: list,
    language: str = "en",
) -> dict:
    """Update a personalization variant via PUT /api/v1/personalization/{pageId}/versions/{variantId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/personalization/{page_id}/versions/{variant_id}"
    body: dict = {
        "variant_name": variant_name,
        "audience_name": audience_name,
        "condition_groups": condition_groups,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.put(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="personalization")
async def get_condition_templates_api() -> list:
    """List all personalization condition templates via GET /api/v1/personalization/condition-templates."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/personalization/condition-templates"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="personalization")
async def get_condition_template_by_id_api(template_id: str) -> dict:
    """Get a specific condition template via GET /api/v1/personalization/condition-templates/{template_id}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/personalization/condition-templates/{template_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# A/B Experiments
# ---------------------------------------------------------------------------

@api_endpoint(exposed=True, category="personalization")
async def create_component_ab_test_api(
    site_id: str,
    page_id: str,
    component_id: str,
    name: str,
    goal_type: str,
    variants: list,
    language: str = "en",
) -> dict:
    """Create an A/B/n test via POST /api/v1/experiments/flows."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/experiments/flows"
    body: dict = {
        "site_id": site_id,
        "page_id": page_id,
        "component_id": component_id,
        "name": name,
        "goal_type": goal_type,
        "variants": variants,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="personalization")
async def update_ab_test_api(
    flow_id: str,
    name: str | None = None,
    variants: list | None = None,
    archived: bool | None = None,
) -> dict:
    """Update an A/B/n test via PUT /api/v1/experiments/{flowId}."""
    token = await get_sitecore_automation_token()
    url = f"{_get_agents_base_url()}/api/v1/experiments/{flow_id}"
    body: dict = {}
    if name is not None:
        body["name"] = name
    if variants is not None:
        body["variants"] = variants
    if archived is not None:
        body["archived"] = archived
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.put(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()
