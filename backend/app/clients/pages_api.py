import logging

from langchain_core.tools import tool

from app.services._api_endpoint import TOOL_TIER_COMPOSITE, TOOL_TIER_DIRECT
from app.services.pages_service import (
    build_site_pages,
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
    subtree rooted at root_page_id. Returns up to 20 matches per page with
    page_id, display_name, parent_id, has_children, and has_presentation.
    If has_more is True, refine the query to narrow results.

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
    if not query or not query.strip():
        return {
            "success": False,
            "pages": [],
            "total_count": 0,
            "has_more": False,
            "error": "query is required. To find the home page pass query='Home'.",
        }

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
    under the specified parent.

    REQUIRED before generating any sitemap or creating multiple pages: call this
    once on the home/root page and use only the returned template names when
    planning which page types to create. Never invent template names — if a name
    does not appear in this result, it cannot be used with create_page.

    Results are cached for 120 seconds, so calling this once per parent is
    sufficient — create_page will reuse the cached result automatically.

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

    template_name MUST exactly match a name returned by get_insert_options for the
    parent location. Never invent a template name — always call get_insert_options
    first (especially before bulk creation) and use only the names it returns.

    The insert-options result is cached for 120 seconds, so repeated create_page
    calls for the same parent are efficient — no redundant API calls are made.

    If template_name does not match any available type, the tool returns
    {success: False, available_templates: [...]} listing what IS available.

    ONLY call this tool after the marketer has confirmed the parent location, page
    type, and display name.

    IMPORTANT: parent_page_id must be a UUID from search_pages — NEVER use "root",
    "home", or any string not returned by a prior search_pages call.

    Args:
        site_id: Active site identifier from session context
        environment: Active environment identifier from session context
        parent_page_id: UUID of the parent page, from search_pages
        template_name: Exact page type name from get_insert_options, e.g.
                       "Landing Page". Case-insensitive match is attempted.
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
async def create_site_pages(
    site_id: str,
    environment: str,
    home_page_id: str,
    language: str,
    pages: list[dict],
) -> dict:
    """
    Create multiple pages for a site from a sitemap specification in a single call.

    Use this instead of calling create_page repeatedly when implementing a sitemap.
    The tool handles all of the following internally:
      - Searches for each desired page by name to detect pages that already exist
        (skips them cleanly, records their IDs for child-page reference).
      - Resolves parent page IDs, including pages created earlier in the same run,
        which allows hierarchical creation in one call.
      - Fetches insert-options for each parent once and caches the result — no
        redundant API calls.
      - Auto-selects the most appropriate available template based on template_hint.
      - Creates missing pages sequentially and reports each result.

    REQUIRED before calling: call get_insert_options on the home page and present
    the available template names to the marketer. All template_hint values in the
    pages list must reference those actual template names — do not invent names.

    The pages list must be approved by the marketer before calling this tool.

    Each entry in the pages list:
        name            (required) Display name for the page.
        parent          (optional, default "home") Either "home" or the display
                        name of the parent page — either pre-existing or another
                        entry in this list. Names are matched case-insensitively.
        template_hint   (optional) Partial or full name of the desired template,
                        e.g. "Landing" or "Detail Page". If omitted or unmatched,
                        the most general available template is used.

    Multi-level hierarchy is supported. Include ALL pages (every depth level)
    in a single call. Set `parent` to the display name of the immediate parent
    page — not always "home". Order does not matter; the tool resolves parents
    across passes automatically.

    Example pages value (two levels deep):
        [
          {"name": "About Us",  "parent": "home",     "template_hint": "Landing"},
          {"name": "Services",  "parent": "home",     "template_hint": "Landing"},
          {"name": "Contact",   "parent": "home",     "template_hint": "Detail"},
          {"name": "Team",      "parent": "About Us", "template_hint": "Detail"},
          {"name": "History",   "parent": "About Us", "template_hint": "Detail"},
          {"name": "Web Design","parent": "Services", "template_hint": "Detail"}
        ]

    IMPORTANT: child pages must reference their immediate parent by display name,
    not "home". "home" is only valid for top-level pages directly under the site root.

    Args:
        site_id:       Active site identifier from session context
        environment:   Active environment identifier from session context
        home_page_id:  UUID of the site home page, from search_pages(query="Home")
        language:      Language code, e.g. "en"
        pages:         Ordered list of page specifications (see above)

    Returns created, skipped (already existed), and failed entries with reasons,
    plus a one-line summary.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "created": [], "skipped": [], "failed": []}

    return await build_site_pages(site_id, home_page_id, language, auth_token, pages)


create_site_pages._tier = TOOL_TIER_COMPOSITE


async def _resolve_navigation_matches(pages: list[dict], query_lower: str) -> list[dict]:
    return [p for p in pages if query_lower in p["display_name"].lower()]


async def _navigation_result(matches: list[dict], query: str) -> dict:
    if len(matches) == 1:
        page = matches[0]
        return {
            "success": True,
            "navigated": True,
            "page_id": page["page_id"],
            "display_name": page["display_name"],
            "pages": matches,
        }
    return {
        "success": True,
        "navigated": False,
        "pages": matches,
        "message": f"Found {len(matches)} pages matching '{query}'. Please select one.",
    }


@tool
async def open_page(
    site_id: str,
    environment: str,
    query: str,
    language: str,
    strategy: str = "wide",
    context_page_id: str = "",
) -> dict:
    """
    Navigate to an existing page in the Sitecore Pages editor.

    Use this when the marketer wants to OPEN, VIEW, GO TO, NAVIGATE TO, or LOOK AT
    a page. This is a navigation action — it NEVER creates a new page.

    Trigger phrases that indicate navigation intent (use this tool, not create_page):
      "open X", "go to X", "show me X", "take me to X", "navigate to X",
      "view X", "see X page", "load X", "switch to X", "bring up X"

    If a single match is found, the editor automatically navigates to that page.
    If multiple matches are returned, call `present_options` so the marketer can select
    one, then call `open_page` again with the exact page name.
    If no match is found, report that clearly — do NOT offer to create the page unless
    the marketer explicitly asks.

    Search strategies — ask the marketer which to use before calling:
      "local"  Search only under the currently viewed page (context_page_id). Fast.
               Best when the marketer is already inside the section they want.
               Returns no results if the page is outside the current branch.
      "wide"   BFS from the site root, first 20 items per level. One API call per
               depth level. Finds most pages on typical marketing sites (default).
      "full"   BFS from the site root, all items per level with pagination. More
               thorough for wide trees (large article/product listings). Slower.

    Args:
        site_id:         Active site identifier from session context
        environment:     Active environment identifier from session context
        query:           Page display name to search for (e.g. "About Us", "Contact", "Home")
        language:        Language code, e.g. "en"
        strategy:        Search strategy: "local", "wide" (default), or "full"
        context_page_id: Currently viewed page_id from session context. Required for
                         "local" strategy; used as a hint for "wide"/"full" to try
                         the current branch first before falling back to site root.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "navigated": False, "pages": [], "error": str(exc)}

    query_lower = query.strip().lower()
    _MAX_DEPTH = 8

    # ── local ────────────────────────────────────────────────────────────────
    if strategy == "local":
        if not context_page_id:
            return {
                "success": False,
                "navigated": False,
                "pages": [],
                "error": "Local search requires context_page_id (currently viewed page).",
            }
        result = await search_pages_api(context_page_id, query, language, auth_token)
        if not result.get("success"):
            return {"success": False, "navigated": False, "pages": [], "error": result.get("error")}
        matches = await _resolve_navigation_matches(result.get("pages", []), query_lower)
        if matches:
            return await _navigation_result(matches, query)
        return {
            "success": True,
            "navigated": False,
            "pages": [],
            "message": f"No page found matching '{query}' under the current page. Try a wider search.",
        }

    # ── wide / full ───────────────────────────────────────────────────────────
    # For both strategies, try the context branch first (one searchText call)
    # before crawling from the site root — same fast-path benefit as local.
    if context_page_id:
        result = await search_pages_api(context_page_id, query, language, auth_token)
        if result.get("success"):
            matches = await _resolve_navigation_matches(result.get("pages", []), query_lower)
            if matches:
                return await _navigation_result(matches, query)

    # BFS from site root.  Each level is one call (wide) or one-or-more calls
    # with pagination (full).  rootIds accepts a list so the full width of each
    # level is covered in a single request regardless of branching factor.
    # has_children prunes leaf nodes so we never request children of leaves.
    roots: list[str] = [site_id]

    for _ in range(_MAX_DEPTH):
        all_level_pages: list[dict] = []
        page_number = 1

        while True:
            result = await search_pages_api(roots, "", language, auth_token, page_number=page_number)
            if not result.get("success"):
                return {"success": False, "navigated": False, "pages": [], "error": result.get("error")}

            batch = result.get("pages", [])
            all_level_pages.extend(batch)

            # wide: take the first page only; full: follow has_more
            if strategy != "full" or not result.get("has_more") or not batch:
                break
            page_number += 1

        if not all_level_pages:
            break

        matches = await _resolve_navigation_matches(all_level_pages, query_lower)
        if matches:
            return await _navigation_result(matches, query)

        roots = [p["page_id"] for p in all_level_pages if p.get("has_children")]

    return {
        "success": True,
        "navigated": False,
        "pages": [],
        "message": f"No page found matching '{query}'. Try a different search term or strategy.",
    }


open_page._tier = TOOL_TIER_COMPOSITE


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
