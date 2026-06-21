import logging

from langchain_core.tools import tool

from app.services.sites_service import (
    add_site_language as _svc_add_language,
    get_site_info,
    get_site_languages as _svc_get_languages,
)
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


@tool
async def get_site_context(site_id: str) -> dict:
    """
    Resolve the site name and collection (organization grouping) for a given site_id.

    Use this when you need to understand the site hierarchy — for example, to describe
    what collection a site belongs to, or to prepare for creating new sites or collections
    as part of a microsite deployment.

    The collection is the organizational grouping above a site (formerly called 'tenant').
    It is used to scope media library paths, brand kits, and publishing targets.

    Args:
        site_id: Site identifier from session context

    Returns site name, collection name, and full site id. Returns success=False with
    an error message if the site cannot be resolved.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "site_id": site_id}

    return await get_site_info(site_id, auth_token)


@tool
async def list_site_languages(site_id: str) -> dict:
    """
    Get all languages/locales configured for a site.

    Use this to see which languages are enabled before starting a multilingual
    campaign, or to check supported locales when preparing targeted content.
    Each language entry includes at minimum an isoCode (e.g. "en", "fr-FR").

    Args:
        site_id: Site identifier from session context

    Returns a list of language objects and total count, or success=False on error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "site_id": site_id}

    return await _svc_get_languages(site_id, auth_token)


@tool
async def add_language_to_site(site_id: str, language: str) -> dict:
    """
    Add a language/locale to a site.

    Use when enabling a new locale for a targeted campaign or preparing a
    multilingual marketing microsite. The language must be a BCP 47 code
    (e.g. "en", "fr-FR", "de-DE", "ja-JP").

    Returns an error if the language is already configured on the site.

    Args:
        site_id: Site identifier from session context
        language: BCP 47 language/locale code to add (e.g. "fr-FR", "de-DE")

    Returns success status and the added language code, or success=False with
    a descriptive error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "site_id": site_id}

    return await _svc_add_language(site_id, language, auth_token)
