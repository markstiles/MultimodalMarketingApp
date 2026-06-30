import logging

from langchain_core.tools import tool

from app.services._api_endpoint import TOOL_TIER_COMPOSITE, TOOL_TIER_DIRECT
from app.services.pages_service import (
    add_component_on_page_api,
    add_language_to_page_api,
    get_all_pages_by_site_api,
    get_allowed_components_api,
    get_components_on_page_api,
    get_page_preview_url_api,
    get_page_screenshot_api,
    set_component_datasource_api,
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
from app.services.sites_service import list_sites
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


@tool
async def search_pages(
    root_page_id: str,
    query: str,
    language: str,
) -> dict:
    """
    Search for pages whose display name contains the query string.

    Automatically escalates scope when nothing is found:
    1. Root search — scoped to root_page_id (typically the site_id).
    2. Under-home search — if root returns 0, finds the home page and searches
       its direct children. Covers the standard Site → Home → pages structure.
    The response includes a "search_scope" field ("root" or "under_home") and a
    "note" when nothing was found at either level.

    Returns up to 20 matches per page with page_id, display_name, parent_id,
    has_children, and has_presentation. If has_more is True, refine the query.

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

    # Step 1: search scoped to root_page_id (typically the site_id).
    result = await search_pages_api(root_page_id, query, language, auth_token)
    if result.get("pages"):
        result["search_scope"] = "root"
        return result

    # Step 2: find the home page so we can search one level deeper.
    # The pages search API requires rootIds, so there is no global search.
    # The typical Sitecore structure is Site → Home → [pages], meaning pages
    # like "Detail Page" are not direct children of the site root and will not
    # appear in a root-scoped search.
    home_result = await search_pages_api(root_page_id, "Home", language, auth_token)
    home_pages = [
        p for p in home_result.get("pages", [])
        if "home" in p.get("display_name", "").lower()
    ]
    if home_pages:
        home_id = home_pages[0]["page_id"]
        under_home = await search_pages_api(home_id, query, language, auth_token)
        if under_home.get("pages"):
            under_home["search_scope"] = "under_home"
            return under_home

    result["search_scope"] = "root"
    result["note"] = (
        f"No pages matching '{query}' found under the site root or home page. "
        "Call find_pages(site_id=..., query=...) to search the full site tree."
    )
    return result


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
      "wide"   Try context branch → site root → home page in sequence.
               Covers the standard Sitecore structure (Site → Home → pages) in
               up to three API calls. Use this when location is unknown (default).
      "full"   Alias for "wide" — behaves identically. Retained for compatibility.

    Args:
        site_id:         Active site identifier from session context (UUID). Never guess
                         a site name — pass the UUID directly; resolution happens internally.
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
    # The pages search API requires BOTH rootIds and searchText — there is no
    # global search.  Try the context branch first (fast path), then fall back
    # to a full site dump via the agents API with Jaccard scoring.

    # Step 1: context branch fast-path.
    if context_page_id:
        result = await search_pages_api(context_page_id, query, language, auth_token)
        if result.get("success"):
            matches = await _resolve_navigation_matches(result.get("pages", []), query_lower)
            if matches:
                return await _navigation_result(matches, query)

    # Step 2: full site dump via agents API + Jaccard scoring.
    # The xmapps search API often cannot scope to the site_id and returns 0 results.
    # Fall back to fetching all pages by site name and scoring by path similarity.
    site_name, _err = await _resolve_site_name(site_id, auth_token)
    if site_name:
        all_pages = await get_all_pages_by_site_api(
            site_name=site_name, language=language, auth_token=auth_token
        )
        if all_pages.get("success"):
            query_words = set(query_lower.split())
            scored = []
            for page in all_pages.get("pages", []):
                path = page.get("path", "") or ""
                name = page.get("name", "") or ""
                score, display_name = _path_jaccard(query_words, path, name)
                if score > 0:
                    scored.append({
                        **page,
                        "display_name": display_name,
                        "similarity": round(score, 3),
                    })
            scored.sort(key=lambda p: p["similarity"], reverse=True)
            top4 = scored[:4]
            if top4:
                # Single unambiguous match (top score clearly ahead) — navigate directly.
                if len(top4) == 1 or top4[0]["similarity"] - top4[1]["similarity"] >= 0.4:
                    best = top4[0]
                    return {
                        "success": True,
                        "navigated": True,
                        "page_id": best["page_id"],
                        "display_name": best["display_name"],
                        "pages": top4,
                    }
                # Multiple plausible matches — return top 4 for user selection.
                return {
                    "success": True,
                    "navigated": False,
                    "pages": top4,
                    "message": (
                        f"Found {len(scored)} pages matching '{query}'. "
                        "Present these as options and call navigate_to_page with the chosen page_id."
                    ),
                }

    return {
        "success": True,
        "navigated": False,
        "pages": [],
        "message": f"No page found matching '{query}'. Try a different search term.",
    }


open_page._tier = TOOL_TIER_COMPOSITE


@tool
async def navigate_to_page(page_id: str) -> dict:
    """Navigate directly to a page by its ID.

    Use this after open_page or find_pages returns multiple options and the marketer
    has selected one. Pass the page_id from the selected result — no additional
    search is needed.

    Args:
        page_id: The page ID returned by open_page or find_pages
    """
    if not page_id or not page_id.strip():
        return {"success": False, "navigated": False, "error": "page_id is required."}
    return {"success": True, "navigated": True, "page_id": page_id.strip()}


navigate_to_page._tier = TOOL_TIER_DIRECT


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

    return await delete_page_api(page_id, site_id, auth_token)


# delete_page_api is exposed=False (destructive); this is the only sanctioned call path.
delete_page._tier = TOOL_TIER_COMPOSITE


# ---------------------------------------------------------------------------
# Agent API tools — T032–T040
# ---------------------------------------------------------------------------

@tool
async def add_language_to_page(
    page_id: str,
    language: str,
) -> dict:
    """Add a language version to an existing page.

    ONLY call this tool after the marketer has explicitly confirmed the language to add.

    Args:
        page_id:  ID of the page to add a language version to
        language: Language code to add, e.g. "fr-CA", "de", "es"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}
    return await add_language_to_page_api(page_id=page_id, language=language, auth_token=auth_token)


@tool
async def get_components_on_page(
    page_id: str,
    language: str = "en",
) -> dict:
    """Retrieve all components currently placed on a page.

    Read-only — no confirmation required. Use this to understand what components
    are on a page before adding new ones or setting datasources.

    Args:
        page_id:  ID of the page
        language: Language version to retrieve components for (default "en")
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "components": [], "error": str(exc)}
    return await get_components_on_page_api(page_id=page_id, language=language, auth_token=auth_token)


@tool
async def add_component_on_page(
    page_id: str,
    component_rendering_id: str,
    placeholder_path: str,
    component_item_name: str,
    position_after_component_id: str = "",
) -> dict:
    """Add a component to a placeholder on a page.

    ONLY call this tool after the marketer has explicitly approved adding the component,
    including which component type and which placeholder location.

    Args:
        page_id:                     ID of the target page
        component_rendering_id:      Rendering/template ID of the component to add
                                     (get from get_allowed_components_by_placeholder)
        placeholder_path:            Placeholder path on the page, e.g. "/jss-main/jss-header"
        component_item_name:         Display name for the new component item
        position_after_component_id: Optional ID of an existing component to position after
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "component_id": None, "error": str(exc)}
    return await add_component_on_page_api(
        page_id=page_id,
        component_rendering_id=component_rendering_id,
        placeholder_path=placeholder_path,
        component_item_name=component_item_name,
        auth_token=auth_token,
        position_after_component_id=position_after_component_id,
    )


@tool
async def set_component_datasource(
    page_id: str,
    component_id: str,
    datasource_id: str,
    language: str = "en",
) -> dict:
    """Bind a datasource item to a component on a page.

    ONLY call this tool after the marketer has explicitly confirmed the datasource
    to bind to the component.

    Args:
        page_id:        ID of the page
        component_id:   ID of the component instance on the page
        datasource_id:  ID of the datasource item to bind
        language:       Language version (default "en")
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}
    return await set_component_datasource_api(
        page_id=page_id,
        component_id=component_id,
        datasource_id=datasource_id,
        language=language,
        auth_token=auth_token,
    )


@tool
async def get_allowed_components_by_placeholder(
    page_id: str,
    placeholder_name: str,
) -> dict:
    """Retrieve the components allowed in a specific placeholder on a page.

    Read-only — no confirmation required. Call this before add_component_on_page
    to know which component rendering IDs are valid for a given placeholder.

    Args:
        page_id:          ID of the page
        placeholder_name: Placeholder path, e.g. "jss-main" or "/jss-main/jss-header"
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "components": [], "error": str(exc)}
    return await get_allowed_components_api(
        page_id=page_id,
        placeholder_name=placeholder_name,
        auth_token=auth_token,
    )


@tool
async def get_page_preview_url(
    page_id: str,
    language: str = "",
) -> dict:
    """Get the preview URL for a page so the marketer can review it in a browser.

    Read-only — no confirmation required.

    Args:
        page_id:  ID of the page
        language: Language version (optional — omit for the default language)

    Returns {success, page_id, preview_url}.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "preview_url": None, "error": str(exc)}
    return await get_page_preview_url_api(page_id=page_id, auth_token=auth_token, language=language)


@tool
async def get_page_screenshot(
    page_id: str,
    version: int = 1,
    language: str = "en",
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Capture a screenshot of a page as a base64-encoded image.

    Use this when the marketer wants to visually review a page without leaving
    the chat, or before publishing to confirm layout and content look correct.
    Read-only — no confirmation required.

    Args:
        page_id:  ID of the page to screenshot
        version:  Page version number (default 1)
        language: Language version (default "en")
        width:    Viewport width in pixels (optional)
        height:   Viewport height in pixels (optional)

    Returns {success, page_id, screenshot_base64, type, encoding, full_page, timestamp}.
    The screenshot_base64 field contains the raw base64 image data.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "screenshot_base64": None, "error": str(exc)}
    return await get_page_screenshot_api(
        page_id=page_id,
        auth_token=auth_token,
        version=version,
        language=language,
        width=width,
        height=height,
    )


async def _resolve_site_name(site_id: str, auth_token: str) -> tuple[str | None, str | None]:
    """Resolve site_id (UUID or display name) to the Agents API site name.

    Resolution order:
      1. Exact case-insensitive match on the `id` field (UUID from session context).
      2. Exact case-insensitive match on the `name` field (fallback when model passes display name).

    Returns (site_name, None) on success or (None, error_message) on failure.
    """
    sites_result = await list_sites(auth_token)
    if not sites_result.get("success"):
        return None, f"Could not list sites: {sites_result.get('error')}"

    sites = sites_result.get("sites", [])
    sid_lower = site_id.strip().lower()

    # 1. UUID match
    match = next((s for s in sites if s.get("id", "").lower() == sid_lower), None)
    if match:
        return match["name"], None

    # 2. Name match — model may pass display name instead of UUID
    match = next((s for s in sites if s.get("name", "").lower() == sid_lower), None)
    if match:
        return match["name"], None

    available = ", ".join(f'"{s["name"]}"' for s in sites[:6])
    return None, (
        f"Site {site_id!r} not found. Call list_all_sites to get the correct site_id. "
        f"Known sites: {available}"
    )


def _path_jaccard(query_words: set[str], path: str, name: str = "") -> tuple[float, str]:
    """Score a page path against query words using Jaccard similarity.

    Each path segment (split on '/') is tokenized by splitting on '-'.  The
    segment with the highest Jaccard score against the query is used.

    The root path "/" has no segments; it is treated as "Home" by Sitecore convention
    and scored against {"home"} so that searching for "Home" resolves correctly.

    The optional `name` parameter supplies the API-provided display name, which is
    preferred over the path-reconstructed label when available.

    Example: query="Detail Page", path="/Landing-Page/Detail-Page"
      segment "Detail-Page" → words {"detail","page"} → Jaccard = 2/2 = 1.0
    """
    segments = [s for s in path.split("/") if s] if path else []

    if not segments:
        # Root path "/" is the Home page by Sitecore convention.
        seg_words = {"home"}
        union = query_words | seg_words
        score = len(query_words & seg_words) / len(union) if union else 0.0
        return score, name or "Home"

    best_score = 0.0
    best_label = name or segments[-1].replace("-", " ").title()

    for seg in segments:
        seg_words = set(seg.lower().replace("-", " ").split())
        intersection = len(query_words & seg_words)
        union = len(query_words | seg_words)
        score = intersection / union if union else 0.0
        if score > best_score:
            best_score = score
            # Prefer the API name; only fall back to path reconstruction if absent.
            best_label = name or seg.replace("-", " ").title()

    return best_score, best_label


@tool
async def find_pages(
    site_id: str,
    query: str,
    language: str = "en",
) -> dict:
    """Find pages across the entire site using path-based Jaccard similarity scoring.

    Use this when search_pages returns no results. Fetches every page on the site
    and ranks by how closely each page's path segments match the query words.

    Always pass the `site_id` from session context (UUID). Never guess a site name —
    the tool resolves the correct identifier internally. If site_id is unknown, call
    list_all_sites first.

    Args:
        site_id:  Site identifier from session context (UUID or value from list_all_sites)
        query:    Page name to search for, e.g. "Detail Page"
        language: Language code (default "en")
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "pages": [], "error": str(exc)}

    # Resolve site name from site_id (UUID or display name).
    site_name, err = await _resolve_site_name(site_id, auth_token)
    if not site_name:
        return {"success": False, "pages": [], "error": err}

    # Fetch all pages.
    all_pages_result = await get_all_pages_by_site_api(
        site_name=site_name, language=language, auth_token=auth_token
    )
    if not all_pages_result.get("success"):
        return all_pages_result

    # Score each page by Jaccard similarity between query words and path segments.
    query_words = set(query.strip().lower().split())
    scored: list[dict] = []
    for page in all_pages_result.get("pages", []):
        path = page.get("path", "") or ""
        name = page.get("name", "") or ""
        score, display_name = _path_jaccard(query_words, path, name)
        if score > 0:
            scored.append({
                **page,
                "display_name": display_name,
                "similarity": round(score, 3),
            })

    scored.sort(key=lambda p: p["similarity"], reverse=True)
    return {
        "success": True,
        "pages": scored,
        "total_count": len(scored),
        "site_name": site_name,
    }


find_pages._tier = TOOL_TIER_COMPOSITE


@tool
async def get_all_pages_by_site(
    site_id: str,
    language: str = "en",
) -> dict:
    """Retrieve a flat list of every page on a site.

    Read-only — no confirmation required. Useful for auditing a full site structure
    or showing a complete page list.

    Always pass the `site_id` from session context (the UUID the editor provides).
    Never guess a site name — the tool resolves the correct Agents API identifier
    internally. If site_id is unknown, call list_all_sites first.

    Args:
        site_id:  Site identifier from session context (UUID or value from list_all_sites)
        language: Language code (default "en")

    Returns {success, pages, total_count} where each page has {page_id, name, path, language}.
    """
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "pages": [], "error": str(exc)}

    site_name, err = await _resolve_site_name(site_id, auth_token)
    if not site_name:
        return {"success": False, "pages": [], "error": err}

    return await get_all_pages_by_site_api(
        site_name=site_name,
        language=language,
        auth_token=auth_token,
    )
