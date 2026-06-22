import logging

from langchain_core.tools import tool

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

    Use this to obtain a valid page_id before calling get_insert_options or create_page.
    NEVER invent a page_id — always use one returned by this tool.

    How to get the first page_id when building a content tree:
      1. Use the page_id from session context as root_page_id.
      2. Call get_page_state on that page_id to find its parent_path and navigate
         up to the home/root page if needed.
      3. Then call search_pages from the home page to find sibling or child pages.

    Args:
        root_page_id: A page UUID to scope the search — use session page_id as the
                      starting point; NEVER invent this value
        query: Non-empty search term to match against page display names
        language: Language code, e.g. "en"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "pages": [], "total_count": 0, "has_more": False, "error": str(exc)}

    return await search_pages_api(root_page_id, query, language, auth_token)


@tool
async def get_insert_options(
    site_id: str,
    environment: str,
    parent_page_id: str,
    language: str,
) -> dict:
    """
    Retrieve the list of page types (templates) that can be created as child pages
    under the specified parent. Always call this before presenting a page creation plan —
    the marketer must choose from the available types for the selected parent location.
    Returns an empty insert_options list if no templates are available (creation not
    permitted at that location).

    IMPORTANT: parent_page_id must be a UUID obtained from search_pages. NEVER pass
    a string like "root", "home", or any invented value — the API will reject it.
    Call search_pages with an empty query first to find the home page ID.

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


@tool
async def create_page(
    site_id: str,
    environment: str,
    parent_page_id: str,
    template_id: str,
    display_name: str,
    language: str,
) -> dict:
    """
    Create a new page as a child of the specified parent page using the selected template.
    ONLY call this tool after the marketer has explicitly approved the creation plan
    (parent path, page type, and display name). Returns the new page's ID and display name.

    IMPORTANT: parent_page_id must be a UUID from search_pages — NEVER use "root", "home",
    or any string that was not returned by a prior search_pages call.
    template_id must be a UUID from get_insert_options — NEVER invent one.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        parent_page_id: UUID of the parent page, obtained from search_pages
        template_id: Template UUID from get_insert_options result
        display_name: Simple page label chosen by the marketer — letters, numbers,
                      hyphens, and spaces only. No slashes, angle brackets, or
                      special characters (they will be rejected by the API).
        language: Language code for the new page
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    return await create_page_api(site_id, parent_page_id, template_id, display_name, language, auth_token)


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

    return await get_page_state_api(page_id, auth_token)


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


@tool
async def duplicate_page(
    site_id: str,
    environment: str,
    page_id: str,
) -> dict:
    """
    Duplicate a page, creating a copy as a sibling with a system-generated name.
    ONLY call this tool after the marketer has confirmed the duplication.
    Returns the new (duplicate) page's ID and display name.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        page_id: Pages API identifier of the page to duplicate
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "page_id": None, "display_name": None, "version": None, "error": str(exc)}

    return await duplicate_page_api(page_id, auth_token)


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

    return await update_page_fields_api(page_id, fields, language, auth_token)


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
