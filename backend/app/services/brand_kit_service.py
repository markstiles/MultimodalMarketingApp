import logging
import os

import httpx

logger = logging.getLogger(__name__)

BRANDS_BASE = "https://edge-platform.sitecorecloud.io/stream/ai-brands-api"
DOCUMENTS_BASE = "https://edge-platform.sitecorecloud.io/stream/ai-document-api"
REVIEW_BASE = "https://edge-platform.sitecorecloud.io/stream/ai-skills-api"

# Brand kit section names that contain brand voice guidelines.
VOICE_SECTION_NAMES = {"Brand Context", "Tone of Voice", "Do's and Don'ts"}


def _org_id() -> str:
    org_id = os.environ.get("SITECORE_ORGANIZATION_ID", "")
    if not org_id:
        raise RuntimeError(
            "SITECORE_ORGANIZATION_ID is not set — add it to your .env"
        )
    return org_id


async def list_brand_kits(stream_token: str) -> list[dict]:
    """Return all brand kits for the organization (id, name, status, industry)."""
    org_id = _org_id()
    url = f"{BRANDS_BASE}/api/brands/v1/organizations/{org_id}/brandkits"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                url,
                headers={"Authorization": f"Bearer {stream_token}"},
            )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", data.get("brandkits", []))
        return [
            {
                "id": kit.get("id"),
                "name": kit.get("name"),
                "status": kit.get("status"),
                "industry": kit.get("industry"),
                "brand_name": kit.get("brandName"),
                "description": kit.get("description"),
            }
            for kit in items
        ]
    except httpx.HTTPStatusError as exc:
        logger.error("list_brand_kits HTTP %d: %s", exc.response.status_code, exc.response.text[:300])
        raise RuntimeError(f"Failed to list brand kits: HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        logger.error("list_brand_kits failed: %s", exc)
        raise RuntimeError(f"Failed to list brand kits: {exc}") from exc


async def create_brand_kit(name: str, stream_token: str, brand_name: str | None = None) -> dict:
    """Create a new brand kit and return {id, name}."""
    org_id = _org_id()
    url = f"{BRANDS_BASE}/api/brands/v1/organizations/{org_id}/brandkits"
    payload: dict = {"name": name}
    if brand_name:
        payload["brandName"] = brand_name
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {stream_token}",
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()
        data = resp.json()
        return {"id": data.get("id"), "name": data.get("name")}
    except httpx.HTTPStatusError as exc:
        logger.error("create_brand_kit HTTP %d: %s", exc.response.status_code, exc.response.text[:300])
        raise RuntimeError(f"Failed to create brand kit: HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to create brand kit: {exc}") from exc


async def _list_sections(kit_id: str, stream_token: str) -> list[dict]:
    org_id = _org_id()
    url = f"{BRANDS_BASE}/api/brands/v1/organizations/{org_id}/brandkits/{kit_id}/sections"
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(url, headers={"Authorization": f"Bearer {stream_token}"})
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def _list_fields(kit_id: str, section_id: str, stream_token: str) -> list[dict]:
    org_id = _org_id()
    url = (
        f"{BRANDS_BASE}/api/brands/v2/organizations/{org_id}"
        f"/brandkits/{kit_id}/sections/{section_id}/fields"
    )
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(url, headers={"Authorization": f"Bearer {stream_token}"})
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def get_brand_kit_voice_sections(kit_id: str, stream_token: str) -> dict:
    """Read Brand Context, Tone of Voice, and Do's & Don'ts from the brand kit.

    Returns a dict with keys: brand_context, tone_of_voice, dos_and_donts,
    each containing the concatenated field values for that section, or an empty
    string if the section does not exist or has no content.
    """
    try:
        sections = await _list_sections(kit_id, stream_token)
    except Exception as exc:
        raise RuntimeError(f"Failed to read brand kit sections: {exc}") from exc

    result: dict[str, str] = {
        "brand_context": "",
        "tone_of_voice": "",
        "dos_and_donts": "",
    }

    key_map = {
        "Brand Context": "brand_context",
        "Tone of Voice": "tone_of_voice",
        "Do's and Don'ts": "dos_and_donts",
        "Dos and Don'ts": "dos_and_donts",
    }

    for section in sections:
        section_name = section.get("name", "")
        result_key = key_map.get(section_name)
        if not result_key:
            continue
        section_id = section.get("id")
        if not section_id:
            continue
        try:
            fields = await _list_fields(kit_id, section_id, stream_token)
            parts = []
            for field in fields:
                value = field.get("value")
                if isinstance(value, str) and value.strip():
                    parts.append(f"**{field.get('name', '')}**: {value.strip()}")
                elif isinstance(value, list):
                    items = [str(v) for v in value if v]
                    if items:
                        parts.append(f"**{field.get('name', '')}**: {', '.join(items)}")
            result[result_key] = "\n\n".join(parts)
        except Exception as exc:
            logger.warning("Failed to read fields for section %s: %s", section_name, exc)

    return result


async def upload_brand_document(
    kit_id: str,
    file_url: str,
    filename: str,
    stream_token: str,
) -> dict:
    """Upload a brand document (by URL) to a brand kit via the Document Management API.

    file_url may be an absolute https URL or a Sitecore media path beginning with '/'.
    If it starts with '/', the SITECORE_CM_HOST is prepended to make it absolute.

    Returns {id, status, title} from the created document.
    """
    org_id = _org_id()

    if file_url.startswith("/"):
        cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
        if not cm_host:
            raise RuntimeError("SITECORE_CM_HOST not set — cannot resolve relative media URL")
        file_url = f"{cm_host}{file_url}"

    create_request = {
        "url": file_url,
        "setMetadata": True,
        "title": filename,
        "references": [
            {
                "type": "brandkit",
                "id": kit_id,
                "path": f"/api/brands/v1/organizations/{org_id}/brandkits/{kit_id}/references",
            }
        ],
    }

    import json
    url = f"{DOCUMENTS_BASE}/api/documents/v2/organizations/{org_id}/documents"
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                url,
                data={"create_request": json.dumps(create_request)},
                headers={"Authorization": f"Bearer {stream_token}"},
            )
        resp.raise_for_status()
        data = resp.json()
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "title": data.get("title"),
        }
    except httpx.HTTPStatusError as exc:
        logger.error("upload_brand_document HTTP %d: %s", exc.response.status_code, exc.response.text[:300])
        raise RuntimeError(f"Failed to upload brand document: HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to upload brand document: {exc}") from exc


async def get_brand_kit_sections(
    kit_id: str,
    stream_token: str,
    section_names: list[str] | None = None,
) -> dict:
    """Return brand kit section content filtered to the requested section names.

    When section_names is None or empty, all sections with content are returned.
    Section name matching is case-insensitive. Sections with no field content are
    omitted from the result silently.

    Returns:
        {
            "sections": [{"name": str, "content": str}, ...],
            "empty_sections": [str, ...],   # requested but found empty
            "missing_sections": [str, ...], # requested but not in kit at all
        }
    """
    try:
        all_sections = await _list_sections(kit_id, stream_token)
    except Exception as exc:
        raise RuntimeError(f"Failed to read brand kit sections: {exc}") from exc

    section_index = {s.get("name", ""): s for s in all_sections}

    if section_names:
        requested_lower = {n.lower(): n for n in section_names}
        matched = {
            display: section_index[actual]
            for actual, display in {
                actual_name: requested_lower[actual_name.lower()]
                for actual_name in section_index
                if actual_name.lower() in requested_lower
            }.items()
        }
        missing = [
            n for n in section_names
            if n.lower() not in {k.lower() for k in section_index}
        ]
    else:
        matched = {name: sec for name, sec in section_index.items()}
        missing = []

    result_sections = []
    empty_sections = []

    for display_name, section in matched.items():
        section_id = section.get("id")
        if not section_id:
            empty_sections.append(display_name)
            continue
        try:
            fields = await _list_fields(kit_id, section_id, stream_token)
        except Exception as exc:
            logger.warning("Failed to read fields for section %s: %s", display_name, exc)
            empty_sections.append(display_name)
            continue

        parts = []
        for field in fields:
            value = field.get("value")
            if isinstance(value, str) and value.strip():
                parts.append(f"**{field.get('name', '')}**: {value.strip()}")
            elif isinstance(value, list):
                items = [str(v) for v in value if v]
                if items:
                    parts.append(f"**{field.get('name', '')}**: {', '.join(items)}")

        if parts:
            result_sections.append({"name": display_name, "content": "\n\n".join(parts)})
        else:
            empty_sections.append(display_name)

    return {
        "sections": result_sections,
        "empty_sections": empty_sections,
        "missing_sections": missing,
    }


async def run_brand_review(kit_id: str, content: str, stream_token: str) -> dict:
    """Score content against a brand kit using the Brand Review API.

    Returns {overall_score, reviews} where overall_score is the mean across
    all section scores and reviews is the raw list from the API.
    """
    url = f"{REVIEW_BASE}/api/skills/v1/brandreview/generate"
    payload = {
        "brandkitId": kit_id,
        "input": {"content": content},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {stream_token}",
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()
        data = resp.json()
        reviews = data.get("reviews", [])
        scores = [r["score"] for r in reviews if isinstance(r.get("score"), (int, float))]
        overall = round(sum(scores) / len(scores), 1) if scores else None
        return {"overall_score": overall, "reviews": reviews}
    except httpx.HTTPStatusError as exc:
        logger.error("run_brand_review HTTP %d: %s", exc.response.status_code, exc.response.text[:300])
        raise RuntimeError(f"Brand review failed: HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Brand review failed: {exc}") from exc
