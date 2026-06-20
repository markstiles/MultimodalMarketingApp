# Data Model: Guided Page Creation & Management

**Feature**: 011-page-management | **Date**: 2026-06-19

> No new SQLModel tables. All page data is retrieved live from the Pages API on demand.
> This document defines the runtime data shapes (Python TypedDict-compatible dicts) used
> by the `@tool` functions in `pages_api.py` and the service functions in `pages_service.py`.

---

## Pages API Base URL

All requests use:

```
SITECORE_PAGES_API_BASE_URL (default: https://xmapps-api.sitecorecloud.io/api/v1/pages)
```

Authentication: Bearer token acquired from Auth0 via `get_sitecore_automation_token()` in `sitecore_auth.py`.

---

## Runtime Data Shapes

These are Python TypedDict-compatible shapes returned by service functions and `@tool` functions. They are not database models.

### PageSummary

Returned by `search_pages` for each matching result.

```python
class PageSummary(TypedDict):
    page_id: str          # Pages API page identifier
    display_name: str     # Human-readable page name
    parent_path: str      # Path of the parent page in the site hierarchy
    template_name: str    # Template/page type display name
    is_folder: bool       # True if this item is a folder rather than a page
    site_id: str          # Site the page belongs to
```

### PageState

Returned by `get_page_state` for a specific page.

```python
class PageState(TypedDict):
    page_id: str
    display_name: str
    parent_path: str
    template_name: str
    language: str
    version: int           # Current version number
    workflow_state: str    # e.g., "Draft", "Awaiting Approval", "Approved"
    is_live: bool          # True if published to Sitecore Edge
    last_modified: str     # ISO 8601 datetime
    site_id: str
```

### InsertOption

One entry in the list returned by `get_insert_options`.

```python
class InsertOption(TypedDict):
    template_id: str       # Template ID (GUID)
    template_name: str     # Human-readable name shown to the marketer
```

### PageWriteResult

Standard success/failure shape returned by all write operations (create, rename, duplicate, update fields, delete, create version).

```python
class PageWriteResult(TypedDict):
    success: bool
    page_id: str | None    # New or existing page ID; None on failure
    display_name: str | None
    version: int | None    # Populated only for create_page_version
    error: str | None      # Human-readable error message; None on success
```

### PageSearchResult

Returned by `search_pages`, wrapping the list of matches with pagination info.

```python
class PageSearchResult(TypedDict):
    success: bool
    pages: list[PageSummary]
    total_count: int       # Total results available (may exceed len(pages))
    has_more: bool         # True if total_count > len(pages)
    error: str | None
```

---

## Entity Relationships

```
Site
 └── Page (parent_path describes position in site hierarchy)
      ├── Page (child pages — navigated via insert options and parent_id)
      │     └── ...
      └── PageVersion (version number + language)
```

---

## Pages API Endpoint Mapping

| Operation | HTTP Method | Endpoint | Key Parameters |
|-----------|------------|----------|---------------|
| Search pages | GET | `/search` | `siteId`, `search` (query string), `language` |
| Get page state | GET | `/{pageId}/state` | — |
| Get insert options | GET | `/{pageId}/insertoptions` | — |
| Create page | POST | `/` | `site`, `language`, `parent`, `template` (body) |
| Rename page | POST | `/{pageId}/rename` | `displayName` (body) |
| Duplicate page | POST | `/{pageId}/duplicate` | — |
| Update fields | POST | `/{pageId}/fields` | field key/value pairs (body) |
| Create version | POST | `/{pageId}/version` | `language` (body) |
| Delete page | DELETE | `/{pageId}` | — |
