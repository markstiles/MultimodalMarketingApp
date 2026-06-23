import logging

from langchain_core.tools import tool

from app.services.sites_service import (
    add_site_language as _svc_add_language,
    create_site as _svc_create_site,
    get_environment_languages as _svc_get_env_languages,
    get_site_info,
    get_site_languages as _svc_get_languages,
    get_site_templates as _svc_get_templates,
    list_sites as _svc_list_sites,
    validate_site_name as _svc_validate_name,
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
async def list_all_sites() -> dict:
    """
    List all Sitecore XM Cloud sites accessible to the current organisation.

    Use this to browse existing sites before creating a new one, or to find a
    site's id when only the name is known. Each entry includes the site's id,
    name, and collection (organisational grouping).

    Returns a list of site objects with total count, or success=False on error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_list_sites(auth_token)


@tool
async def get_environment_languages(environment_id: str) -> dict:
    """
    Retrieve all languages available for selection in the given environment.

    Call this when creating a new site so the marketer can choose the primary
    language. Each entry has at minimum an isoCode (e.g. "en", "fr-FR") and a
    label. Pass the chosen isoCode as the language argument to create_marketing_site.

    Args:
        environment_id: Environment name from session context (e.g. "Production",
                        "Default") — use the environment value from the Pages editor
                        context, or ask the marketer if unknown

    Returns a list of language objects with isoCode, label, and count.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "languages": [], "error": str(exc)}

    return await _svc_get_env_languages(environment_id, auth_token)


@tool
async def get_site_templates(environment_id: str) -> dict:
    """
    Retrieve available site templates for the given environment.

    Call this FIRST before creating a site — the marketer must pick a template
    and you need its id for both validate_site_name and create_marketing_site.

    Args:
        environment_id: Environment name from session context (e.g. "Production",
                        "Default") — use the environment value from the Pages editor
                        context, or ask the marketer if unknown

    Returns a list of templates. Each entry has:
      - template_id: the UUID to pass to validate_site_name and create_marketing_site
      - template_name: the human-readable label to show the marketer
    NEVER pass template_name as the template_id — the API will reject it.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "templates": [], "error": str(exc)}

    return await _svc_get_templates(environment_id, auth_token)


@tool
async def validate_site_name(
    site_name: str,
    language: str,
    template_id: str,
) -> dict:
    """
    Validate a proposed site name before creation.

    Call this AFTER get_site_templates and BEFORE create_marketing_site.
    Returns valid=True when the name is accepted, or valid=False with field-level
    error messages explaining why the name was rejected (e.g. already taken,
    invalid characters).

    Args:
        site_name:   Proposed URL-safe site name (e.g. "acme-q3-campaign")
        language:    isoCode from get_environment_languages (e.g. "en")
        template_id: The template_id UUID from get_site_templates — NEVER the template_name
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "valid": False, "error": str(exc)}

    return await _svc_validate_name(site_name, language, template_id, auth_token)


@tool
async def create_marketing_site(
    name: str,
    collection: str,
    template_id: str,
    language: str = "en",
) -> dict:
    """
    Create a new Sitecore XM Cloud marketing site.

    REQUIRED workflow before calling this tool:
      1. Call get_site_templates to obtain available templates and their IDs.
      2. Call get_environment_languages to obtain available languages.
      3. Present template AND language choices to the marketer and get their selections.
      4. Call validate_site_name with the confirmed name, language, and template_id.
      5. Only proceed here if validate_site_name returns valid=True.

    Supplying a collection name that does not yet exist will create a new collection
    (organisational grouping) automatically. Always confirm name, collection, and
    template with the marketer before calling — site creation cannot be undone
    through the chat.

    Call list_all_sites first to confirm the site does not already exist.

    Args:
        name:        URL-safe site name confirmed by validate_site_name
        collection:  Collection/tenant name (e.g. "acme-corp", "test")
        template_id: The template_id UUID from get_site_templates — NEVER the template_name string
        language:    isoCode from get_environment_languages (e.g. "en")

    Returns the new site's id, name, and collection on success, or
    success=False with a descriptive error (including 409 if the site exists).
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_create_site(name, collection, language, template_id, auth_token)


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
