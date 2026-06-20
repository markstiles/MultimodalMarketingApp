# Tool Contracts: Guided Page Creation & Management

**Feature**: 011-page-management | **Date**: 2026-06-19

These are the LangChain `@tool` function signatures and return shapes for `backend/app/clients/pages_api.py`. All shapes reference the TypedDict definitions in [data-model.md](../data-model.md).

---

## Read-Only Tools

### `search_pages`

Find pages by name within the active site.

```python
@tool
async def search_pages(
    site_id: str,       # Active site identifier from session context
    environment: str,   # Active environment identifier from session context
    query: str,         # Search term to match against page display names
    language: str,      # Language code, e.g. "en" — defaults to site primary language
) -> PageSearchResult:
    """
    Search for pages in the active site whose display name contains the query string.
    Returns up to 20 matching pages with their location in the site hierarchy.
    If has_more is True, ask the marketer to refine the search rather than paginating.
    """
```

**Returns**: `PageSearchResult` — `success`, `pages` (list of `PageSummary`), `total_count`, `has_more`, `error`

---

### `get_page_state`

Retrieve the current state of a specific page.

```python
@tool
async def get_page_state(
    site_id: str,
    environment: str,
    page_id: str,       # Pages API page identifier
) -> PageState | dict:
    """
    Retrieve the current state of a page: display name, parent path, template, language,
    version number, workflow state, and whether it is live on Sitecore Edge.
    Use this to answer marketer questions about a page's status without making changes.
    """
```

**Returns**: `PageState` on success; `{"success": False, "error": str}` on failure

---

### `get_insert_options`

List available page types (templates) for creating a child page under a given parent.

```python
@tool
async def get_insert_options(
    site_id: str,
    environment: str,
    parent_page_id: str,  # The page under which a new child page will be created
) -> dict:
    """
    Retrieve the list of page types (templates) that can be created as child pages
    under the specified parent. Always call this before presenting a page creation plan —
    the marketer must choose from the available types for the selected parent location.
    Returns an empty list if no templates are available (creation not permitted there).
    """
```

**Returns**: `{"success": bool, "insert_options": list[InsertOption], "error": str | None}`

---

## Write Tools — Confirmation Required Before Calling

> All write tools MUST only be called after the marketer has explicitly approved the operation.
> The `page-management.md` instruction overlay governs when these tools may be invoked.

---

### `create_page`

Create a new page at a specified location.

```python
@tool
async def create_page(
    site_id: str,
    environment: str,
    parent_page_id: str,  # ID of the parent page
    template_id: str,     # Template ID from get_insert_options result
    display_name: str,    # Human-readable page name chosen by the marketer
    language: str,        # Language code for the new page
) -> PageWriteResult:
    """
    Create a new page as a child of the specified parent page using the selected template.
    ONLY call this tool after the marketer has explicitly approved the creation plan
    (parent path, page type, and display name). Returns the new page's ID and display name.
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id`, `display_name`, `version: None`, `error`

---

### `rename_page`

Rename an existing page.

```python
@tool
async def rename_page(
    site_id: str,
    environment: str,
    page_id: str,
    new_display_name: str,
) -> PageWriteResult:
    """
    Rename a page to a new display name.
    ONLY call this tool after the marketer has confirmed the target page and the new name.
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id`, `display_name` (new name), `version: None`, `error`

---

### `duplicate_page`

Create a copy of an existing page as a sibling.

```python
@tool
async def duplicate_page(
    site_id: str,
    environment: str,
    page_id: str,
) -> PageWriteResult:
    """
    Duplicate a page, creating a copy as a sibling with a system-generated name.
    ONLY call this tool after the marketer has confirmed the duplication.
    Returns the new (duplicate) page's ID and display name.
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id` (new page), `display_name`, `version: None`, `error`

---

### `update_page_fields`

Update specific field values on a page.

```python
@tool
async def update_page_fields(
    site_id: str,
    environment: str,
    page_id: str,
    fields: dict[str, str],  # {field_key: new_value} — field keys as used by the Pages API
    language: str,
) -> PageWriteResult:
    """
    Update one or more field values on a page. Only the specified fields are changed;
    all other fields remain unchanged.
    ONLY call this tool after the marketer has confirmed the target page, field name(s),
    and new value(s).
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id`, `display_name`, `version: None`, `error`

---

### `create_page_version`

Create a new version of a page.

```python
@tool
async def create_page_version(
    site_id: str,
    environment: str,
    page_id: str,
    language: str,
) -> PageWriteResult:
    """
    Create a new draft version of a page in the specified language.
    ONLY call this tool after the marketer has confirmed the version creation.
    Returns the new version number.
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id`, `display_name`, `version` (new version number), `error`

---

### `delete_page`

Permanently delete a page.

```python
@tool
async def delete_page(
    site_id: str,
    environment: str,
    page_id: str,
) -> PageWriteResult:
    """
    Permanently delete a page. This action is IRREVERSIBLE.
    ONLY call this tool after the marketer has received an explicit warning that deletion
    cannot be undone AND has confirmed they want to proceed.
    """
```

**Returns**: `PageWriteResult` — `success`, `page_id: None`, `display_name: None`, `version: None`, `error`
