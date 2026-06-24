import logging
import os

import httpx

from app.services._api_endpoint import api_endpoint

logger = logging.getLogger(__name__)


def _normalize_id(value: str) -> str:
    """Strip Sitecore-style curly braces from a GUID, e.g. {B0A6...} → b0a6..."""
    return value.strip("{}").lower() if value else value


_INVALID_NAME_CHARS = str.maketrans({
    "/": "-", "\\": "-", ":": "-", "*": "",
    "?": "", '"': "", "<": "", ">": "", "|": "",
})


def _sanitize_page_name(name: str) -> str:
    """Replace characters Sitecore rejects in item names."""
    cleaned = name.translate(_INVALID_NAME_CHARS).strip()
    if cleaned != name:
        logger.warning("create_page_api: sanitized page name %r → %r", name, cleaned)
    return cleaned


def _get_base_url() -> str:
    return os.environ.get(
        "SITECORE_PAGES_API_BASE_URL",
        "https://xmapps-api.sitecorecloud.io/api/v1/pages",
    ).rstrip("/")


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@api_endpoint(exposed=True, category="pages")
async def search_pages_api(
    root_page_id: str,
    query: str,
    language: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    if not query or not query.strip():
        return {
            "success": False,
            "pages": [],
            "total_count": 0,
            "has_more": False,
            "error": (
                "searchText is required and cannot be empty. "
                "To find the site home page, pass root_page_id=site_id and query='Home'."
            ),
        }

    # rootIds is an array param; httpx repeats the key for each list entry.
    params: list[tuple[str, str]] = [
        ("rootIds", root_page_id),
        ("searchText", query.strip()),
    ]
    if language:
        params.append(("language", language))

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/search",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("search_pages_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "pages": [], "total_count": 0, "has_more": False, "error": str(exc)}
    except Exception as exc:
        logger.error("search_pages_api error: %s", exc)
        return {"success": False, "pages": [], "total_count": 0, "has_more": False, "error": str(exc)}

    raw_pages = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(raw_pages, dict):
        raw_pages = raw_pages.get("items", [])

    pages = [
        {
            "page_id": _normalize_id(p.get("id", "")),
            "display_name": p.get("displayName", p.get("name", "")),
            "parent_path": p.get("parentPath", p.get("path", "")),
            "template_name": p.get("templateName", ""),
            "is_folder": p.get("isFolder", False),
            "site_id": p.get("siteId", ""),
        }
        for p in (raw_pages if isinstance(raw_pages, list) else [])
    ]

    total = data.get("total", len(pages)) if isinstance(data, dict) else len(pages)
    return {
        "success": True,
        "pages": pages[:20],
        "total_count": total,
        "has_more": total > 20,
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def get_insert_options_api(
    parent_page_id: str,
    site_id: str,
    language: str,
    auth_token: str,
    insert_option_kind: str = "Page",
) -> dict:
    base_url = _get_base_url()
    params = {
        "site": site_id,
        "language": language,
        "insertOptionKind": insert_option_kind,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/{_normalize_id(parent_page_id)}/insertoptions",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_insert_options_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "insert_options": [], "error": str(exc)}
    except Exception as exc:
        logger.error("get_insert_options_api error: %s", exc)
        return {"success": False, "insert_options": [], "error": str(exc)}

    raw = data if isinstance(data, list) else data.get("data", data.get("items", []))
    if raw and isinstance(raw, list):
        logger.info("get_insert_options_api first item keys: %s, sample: %s", list(raw[0].keys()), raw[0])
    options = [
        {
            "template_id": _normalize_id(t.get("id") or t.get("templateId") or ""),
            "template_name": t.get("displayName") or t.get("name") or "",
        }
        for t in (raw if isinstance(raw, list) else [])
    ]
    return {"success": True, "insert_options": options, "error": None}


@api_endpoint(exposed=True, category="pages")
async def get_page_state_api(
    page_id: str,
    auth_token: str,
    site_id: str = "",
    language: str = "",
) -> dict:
    base_url = _get_base_url()
    normalized = _normalize_id(page_id)
    params: dict = {}
    if site_id:
        params["Site"] = site_id
    if language:
        params["Language"] = language
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/{normalized}/state",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "get_page_state_api HTTP %s (raw=%r normalized=%r): %s",
            exc.response.status_code, page_id, normalized, exc.response.text,
        )
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("get_page_state_api error: %s", exc)
        return {"success": False, "error": str(exc)}

    d = data.get("data", data) if isinstance(data, dict) else data
    return {
        "success": True,
        "page_id": d.get("id", page_id),
        "display_name": d.get("displayName", d.get("name", "")),
        "parent_path": d.get("parentPath", d.get("path", "")),
        "template_name": d.get("templateName", ""),
        "language": d.get("language", ""),
        "version": d.get("version", 1),
        "workflow_state": d.get("workflowState", d.get("state", "")),
        "is_live": d.get("isLive", False),
        "last_modified": d.get("lastModified", d.get("updatedAt", "")),
        "site_id": d.get("siteId", ""),
        "error": None,
    }


@api_endpoint(exposed=False, category="pages")
async def create_page_api(
    site_id: str,
    parent_page_id: str,
    template_id: str,
    display_name: str,
    language: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    # CreatePageInput spec: parentId, pageName, templateId, language (no site field)
    body = {
        "parentId": _normalize_id(parent_page_id),
        "templateId": _normalize_id(template_id),
        "pageName": _sanitize_page_name(display_name),
        "language": language,
    }
    logger.debug("create_page_api body: %s", body)
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(base_url, json=body, headers=_auth_headers(auth_token))
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("create_page_api HTTP %s (body=%s): %s", exc.response.status_code, body, exc.response.text)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("create_page_api error: %s", exc)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    d = data.get("data", data) if isinstance(data, dict) else data
    return {
        "success": True,
        "page_id": d.get("id", ""),
        "display_name": d.get("displayName") or d.get("pageName") or display_name,
        "version": None,
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def rename_page_api(
    page_id: str,
    new_display_name: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base_url}/{_normalize_id(page_id)}/rename",
                json={"displayName": new_display_name},
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("rename_page_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("rename_page_api error: %s", exc)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    return {"success": True, "page_id": page_id, "display_name": new_display_name, "version": None, "error": None}


@api_endpoint(exposed=True, category="pages")
async def duplicate_page_api(
    page_id: str,
    site_id: str,
    new_name: str,
    language: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    # DuplicatePageInput spec: site, newName, language (all required)
    body = {"site": site_id, "newName": _sanitize_page_name(new_name), "language": language}
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{base_url}/{_normalize_id(page_id)}/duplicate",
                json=body,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("duplicate_page_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("duplicate_page_api error: %s", exc)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    d = data.get("data", data) if isinstance(data, dict) else data
    return {
        "success": True,
        "page_id": d.get("id", ""),
        "display_name": d.get("displayName", d.get("name", "")),
        "version": None,
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def update_page_fields_api(
    page_id: str,
    site_id: str,
    fields: dict,
    language: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    # SavePageFieldsInput spec: fields, language, site (all required)
    body = {"site": site_id, "fields": fields, "language": language}
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base_url}/{_normalize_id(page_id)}/fields",
                json=body,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("update_page_fields_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("update_page_fields_api error: %s", exc)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    return {"success": True, "page_id": page_id, "display_name": None, "version": None, "error": None}


@api_endpoint(exposed=True, category="pages")
async def create_page_version_api(
    page_id: str,
    language: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base_url}/{_normalize_id(page_id)}/version",
                json={"language": language},
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("create_page_version_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("create_page_version_api error: %s", exc)
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    d = data.get("data", data) if isinstance(data, dict) else data
    return {
        "success": True,
        "page_id": page_id,
        "display_name": None,
        "version": d.get("version", d.get("versionNumber")),
        "error": None,
    }


@api_endpoint(exposed=False, category="pages")
async def delete_page_api(
    page_id: str,
    auth_token: str,
) -> dict:
    base_url = _get_base_url()
    normalized = _normalize_id(page_id)
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.delete(
                f"{base_url}/{normalized}",
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("delete_page_api HTTP %s (page_id=%s): %s", exc.response.status_code, normalized, exc.response.text)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}
    except Exception as exc:
        logger.error("delete_page_api error: %s", exc)
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    return {"success": True, "page_id": page_id, "display_name": None, "version": None, "error": None}


@api_endpoint(exposed=False, category="pages")
async def get_page_api(
    page_id: str,
    auth_token: str,
    site_id: str = "",
    language: str = "",
) -> dict:
    """Return full page info via GET /api/v1/pages/{id}.

    Spec requires site and language as query params.
    Falls back to get_page_state_api if the endpoint returns 404.
    """
    base_url = _get_base_url()
    normalized = _normalize_id(page_id)
    params: dict = {}
    if site_id:
        params["site"] = site_id
    if language:
        params["language"] = language
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/{normalized}",
                params=params,
                headers=_auth_headers(auth_token),
            )
        if resp.status_code == 404:
            logger.debug("get_page_api: 404 for %s, falling back to /state", normalized)
            return await get_page_state_api(page_id, auth_token, site_id=site_id, language=language)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "get_page_api HTTP %s (page_id=%r): %s",
            exc.response.status_code, normalized, exc.response.text,
        )
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("get_page_api error: %s", exc)
        return {"success": False, "error": str(exc)}

    d = data.get("data", data) if isinstance(data, dict) else data
    return {
        "success": True,
        "page_id": d.get("id", page_id),
        "display_name": d.get("displayName", d.get("name", "")),
        "parent_path": d.get("parentPath", d.get("path", "")),
        "template_id": _normalize_id(d.get("templateId", "")),
        "template_name": d.get("templateName", ""),
        "language": d.get("language", ""),
        "version": d.get("version", 1),
        "workflow_state": d.get("workflowState", d.get("state", "")),
        "is_live": d.get("isLive", False),
        "last_modified": d.get("lastModified", d.get("updatedAt", "")),
        "site_id": d.get("siteId", ""),
        "url": d.get("url", ""),
        "error": None,
    }
