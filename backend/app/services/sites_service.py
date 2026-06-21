import logging
import os

import httpx

logger = logging.getLogger(__name__)

_site_cache: dict[str, dict] = {}


def _get_base_url() -> str:
    return os.environ.get(
        "SITECORE_SITES_API_BASE_URL",
        "https://xmapps-api.sitecorecloud.io/api/v1/sites",
    ).rstrip("/")


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


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

    # The API may return collection as a string field or as a nested object.
    raw_collection = data.get("collection") or data.get("siteCollection") or {}
    collection = (
        raw_collection if isinstance(raw_collection, str)
        else raw_collection.get("name", "")
    )

    result = {
        "success": True,
        "id": data.get("id", site_id),
        "name": data.get("name", site_id),
        "collection": collection,
    }
    _site_cache[site_id] = result
    return result


def _clear_site_cache() -> None:
    """Clear the in-process cache — used in tests."""
    _site_cache.clear()


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
