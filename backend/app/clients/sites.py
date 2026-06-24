import logging

from langchain_core.tools import tool

from app.services.sites_service import (
    add_environment_language as _svc_add_language,
    create_collection as _svc_create_collection,
    create_site as _svc_create_site,
    delete_environment_language as _svc_delete_language,
    delete_site as _svc_delete_site,
    get_environment_languages as _svc_get_env_languages,
    get_site_info,
    get_site_languages as _svc_get_languages,
    get_site_templates as _svc_get_templates,
    list_collections as _svc_list_collections,
    list_sites as _svc_list_sites,
    set_language_fallback as _svc_set_fallback,
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
    If the user is choosing a language, you MUST immediately call `present_options`
    after this tool returns — do NOT write a prose list.
    Format each as: {"id": isoCode, "label": isoCode}
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
    If the user is choosing which site to work with, you MUST immediately call
    `present_options` after this tool returns — do NOT write a prose list.
    Format each site as: {"id": site_id, "label": site_name, "metadata": collection_name}
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_list_sites(auth_token)


@tool
async def get_environment_languages() -> dict:
    """
    Retrieve all languages available for selection in the current environment.

    Call this when creating a new site so the marketer can choose the primary
    language. Each entry has at minimum an isoCode (e.g. "en", "fr-FR") and a
    label. Pass the chosen isoCode as the language argument to create_marketing_site.

    Returns a list of language objects. The system automatically displays them as
    clickable buttons — do NOT call `present_options` and do NOT list them in prose.
    Wait for the user to click a language before proceeding.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "languages": [], "error": str(exc)}

    return await _svc_get_env_languages("", auth_token)


@tool
async def get_site_templates() -> dict:
    """
    Retrieve available site templates for the current environment.

    Call this FIRST before creating a site — the marketer must pick a template
    and you need its id for both validate_site_name and create_marketing_site.

    Returns a list of templates. The system automatically displays them as clickable
    buttons — do NOT call `present_options` and do NOT list them in prose. Wait for
    the user to click a template before proceeding.
    NEVER pass template_name as the template_id — the API will reject it.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "templates": [], "error": str(exc)}

    return await _svc_get_templates("", auth_token)


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

    Returns {success, pending: true, handle, name, collection} when creation has
    started — the site is NOT ready yet. Tell the user it will be ready in 1–3
    minutes and that they will be notified. Do NOT poll or call any other tools
    to check on the job — the system handles completion automatically.
    Returns success=False with a descriptive error on failure (including 409 if
    the site already exists).
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_create_site(name, collection, language, template_id, auth_token)


@tool
async def delete_marketing_site(site_id: str) -> dict:
    """
    Permanently delete a Sitecore XM Cloud site.

    This action is IRREVERSIBLE — all pages, content, and settings for the site
    will be removed. ONLY call this tool after:
      1. The user has received an explicit warning that deletion cannot be undone.
      2. The user has confirmed they want to proceed with deletion.

    Use get_site_context or list_all_sites to resolve a site name to its ID before
    calling this tool. NEVER invent a site_id.

    Args:
        site_id: Site identifier (UUID) from list_all_sites or session context

    Returns success status and the deleted site_id, or success=False with an error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_delete_site(site_id, auth_token)


@tool
async def list_site_collections() -> dict:
    """
    List all site collections (organisational groupings) in the current organisation.

    Use this to present available collections when creating a new site, or to
    help the marketer understand how existing sites are organised.

    Returns a list of collection objects with id, name, and description, plus a count.
    The system automatically displays them as clickable buttons — do NOT call
    `present_options` and do NOT list them in prose. Wait for the user to click a
    collection before proceeding.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "collections": [], "error": str(exc)}

    return await _svc_list_collections(auth_token)


@tool
async def create_site_collection(name: str) -> dict:
    """
    Create a new, empty site collection (organisational grouping).

    Use this when the marketer wants to create a standalone collection before
    adding sites to it. This is an alternative to letting create_marketing_site
    auto-create the collection — prefer this explicit path when the collection
    should exist independently first.

    NOTE: Sitecore may return a 409 "already exists" error for a collection that
    was previously auto-created as a side effect of a site creation, even if the
    collection does not yet appear in list_site_collections. If that happens, call
    list_site_collections to confirm — the collection should be visible within a
    few seconds.

    Args:
        name: URL-safe collection name confirmed by the marketer (e.g. "acme-corp")

    Returns {success, id, name} on success or {success, error} on failure.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_create_collection(name, auth_token)


@tool
async def remove_language_from_site(language: str) -> dict:
    """
    Remove a language/locale from the environment.

    Languages are managed at the environment level, not per-site. Use when a
    language was added in error or a locale is being retired.
    The language must have no published content before it can be removed.

    This action is IRREVERSIBLE for that language's content. ONLY call after the
    marketer has confirmed they want to remove the language.

    Args:
        language: BCP 47 language/locale code to remove (e.g. "fr-FR", "de-DE")

    Returns success status and the removed language code, or success=False with
    a descriptive error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_delete_language(language, auth_token)


@tool
async def add_language_to_site(language: str) -> dict:
    """
    Add a language/locale to the environment.

    Languages are managed at the environment level, not per-site. Use when
    enabling a new locale for multilingual sites. The language must be a BCP 47
    code (e.g. "en", "fr-FR", "de-DE", "ja-JP").

    Returns an error if the language is already configured in the environment.

    After successfully adding a language, you MUST ask the marketer:
    "Would you like to set a fallback language for [language]? A fallback is used
    when content is not available in this language — Sitecore will serve content
    from the fallback instead of showing a blank page."
    - If they want one: call `get_environment_languages` (existing languages will
      appear as buttons). After the marketer clicks one, call `set_fallback_language`.
    - If they say no or skip: proceed without setting a fallback.

    Args:
        language: BCP 47 language/locale code to add (e.g. "fr-FR", "de-DE")

    Returns success status and the added language code, or success=False with
    a descriptive error.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_add_language(language, auth_token)


@tool
async def set_fallback_language(language: str, fallback_language: str) -> dict:
    """
    Set the fallback language for a language/locale in the environment.

    When content is not available in `language`, Sitecore will serve content
    from `fallback_language` instead. Call this after `add_language_to_site`
    when the marketer wants to configure a fallback.

    Use `get_environment_languages` to present the available languages as
    clickable options before calling this tool — never invent an ISO code.

    Args:
        language:          The language to configure (e.g. "fr-CA")
        fallback_language: The fallback ISO code — must be an existing environment
                           language (e.g. "fr-FR", "en"). Never use the same
                           value as `language`.

    Returns {success, language, fallback_language} on success or
    {success, error} on failure.
    """
    if language == fallback_language:
        return {"success": False, "error": "A language cannot be its own fallback."}
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await _svc_set_fallback(language, fallback_language, auth_token)
