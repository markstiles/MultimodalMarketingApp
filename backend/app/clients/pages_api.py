import logging

from langchain_core.tools import tool

from app.services._api_endpoint import TOOL_TIER_COMPOSITE, TOOL_TIER_DIRECT
from app.services.pages_service import (
    create_page_api,
    create_page_version_api,
    delete_page_api,
    duplicate_page_api,
    get_insert_options_api,
    get_page_state_api,
    rename_page_api,
    search_pages_api,
    update_page_fields_api,
)
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


@tool
async def search_pages(
    root_page_id: str,
    query: str,
    language: str,
) -> dict:
    """
    Search for pages whose display name contains the query string, scoped to the
    subtree rooted at root_page_id. Returns up to 20 matches with page_id,
    display_name, and parent_path. If has_more is True, refine the query.

    Use this to obtain a valid page_id before calling create_page.
    NEVER invent a page_id — always use one returned by this tool.

    BOOTSTRAPPING the home page (required before any page creation):
      - Pass root_page_id=<site_id from session context> and query="Home".
      - This returns the site's home page entry whose page_id is the root parent
        for all new pages.
      - Do NOT use the session page_id as root_page_id — it may be a stub in
        local development and will be rejected by the API.

    Args:
        root_page_id: site_id (from session context) to find the home page, or a
                      page_id returned by a previous call to scope a sub-tree search
        query: Non-empty search term — use "Home" to find the site home page
        language: Language code, e.g. "en"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "pages": [], "total_count": 0, "has_more": False, "error": str(exc)}

    return await search_pages_api(root_page_id, query, language, auth_token)


search_pages._tier = TOOL_TIER_DIRECT


@tool
async def get_insert_options(
    site_id: str,
    environment: str,
    parent_page_id: str,
    language: str,
) -> dict:
    """
    Retrieve the list of page types (templates) that can be created as child pages
    under the specified parent. Use this to show the marketer what options are
    available at a given location without creating anything.

    Note: create_page resolves template_name automatically — you only need this
    tool if you want to present the available types before asking the marketer
    to choose.

    IMPORTANT: parent_page_id must be a UUID obtained from search_pages. NEVER pass
    a string like "root", "home", or any invented value — the API will reject it.
    Call search_pages with query="Home" first to find the home page ID.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        parent_page_id: UUID of the parent page, obtained from search_pages
        language: Language code for the site, e.g. "en"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "insert_options": [], "error": str(exc)}

    return await get_insert_options_api(parent_page_id, site_id, language, auth_token)


get_insert_options._tier = TOOL_TIER_DIRECT


@tool
async def create_page(
    site_id: str,
    environment: str,
    parent_page_id: str,
    template_name: str,
    display_name: str,
    language: str,
) -> dict:
    """
    Create a new page as a child of the specified parent page.

    This is a composite tool: it automatically fetches the available page types
    for the parent location and resolves template_name to the correct template ID.
    You do NOT need to call get_insert_options first — pass a human-readable
    template name and the tool will match it.

    If template_name does not match any available type, the tool returns
    {success: False, available_templates: [...]} listing what IS available at that
    location so you can ask the marketer to choose.

    ONLY call this tool after the marketer has confirmed the parent location, page
    type, and display name.

    IMPORTANT: parent_page_id must be a UUID from search_pages — NEVER use "root",
    "home", or any string not returned by a prior search_pages call.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        parent_page_id: UUID of the parent page, from search_pages
        template_name: Human-readable page type name, e.g. "Landing Page" or
                       "Article Page". Case-insensitive. Pass any value if unsure
                       and the tool will return the list of available types.
        display_name: Simple page label — letters, numbers, hyphens, and spaces only.
                      No slashes, angle brackets, or special characters.
        language: Language code for the new page, e.g. "en"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    options_result = await get_insert_options_api(parent_page_id, site_id, language, auth_token)
    if not options_result.get("success"):
        return {
            "success": False,
            "error": f"Could not fetch page types for parent {parent_page_id!r}: {options_result.get('error')}",
        }

    templates = options_result.get("insert_options", [])
    if not templates:
        return {
            "success": False,
            "error": "No page types are available at this parent location.",
            "available_templates": [],
        }

    name_lower = template_name.lower()
    matched = next(
        (t for t in templates if t.get("template_name", "").lower() == name_lower),
        None,
    )
    if matched is None:
        matched = next(
            (t for t in templates if name_lower in t.get("template_name", "").lower()),
            None,
        )

    if matched is None:
        return {
            "success": False,
            "error": f"Page type {template_name!r} not found for this parent location.",
            "available_templates": [t.get("template_name", "") for t in templates],
        }

    return await create_page_api(
        site_id, parent_page_id, matched["template_id"], display_name, language, auth_token
    )


create_page._tier = TOOL_TIER_COMPOSITE


@tool
async def get_page_state(
    site_id: str,
    environment: str,
    page_id: str,
) -> dict:
    """
    Retrieve the current state of a page: display name, parent path, template, language,
    version number, workflow state, and whether it is live on Sitecore Edge.
    Use this to answer marketer questions about a page's status without making changes.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API page identifier
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    return await get_page_state_api(page_id, auth_token, site_id=site_id, language="")


get_page_state._tier = TOOL_TIER_DIRECT


@tool
async def rename_page(
    site_id: str,
    environment: str,
    page_id: str,
    new_display_name: str,
) -> dict:
    """
    Rename a page to a new display name.
    ONLY call this tool after the marketer has confirmed the target page and the new name.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API identifier of the page to rename
        new_display_name: New display name chosen by the marketer
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    return await rename_page_api(page_id, new_display_name, auth_token)


rename_page._tier = TOOL_TIER_DIRECT


@tool
async def duplicate_page(
    site_id: str,
    environment: str,
    page_id: str,
    new_name: str,
    language: str,
) -> dict:
    """
    Duplicate a page, creating a copy with the specified name.
    ONLY call this tool after the marketer has confirmed the page to copy and
    provided a name for the new copy.
    Returns the new (duplicate) page's ID and display name.

    Args:
        site_id:     Active site identifier from session context
        environment: Active environment identifier from session context
        page_id:     Pages API identifier of the page to duplicate
        new_name:    Display name for the duplicate page (chosen by the marketer)
        language:    Language code for the duplicated page (e.g. "en")
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    return await duplicate_page_api(page_id, site_id, new_name, language, auth_token)


duplicate_page._tier = TOOL_TIER_DIRECT


@tool
async def update_page_fields(
    site_id: str,
    environment: str,
    page_id: str,
    fields: dict,
    language: str,
) -> dict:
    """
    Update one or more field values on a page. Only the specified fields are changed;
    all other fields remain unchanged.
    ONLY call this tool after the marketer has confirmed the target page, field name(s),
    and new value(s).

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API identifier of the page to update
        fields: Dict of {field_key: new_value} pairs to update
        language: Language code for the field update
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    return await update_page_fields_api(page_id, site_id, fields, language, auth_token)


update_page_fields._tier = TOOL_TIER_DIRECT


@tool
async def create_page_version(
    site_id: str,
    environment: str,
    page_id: str,
    language: str,
) -> dict:
    """
    Create a new draft version of a page in the specified language.
    ONLY call this tool after the marketer has confirmed the version creation.
    Returns the new version number.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API identifier of the page
        language: Language code for the new version
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": page_id, "display_name": None, "version": None, "error": str(exc)}

    return await create_page_version_api(page_id, language, auth_token)


create_page_version._tier = TOOL_TIER_DIRECT


@tool
async def delete_page(
    site_id: str,
    environment: str,
    page_id: str,
) -> dict:
    """
    Permanently delete a page. This action is IRREVERSIBLE.
    ONLY call this tool after the marketer has received an explicit warning that deletion
    cannot be undone AND has confirmed they want to proceed.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API identifier of the page to delete
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    return await delete_page_api(page_id, auth_token)


# delete_page_api is exposed=False (destructive); this is the only sanctioned call path.
delete_page._tier = TOOL_TIER_COMPOSITE
