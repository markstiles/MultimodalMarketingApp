import logging
import os
import re

import httpx

from app.services._api_endpoint import api_endpoint
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)

_AGENT_API_BASE = "https://edge-platform.sitecorecloud.io/stream/ai-agent-api"

# ---------------------------------------------------------------------------
# Brief field schema — derived from the standard campaign brief type.
# Each entry describes a field the API expects when saving/updating a brief.
# ---------------------------------------------------------------------------

STANDARD_BRIEF_FIELDS: list[dict] = [
    {
        "name": "Objectives",
        "type": "RichText",
        "label": "Campaign Objectives",
        "description": "Primary goals and success metrics for the campaign (e.g. awareness, leads, attendance).",
        "required": True,
    },
    {
        "name": "TargetAudience",
        "type": "RichText",
        "label": "Target Audience",
        "description": "Who the campaign is for — roles, industries, demographics, or segments.",
        "required": True,
    },
    {
        "name": "Message",
        "type": "RichText",
        "label": "Key Message",
        "description": "The core message or value proposition the campaign should convey.",
        "required": True,
    },
    {
        "name": "CreativeRequirements",
        "type": "RichText",
        "label": "Creative Requirements",
        "description": "Brand guidelines, mandatory inclusions, prohibited elements, and tone.",
        "required": False,
    },
    {
        "name": "MarketResearch",
        "type": "RichText",
        "label": "Market Research",
        "description": "Competitor landscape, audience behavior, and market context.",
        "required": False,
    },
    {
        "name": "AdditionalNotes",
        "type": "RichText",
        "label": "Additional Notes",
        "description": "Any other context, constraints, or guidance for the campaign team.",
        "required": False,
    },
    {
        "name": "Timeline",
        "type": "Timeline",
        "label": "Campaign Timeline",
        "description": "Start date, end date, and key milestones. Dates in YYYY-MM-DD format.",
        "required": False,
        "shape": {
            "startDate": "YYYY-MM-DD",
            "endDate": "YYYY-MM-DD",
            "events": [{"title": "string", "dueDate": "YYYY-MM-DD"}],
        },
    },
    {
        "name": "DueDate",
        "type": "DateTime",
        "label": "Due Date",
        "description": "Campaign completion deadline as an ISO 8601 datetime string.",
        "required": False,
        "shape": "ISO 8601 datetime — e.g. '2026-07-19T23:59:59+00:00'",
    },
    {
        "name": "Budget",
        "type": "Budget",
        "label": "Budget",
        "description": "Total campaign budget with currency.",
        "required": False,
        "shape": {"type": "Budget", "currency": "USD", "amount": 0.0},
    },
]

# Map field name → field definition for O(1) lookup
_FIELD_BY_NAME: dict[str, dict] = {f["name"]: f for f in STANDARD_BRIEF_FIELDS}


def text_to_prosemirror(text: str) -> dict:
    """Convert a plain text string to a minimal ProseMirror document.

    Splits on blank lines to produce separate paragraphs. Preserves the
    string as-is if it is already a ProseMirror doc dict.
    """
    if isinstance(text, dict) and text.get("type") == "doc":
        return text

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", str(text).strip()) if p.strip()]
    if not paragraphs:
        paragraphs = [""]

    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": para}],
            }
            for para in paragraphs
        ],
    }


def _normalize_field_value(field_name: str, value: object) -> dict:
    """Wrap a raw value in the {type, value} envelope the API expects.

    If the caller already supplies a properly enveloped dict, return it
    unchanged. Otherwise infer the envelope from the schema.
    """
    if isinstance(value, dict) and "type" in value and "value" in value:
        return value  # already enveloped

    schema = _FIELD_BY_NAME.get(field_name)
    field_type = schema["type"] if schema else "RichText"

    if field_type == "RichText":
        return {"type": "RichText", "value": text_to_prosemirror(value)}
    if field_type == "DateTime":
        return {"type": "DateTime", "value": str(value)}
    if field_type == "Budget":
        if isinstance(value, dict):
            payload = {**value, "type": "Budget"}
        else:
            payload = {"type": "Budget", "currency": "USD", "amount": float(value)}
        return {"type": "Budget", "value": payload}
    if field_type == "Timeline":
        return {"type": "Timeline", "value": value if isinstance(value, dict) else {}}
    return {"type": field_type, "value": value}


def build_brief_fields(
    objectives: str,
    target_audience: str,
    message: str,
    creative_requirements: str = "",
    market_research: str = "",
    additional_notes: str = "",
    due_date: str | None = None,
    budget_amount: float | None = None,
    budget_currency: str = "USD",
    timeline_start: str | None = None,
    timeline_end: str | None = None,
    timeline_events: list[dict] | None = None,
) -> dict:
    """Build a properly typed brief fields dict from plain-text inputs.

    All RichText inputs are wrapped in ProseMirror documents automatically.
    Optional structured fields (Budget, Timeline, DueDate) are included only
    when values are supplied.

    Returns a dict ready to pass as the `fields` argument to create_brief /
    update_brief.
    """
    fields: dict = {
        "Objectives": _normalize_field_value("Objectives", objectives),
        "TargetAudience": _normalize_field_value("TargetAudience", target_audience),
        "Message": _normalize_field_value("Message", message),
    }
    if creative_requirements:
        fields["CreativeRequirements"] = _normalize_field_value("CreativeRequirements", creative_requirements)
    if market_research:
        fields["MarketResearch"] = _normalize_field_value("MarketResearch", market_research)
    if additional_notes:
        fields["AdditionalNotes"] = _normalize_field_value("AdditionalNotes", additional_notes)
    if due_date:
        dt = due_date if "T" in due_date else f"{due_date}T23:59:59+00:00"
        fields["DueDate"] = _normalize_field_value("DueDate", dt)
    if budget_amount is not None:
        fields["Budget"] = _normalize_field_value(
            "Budget", {"type": "Budget", "currency": budget_currency, "amount": budget_amount}
        )
    if timeline_start or timeline_end or timeline_events:
        timeline_val: dict = {}
        if timeline_start:
            timeline_val["startDate"] = timeline_start
        if timeline_end:
            timeline_val["endDate"] = timeline_end
        if timeline_events:
            timeline_val["events"] = timeline_events
        fields["Timeline"] = _normalize_field_value("Timeline", timeline_val)
    return fields


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@api_endpoint(exposed=True, category="briefs")
async def list_brief_types() -> list[dict]:
    """Return all available brief types from GET /api/v1/brief/brief-types."""
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/brief-types"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", data) if isinstance(data, dict) else data


@api_endpoint(exposed=True, category="briefs")
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


@api_endpoint(exposed=True, category="briefs")
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
        body["fields"] = {k: _normalize_field_value(k, v) for k, v in fields.items()}
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json=body, headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="briefs")
async def get_brief(brief_id: str) -> dict:
    """Retrieve a saved brief by ID via GET /api/v1/brief/{brief_id}.

    Falls back to listing all briefs and filtering by ID if the direct GET returns 404,
    since the list endpoint and the individual GET endpoint can behave differently.
    """
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/{brief_id}"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_headers(token))
    if resp.status_code == 404:
        # The individual GET sometimes returns 404 for briefs that are accessible via the
        # list endpoint — fall back to listing and finding by ID.
        logger.warning("get_brief: 404 for ID %s, falling back to list endpoint", brief_id)
        all_briefs = await list_briefs()
        for brief in all_briefs:
            if brief.get("id") == brief_id:
                logger.info("get_brief: resolved via list fallback for ID %s", brief_id)
                return brief
        raise ValueError(
            f"Brief '{brief_id}' not found. "
            "Use find_campaign_brief to list available briefs and confirm the ID."
        )
    resp.raise_for_status()
    return resp.json()


@api_endpoint(exposed=True, category="briefs")
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


@api_endpoint(exposed=True, category="briefs")
async def list_briefs(
    name: str | None = None,
    status: str | None = None,
    brief_type_id: str | None = None,
) -> list[dict]:
    """List briefs via GET /api/v1/brief with optional filters."""
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief"
    params: dict = {}
    if name:
        params["name"] = name
    if status:
        params["status"] = status
    if brief_type_id:
        params["type_id"] = brief_type_id
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


@api_endpoint(exposed=False, category="briefs")
async def delete_brief(brief_id: str) -> dict:
    """Delete a brief by ID via DELETE /api/v1/brief/{brief_id}.

    Returns {success, brief_id} on success or {success, error} on failure.
    """
    token = await get_sitecore_automation_token()
    url = f"{_AGENT_API_BASE}/api/v1/brief/{brief_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.delete(url, headers=_headers(token))
        if resp.status_code == 404:
            return {"success": False, "error": f"Brief '{brief_id}' not found."}
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("delete_brief HTTP %d (id=%s): %s", exc.response.status_code, brief_id, exc.response.text)
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("delete_brief error: %s", exc)
        return {"success": False, "error": str(exc)}
    return {"success": True, "brief_id": brief_id}


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
