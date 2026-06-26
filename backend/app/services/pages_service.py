import logging
import os
import time

import httpx

from app.services._api_endpoint import api_endpoint

logger = logging.getLogger(__name__)

# Short-lived cache for insert-options results.
# Key: (parent_page_id, site_id, language) — Value: (expires_at, result)
# Avoids N identical API calls when create_page is invoked N times for the same parent.
_INSERT_OPTIONS_CACHE: dict[tuple, tuple] = {}
_INSERT_OPTIONS_TTL = 120.0  # seconds


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


def _get_agents_base_url() -> str:
    return os.environ.get(
        "SITECORE_AGENTS_API_BASE_URL",
        "https://edge-platform.sitecorecloud.io/stream/ai-agent-api",
    ).rstrip("/")


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@api_endpoint(exposed=True, category="pages")
async def search_pages_api(
    root_page_id: str | list[str],
    query: str,
    language: str,
    auth_token: str,
    page_number: int = 1,
    page_size: int = 20,
) -> dict:
    """Search for pages under one or more root IDs.

    Pass query="" to enumerate all children at a level without filtering.
    rootIds accepts multiple values — all roots are searched in a single request.
    Use page_number/page_size to paginate through large levels (full strategy).
    """
    base_url = _get_base_url()
    roots = [root_page_id] if isinstance(root_page_id, str) else root_page_id

    # rootIds is a repeatable array param; httpx emits one key per entry.
    params: list[tuple[str, str]] = [("rootIds", r) for r in roots]
    if query and query.strip():
        params.append(("searchText", query.strip()))
    if language:
        params.append(("language", language))
    params.append(("pageSize", str(page_size)))
    if page_number > 1:
        params.append(("pageNumber", str(page_number)))

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

    # Response shape: {"totalCount": N, "results": [...Page objects...]}
    raw_pages = data.get("results") if isinstance(data, dict) else None
    if raw_pages is None:
        raw_pages = data if isinstance(data, list) else []

    pages = [
        {
            "page_id": _normalize_id(p.get("id", "")),
            "display_name": p.get("displayName") or p.get("name", ""),
            "parent_id": _normalize_id(p.get("parentId", "")),
            "template_id": _normalize_id(p.get("templateId", "")),
            "has_children": p.get("hasChildren", False),
            "has_presentation": p.get("hasPresentation", True),
            "language": p.get("language", ""),
        }
        for p in (raw_pages if isinstance(raw_pages, list) else [])
    ]

    if not pages and query:
        logger.warning(
            "search_pages_api: 0 results for query=%r rootIds=%s; response keys=%s",
            query,
            roots,
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )

    total = data.get("totalCount", len(pages)) if isinstance(data, dict) else len(pages)
    return {
        "success": True,
        "pages": pages,
        "total_count": total,
        "has_more": (page_number * page_size) < total,
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
    cache_key = (_normalize_id(parent_page_id), site_id, language, insert_option_kind)
    now = time.monotonic()
    cached_expires, cached_result = _INSERT_OPTIONS_CACHE.get(cache_key, (0.0, None))
    if cached_result is not None and now < cached_expires:
        logger.debug("get_insert_options_api cache hit for parent=%s", parent_page_id)
        return cached_result

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

    logger.debug(
        "get_insert_options_api response type=%s keys=%s",
        type(data).__name__,
        list(data.keys()) if isinstance(data, dict) else "N/A",
    )

    # Try all known response envelope shapes the Pages API may return.
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = (
            data.get("data")
            or data.get("items")
            or data.get("insertOptions")
            or data.get("value")
            or []
        )
    else:
        raw = []

    if raw and isinstance(raw, list):
        logger.info(
            "get_insert_options_api parent=%s found %d options; first=%s",
            parent_page_id, len(raw), raw[0],
        )
    else:
        logger.warning(
            "get_insert_options_api parent=%s returned empty options; raw=%r full_response=%r",
            parent_page_id, raw, data,
        )

    options = [
        {
            "template_id": _normalize_id(t.get("id") or t.get("templateId") or ""),
            "template_name": t.get("displayName") or t.get("name") or "",
        }
        for t in (raw if isinstance(raw, list) else [])
    ]
    result = {"success": True, "insert_options": options, "error": None}
    # Only cache non-empty results so a transient empty response doesn't block
    # retries for the full TTL window.
    if options:
        _INSERT_OPTIONS_CACHE[cache_key] = (now + _INSERT_OPTIONS_TTL, result)
    return result


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


def _match_template(hint: str, templates: list[dict]) -> dict:
    """Pick the best template from the available list using a fuzzy hint.

    Priority:
    1. Exact case-insensitive match on template_name
    2. hint is a substring of template_name
    3. template_name is a substring of hint
    4. First template (fallback)
    If hint is empty, prefer templates whose name contains "landing", then first.
    """
    if not templates:
        raise ValueError("No templates available")
    if not hint:
        for t in templates:
            if "landing" in t.get("template_name", "").lower():
                return t
        return templates[0]
    h = hint.lower()
    for t in templates:
        if t.get("template_name", "").lower() == h:
            return t
    for t in templates:
        if h in t.get("template_name", "").lower():
            return t
    for t in templates:
        if t.get("template_name", "").lower() in h:
            return t
    return templates[0]


async def build_site_pages(
    site_id: str,
    home_page_id: str,
    language: str,
    auth_token: str,
    pages: list[dict],
) -> dict:
    """Orchestrate creation of multiple pages from a sitemap specification.

    For each entry in `pages`:
      - Searches by name to detect pages that already exist (skips them but
        records their IDs so child pages can reference them as parents).
      - Resolves the parent page: "home" → home_page_id, or the display name
        of another entry in the sitemap (created or pre-existing).
      - Retrieves insert-options for the parent (result is cached 120 s).
      - Auto-selects the template that best matches template_hint.
      - Creates the page via the Pages API.

    Pages are processed in order; entries whose parent hasn't been resolved yet
    are deferred and retried on subsequent passes (handles nested hierarchies).

    Each entry in `pages` dict:
        name            (str, required) Display name for the new page.
        parent          (str, default "home") "home" or the display name of the
                        parent page — either pre-existing or another entry in
                        this list.
        template_hint   (str, optional) Partial/full name of the desired
                        template (case-insensitive). If omitted or unmatched,
                        the most general available template is used.

    Returns dict with: created, skipped, failed, summary.
    """
    page_id_by_name: dict[str, str] = {"home": home_page_id}
    created: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    # Step 1: Detect which desired pages already exist.
    for spec in pages:
        name = spec.get("name", "").strip()
        if not name or name.lower() in page_id_by_name:
            continue
        search = await search_pages_api(home_page_id, name, language, auth_token)
        for p in search.get("pages", []):
            if p.get("display_name", "").lower() == name.lower():
                pid = p["page_id"]
                page_id_by_name[name.lower()] = pid
                skipped.append({
                    "name": name,
                    "reason": "already exists",
                    "page_id": pid,
                    "template_id": p.get("template_id", ""),
                })
                break

    # Step 2: Create missing pages with queue-based parent resolution.
    skipped_names = {s["name"].lower() for s in skipped}
    queue = [s for s in pages if s.get("name", "").strip().lower() not in skipped_names]

    for _ in range(len(queue) + 1):
        if not queue:
            break
        deferred = []
        # Pages created in THIS pass are not yet ready to accept children — the
        # CMS may not have fully propagated the new item. Any child whose parent
        # was just created here is deferred to the next pass, giving the API one
        # round-trip of settling time.
        created_this_pass: set[str] = set()

        for spec in queue:
            name = spec.get("name", "").strip()
            parent_ref = spec.get("parent", "home").strip().lower()
            hint = spec.get("template_hint", "")

            # Parent resolved but created in the same pass — defer.
            if parent_ref in created_this_pass:
                deferred.append(spec)
                continue

            parent_id = page_id_by_name.get(parent_ref)
            if parent_id is None:
                deferred.append(spec)
                continue

            options = (await get_insert_options_api(parent_id, site_id, language, auth_token)).get("insert_options", [])
            if not options:
                failed.append({"name": name, "reason": "No page templates available at the parent location"})
                continue

            try:
                matched = _match_template(hint, options)
            except ValueError as exc:
                failed.append({"name": name, "reason": str(exc)})
                continue

            result = await create_page_api(site_id, parent_id, matched["template_id"], name, language, auth_token)
            if result.get("success"):
                pid = result["page_id"]
                page_id_by_name[name.lower()] = pid
                created_this_pass.add(name.lower())
                created.append({
                    "name": name,
                    "page_id": pid,
                    "template": matched["template_name"],
                    "parent": spec.get("parent", "home"),
                })
            else:
                failed.append({"name": name, "reason": result.get("error") or "Unknown error"})

        queue = deferred

    for spec in queue:
        failed.append({
            "name": spec.get("name", ""),
            "reason": f"Parent '{spec.get('parent')}' was not found or could not be created",
        })

    return {
        "success": bool(created) or (not failed),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "summary": (
            f"Created {len(created)}, skipped {len(skipped)} (already existed), "
            f"failed {len(failed)}"
        ),
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


# ---------------------------------------------------------------------------
# Agent API — higher-level page operations (SITECORE_AGENTS_API_BASE_URL)
# ---------------------------------------------------------------------------

@api_endpoint(exposed=True, category="pages")
async def add_language_to_page_api(
    page_id: str,
    language: str,
    auth_token: str,
) -> dict:
    """Add a language version to a page via Agent API POST /api/v1/pages/{pageId}/add-language."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base}/api/v1/pages/{normalized}/add-language",
                json={"language": language},
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("add_language_to_page_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("add_language_to_page_api error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {"success": data.get("success", True), "page_id": page_id, "language": language, "error": None}


@api_endpoint(exposed=True, category="pages")
async def add_component_on_page_api(
    page_id: str,
    component_rendering_id: str,
    placeholder_path: str,
    component_item_name: str,
    auth_token: str,
    position_after_component_id: str = "",
) -> dict:
    """Add a component to a placeholder on a page via Agent API POST /api/v1/pages/{pageId}/components."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    body: dict = {
        "componentRenderingId": component_rendering_id,
        "placeholderPath": placeholder_path,
        "componentItemName": component_item_name,
    }
    if position_after_component_id:
        body["position"] = {"afterComponentId": position_after_component_id}
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base}/api/v1/pages/{normalized}/components",
                json=body,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("add_component_on_page_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "component_id": None, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("add_component_on_page_api error: %s", exc)
        return {"success": False, "component_id": None, "error": str(exc)}

    return {
        "success": True,
        "component_id": data.get("componentId", ""),
        "datasource_id": data.get("datasourceId", ""),
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def get_components_on_page_api(
    page_id: str,
    language: str,
    auth_token: str,
) -> dict:
    """Retrieve all components on a page via Agent API GET /api/v1/pages/{pageId}/components."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    params: dict = {}
    if language:
        params["language"] = language
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base}/api/v1/pages/{normalized}/components",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_components_on_page_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "components": [], "error": str(exc)}
    except Exception as exc:
        logger.error("get_components_on_page_api error: %s", exc)
        return {"success": False, "components": [], "error": str(exc)}

    raw = data.get("components", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    return {"success": True, "components": raw, "error": None}


@api_endpoint(exposed=True, category="pages")
async def set_component_datasource_api(
    page_id: str,
    component_id: str,
    datasource_id: str,
    language: str,
    auth_token: str,
) -> dict:
    """Set the datasource for a component on a page via Agent API POST /api/v1/pages/{pageId}/components/{componentId}/datasource."""
    base = _get_agents_base_url()
    normalized_page = _normalize_id(page_id)
    normalized_comp = _normalize_id(component_id)
    body: dict = {"datasourceId": datasource_id}
    if language:
        body["language"] = language
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base}/api/v1/pages/{normalized_page}/components/{normalized_comp}/datasource",
                json=body,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("set_component_datasource_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("set_component_datasource_api error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {"success": data.get("success", True), "error": None}


@api_endpoint(exposed=True, category="pages")
async def get_allowed_components_api(
    page_id: str,
    placeholder_name: str,
    auth_token: str,
) -> dict:
    """Retrieve components allowed in a placeholder via Agent API GET /api/v1/pages/{pageId}/placeholders/{name}/allowed-components."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base}/api/v1/pages/{normalized}/placeholders/{placeholder_name}/allowed-components",
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_allowed_components_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "components": [], "error": str(exc)}
    except Exception as exc:
        logger.error("get_allowed_components_api error: %s", exc)
        return {"success": False, "components": [], "error": str(exc)}

    raw = data if isinstance(data, list) else data.get("components", data.get("data", []))
    return {"success": True, "components": raw, "error": None}


@api_endpoint(exposed=True, category="pages")
async def get_page_preview_url_api(
    page_id: str,
    auth_token: str,
    language: str = "",
) -> dict:
    """Get the preview URL for a page via Agent API GET /api/v1/pages/{pageId}/preview-url."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    params: dict = {}
    if language:
        params["language"] = language
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base}/api/v1/pages/{normalized}/preview-url",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_page_preview_url_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "preview_url": None, "error": str(exc)}
    except Exception as exc:
        logger.error("get_page_preview_url_api error: %s", exc)
        return {"success": False, "preview_url": None, "error": str(exc)}

    return {
        "success": True,
        "page_id": data.get("pageId", page_id),
        "preview_url": data.get("previewUrl", ""),
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def get_page_screenshot_api(
    page_id: str,
    auth_token: str,
    version: int = 1,
    language: str = "en",
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Capture a screenshot of a page via Agent API GET /api/v1/pages/{pageId}/screenshot."""
    base = _get_agents_base_url()
    normalized = _normalize_id(page_id)
    params: dict = {"version": version, "language": language}
    if width is not None:
        params["width"] = width
    if height is not None:
        params["height"] = height
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(
                f"{base}/api/v1/pages/{normalized}/screenshot",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_page_screenshot_api HTTP %s: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "screenshot_base64": None, "error": str(exc)}
    except Exception as exc:
        logger.error("get_page_screenshot_api error: %s", exc)
        return {"success": False, "screenshot_base64": None, "error": str(exc)}

    return {
        "success": True,
        "page_id": page_id,
        "screenshot_base64": data.get("screenshot_base64"),
        "type": data.get("type", "png"),
        "encoding": data.get("encoding", "base64"),
        "full_page": data.get("fullPage", True),
        "timestamp": data.get("timestamp"),
        "error": None,
    }


@api_endpoint(exposed=True, category="pages")
async def get_all_pages_by_site_api(
    site_name: str,
    language: str,
    auth_token: str,
) -> dict:
    """Retrieve all pages for a site by name via Agent API GET /api/v1/sites/{siteName}/pages."""
    base = _get_agents_base_url()
    params: dict = {}
    if language:
        params["language"] = language
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(
                f"{base}/api/v1/sites/{site_name}/pages",
                params=params,
                headers=_auth_headers(auth_token),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_all_pages_by_site_api HTTP %s (site=%s): %s", exc.response.status_code, site_name, exc.response.text)
        return {"success": False, "pages": [], "error": str(exc)}
    except Exception as exc:
        logger.error("get_all_pages_by_site_api error: %s", exc)
        return {"success": False, "pages": [], "error": str(exc)}

    raw = data if isinstance(data, list) else data.get("pages", data.get("data", []))
    pages = [
        {
            "page_id": _normalize_id(p.get("id", p.get("pageId", ""))),
            "name": p.get("name", p.get("pageName", "")),
            "path": p.get("path", p.get("pagePath", "")),
            "language": p.get("language", ""),
        }
        for p in (raw if isinstance(raw, list) else [])
    ]
    return {"success": True, "pages": pages, "total_count": len(pages), "error": None}
