import logging
import os

import httpx

logger = logging.getLogger(__name__)

_site_cache: dict[str, dict] = {}
_collection_cache: dict[str, str] = {}


def _get_base_url() -> str:
    return os.environ.get(
        "SITECORE_SITES_API_BASE_URL",
        "https://xmapps-api.sitecorecloud.io/api/v1/sites",
    ).rstrip("/")


def _get_api_base_url() -> str:
    """Return the /api/v1 root (strips trailing /sites if present)."""
    base = os.environ.get(
        "SITECORE_SITES_API_BASE_URL",
        "https://xmapps-api.sitecorecloud.io/api/v1",
    ).rstrip("/")
    if base.endswith("/sites"):
        base = base[: -len("/sites")]
    return base


def _get_collections_base_url() -> str:
    return f"{_get_api_base_url()}/collections"


def _get_languages_base_url() -> str:
    return f"{_get_api_base_url()}/languages"


import re as _re

_UUID_RE = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    _re.IGNORECASE,
)


def _normalize_guid(value: str) -> str:
    """Strip Sitecore-style curly braces from a GUID, e.g. {B0A6...} → b0a6..."""
    return value.strip("{}").lower() if value else value


def _is_valid_guid(value: str) -> bool:
    return bool(_UUID_RE.match(_normalize_guid(value)))


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def _collection_from_fields(item: dict) -> str:
    """Return collection name from explicit API fields, or empty string."""
    raw = item.get("collection") or item.get("siteCollection") or {}
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, dict) and raw.get("name"):
        return raw["name"]
    return ""


async def _resolve_collection(item: dict, auth_token: str) -> str:
    """Resolve collection name for a site API response item.

    Resolution order:
    1. Explicit name fields (collection / siteCollection) — fast path.
    2. GET /api/v1/collections/{collectionId} — authoritative name lookup.
    3. Raw collectionId string — last resort so the field is never empty.
    """
    name = _collection_from_fields(item)
    if name:
        return name

    collection_id = item.get("collectionId", "")
    if not collection_id:
        return ""

    if collection_id in _collection_cache:
        return _collection_cache[collection_id]

    url = f"{_get_collections_base_url()}/{collection_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url, headers=_auth_headers(auth_token))
        if resp.status_code == 404:
            logger.debug("Collection %s not found via API, using ID as name", collection_id)
            _collection_cache[collection_id] = collection_id
            return collection_id
        resp.raise_for_status()
        data = resp.json()
        name = data.get("name") or collection_id
    except Exception as exc:
        logger.warning("Failed to fetch collection name for %s: %s", collection_id, exc)
        name = collection_id

    _collection_cache[collection_id] = name
    return name


async def get_site_info(site_id: str, auth_token: str) -> dict:
    """Return site name and collection for a given site_id.

    Result is cached per process — collections don't change within a session.
    Returns {success, id, name, collection} on success or {success, error} on failure.
    """
    if site_id in _site_cache:
        return _site_cache[site_id]

    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/{site_id}",
                headers=_auth_headers(auth_token),
            )
        if resp.status_code == 404:
            return {"success": False, "error": f"Site not found: {site_id!r}"}
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        return {"success": False, "error": f"Timed out resolving site {site_id!r}"}
    except Exception as exc:
        logger.warning("Failed to get site info for %s: %s", site_id, exc)
        return {"success": False, "error": str(exc)}

    result = {
        "success": True,
        "id": data.get("id", site_id),
        "name": data.get("name", site_id),
        "collection": await _resolve_collection(data, auth_token),
    }
    _site_cache[site_id] = result
    return result


def _clear_site_cache() -> None:
    """Clear the in-process caches — used in tests."""
    _site_cache.clear()
    _collection_cache.clear()


async def get_site_languages(site_id: str, auth_token: str) -> dict:
    """Return all languages configured for a site.

    Returns {success, site_id, languages, count} on success.
    Each language entry has at minimum an `isoCode` field; the API may include
    additional fields such as `displayName` or `englishName`.
    """
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/{site_id}/languages",
                headers=_auth_headers(auth_token),
            )
        if resp.status_code == 404:
            return {"success": False, "error": f"Site not found: {site_id!r}"}
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        return {"success": False, "error": f"Timed out getting languages for site {site_id!r}"}
    except Exception as exc:
        logger.warning("Failed to get site languages for %s: %s", site_id, exc)
        return {"success": False, "error": str(exc)}

    # Normalize: the API may return a bare list or wrap it in a data/languages key.
    raw: list = data if isinstance(data, list) else data.get("data") or data.get("languages") or []
    languages = []
    for item in raw:
        if isinstance(item, str):
            languages.append({"isoCode": item})
        elif isinstance(item, dict):
            # Ensure isoCode is present regardless of field naming variance.
            if "isoCode" not in item:
                item = {**item, "isoCode": item.get("language") or item.get("code") or ""}
            languages.append(item)

    return {
        "success": True,
        "site_id": site_id,
        "languages": languages,
        "count": len(languages),
    }


async def list_sites(auth_token: str) -> dict:
    """Return all sites accessible to the current auth token.

    Returns {success, sites, count} on success. Each site entry has at minimum
    id, name, and collection fields (normalized from the raw API response).
    """
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(base_url, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        return {"success": False, "error": "Timed out listing sites"}
    except Exception as exc:
        logger.warning("Failed to list sites: %s", exc)
        return {"success": False, "error": str(exc)}

    raw: list = data if isinstance(data, list) else data.get("data") or data.get("sites") or []
    sites = []
    for item in raw:
        sites.append({
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "collection": await _resolve_collection(item, auth_token),
        })

    return {"success": True, "sites": sites, "count": len(sites)}


async def get_site_templates(environment_id: str, auth_token: str) -> dict:
    """Return available site templates for the given environment.

    Returns {success, templates, count} on success. Each template has id, name,
    and description fields. Pass a template id to create_site.
    """
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base_url}/templates",
                params={"environmentId": environment_id},
                headers=_auth_headers(auth_token),
            )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_site_templates HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "templates": [], "error": str(exc)}
    except Exception as exc:
        logger.warning("get_site_templates error: %s", exc)
        return {"success": False, "templates": [], "error": str(exc)}

    raw = data if isinstance(data, list) else (
        data.get("data") or data.get("templates") or data.get("items") or []
    )
    templates = [
        {
            "template_id": _normalize_guid(t.get("id", "")),
            "template_name": t.get("name") or t.get("displayName") or "",
            "description": t.get("description", ""),
        }
        for t in (raw if isinstance(raw, list) else [])
    ]
    return {"success": True, "templates": templates, "count": len(templates)}


async def get_environment_languages(environment_id: str, auth_token: str) -> dict:
    """Return all languages available in the given environment.

    Returns {success, languages, count} on success. Each language entry has at
    minimum an isoCode field (e.g. "en", "fr-FR"). Pass isoCode to create_site.
    """
    url = _get_languages_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, params={"environmentId": environment_id}, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_environment_languages HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "languages": [], "error": str(exc)}
    except Exception as exc:
        logger.warning("get_environment_languages error: %s", exc)
        return {"success": False, "languages": [], "error": str(exc)}

    raw = data if isinstance(data, list) else (data.get("data") or data.get("languages") or data.get("items") or [])
    languages = []
    for item in raw:
        if isinstance(item, str):
            languages.append({"isoCode": item, "label": item})
        elif isinstance(item, dict):
            iso = item.get("isoCode") or item.get("code") or item.get("language") or ""
            languages.append({
                "isoCode": iso,
                "label": item.get("displayName") or item.get("englishName") or iso,
                **{k: v for k, v in item.items() if k not in ("isoCode", "code", "language")},
            })

    return {"success": True, "languages": languages, "count": len(languages)}


async def validate_site_name(
    site_name: str,
    language: str,
    template_id: str,
    auth_token: str,
) -> dict:
    """Validate a proposed site name via POST /api/v1/sites/name/validate.

    Returns {success, valid, site_name} when the name is accepted, or
    {success, valid=False, errors} when the API rejects it with field-level messages.
    """
    if not _is_valid_guid(template_id):
        return {
            "success": False,
            "valid": False,
            "error": (
                f"template_id must be the UUID from get_site_templates (the 'template_id' field), "
                f"not the template name. Got: {template_id!r}"
            ),
        }
    base_url = _get_base_url()
    body = {"name": site_name, "language": language, "templateId": _normalize_guid(template_id)}
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base_url}/name/validate",
                json=body,
                headers=_auth_headers(auth_token),
            )
        if resp.status_code in (200, 204):
            return {"success": True, "valid": True, "site_name": site_name}
        if resp.status_code == 400:
            try:
                error_data = resp.json()
            except Exception:
                error_data = {}
            logger.warning(
                "validate_site_name rejected %r (lang=%s template=%s): %s",
                site_name, language, template_id, error_data,
            )
            return {
                "success": True,
                "valid": False,
                "site_name": site_name,
                "errors": error_data.get("errors", error_data),
            }
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("validate_site_name HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "valid": False, "error": str(exc)}
    except Exception as exc:
        logger.warning("validate_site_name error: %s", exc)
        return {"success": False, "valid": False, "error": str(exc)}

    return {"success": True, "valid": True, "site_name": site_name}


async def create_site(
    name: str,
    collection: str,
    language: str,
    template_id: str,
    auth_token: str,
) -> dict:
    """Create a new Sitecore XM Cloud site.

    Call get_site_templates to obtain a valid template_id and validate_site_name
    to confirm the name is acceptable before calling this function.

    Returns {success, id, name, collection} on success or {success, error} on failure.
    A 409 means a site with that name already exists in the given collection.
    """
    if not _is_valid_guid(template_id):
        return {
            "success": False,
            "error": (
                f"template_id must be the UUID from get_site_templates (the 'template_id' field), "
                f"not the template name. Got: {template_id!r}"
            ),
        }
    base_url = _get_base_url()
    payload = {
        "siteName": name,
        "collectionName": collection,
        "language": language,
        "templateId": _normalize_guid(template_id),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(base_url, json=payload, headers=_auth_headers(auth_token))
        if resp.status_code == 409:
            return {
                "success": False,
                "error": f"Site {name!r} already exists in collection {collection!r}",
            }
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
    except httpx.HTTPStatusError as exc:
        logger.error(
            "create_site HTTP %d (payload=%s): %s",
            exc.response.status_code,
            payload,
            exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except httpx.TimeoutException:
        return {"success": False, "error": f"Timed out creating site {name!r}"}
    except Exception as exc:
        logger.warning("Failed to create site %s: %s", name, exc)
        return {"success": False, "error": str(exc)}

    result = {
        "success": True,
        "id": data.get("id", ""),
        "name": data.get("name") or data.get("siteName") or name,
        "collection": await _resolve_collection(data, auth_token) or collection,
    }
    if result["id"]:
        _site_cache[result["id"]] = result
    return result


async def add_site_language(site_id: str, language: str, auth_token: str) -> dict:
    """Add a language/locale to a site.

    `language` should be a BCP 47 code such as "en", "fr-FR", or "de-DE".
    Returns {success, site_id, language} on success or {success, error} on failure.
    Returns a descriptive error if the language already exists (HTTP 409).
    """
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{base_url}/{site_id}/languages",
                json={"language": language},
                headers=_auth_headers(auth_token),
            )
        if resp.status_code == 404:
            return {"success": False, "error": f"Site not found: {site_id!r}"}
        if resp.status_code == 409:
            return {
                "success": False,
                "error": f"Language {language!r} already exists on site {site_id!r}",
            }
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
    except httpx.TimeoutException:
        return {"success": False, "error": f"Timed out adding language {language!r} to site {site_id!r}"}
    except Exception as exc:
        logger.warning("Failed to add language %s to site %s: %s", language, site_id, exc)
        return {"success": False, "error": str(exc)}

    return {"success": True, "site_id": site_id, "language": language, "data": data}
