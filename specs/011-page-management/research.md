# Research: Guided Page Creation & Management

**Feature**: 011-page-management | **Date**: 2026-06-19

---

## Decision 1: Auth token sharing across Pages API and Agents API clients

**Decision**: Extract the automation client token acquisition into a shared `backend/app/services/sitecore_auth.py` module with an in-process cache. Both `content_workflow_service.py` (spec 007) and the new `pages_service.py` import from it. The function signature is `async def get_sitecore_automation_token() -> str`, returning a cached Bearer token refreshed 60 seconds before expiry.

**Rationale**: `content_workflow_service.py` already implements token caching with a `_token_cache` dict. Copying this pattern into `pages_service.py` would be a direct DRY violation — the global CLAUDE.md coding principles require centralizing shared logic. The Auth0 call (`POST https://auth.sitecorecloud.io/oauth/token` with client credentials grant, audience `https://api.sitecorecloud.io`) is identical for both the Agents API and the Pages API. The existing implementation in `content_workflow_service.py` is correct and can be moved to `sitecore_auth.py` with a two-line import update in the service file.

**Alternatives considered**:
- Duplicate token acquisition in `pages_service.py` (rejected: direct DRY violation, risk of two caches diverging on token refresh)
- Use a class-based singleton (rejected: adds complexity; the module-level `_token_cache` dict is already working in production)
- Per-request token fetch with no cache (rejected: Auth0 rate limits; multiple tool calls per conversation turn would each trigger an Auth0 request)

---

## Decision 2: Pages API HTTP client placement and structure

**Decision**: Create `backend/app/services/pages_service.py` as a collection of plain async functions (no class), one per Pages API operation. Each function accepts typed parameters and returns a typed dict. The `@tool` functions in `pages_api.py` call these service functions — the service layer handles HTTP errors and translates them to structured error dicts; the tool layer handles the tool-call interface contract.

**Rationale**: This mirrors the existing pattern from `content_workflow_service.py` — service functions are thin async wrappers around `httpx` calls, and the `@tool` layer provides the LLM-facing interface. Keeping service functions as plain async functions (not a class) is consistent with the rest of the codebase. The two-layer split (service + tool) allows service functions to be independently unit-tested without LangChain infrastructure.

**Alternatives considered**:
- Single `pages_api.py` file with both HTTP calls and `@tool` decorators (rejected: mixes concerns; service HTTP logic becomes harder to unit-test independently)
- Use a shared `httpx.AsyncClient` singleton (deferred: not needed for v1 throughput; `httpx.AsyncClient` can be added later for connection pooling if benchmarks show it's needed)
- Reuse the existing `mcp_client.py` HTTP infrastructure (rejected: MCP client is purpose-built for MCP server connections; Pages API is a plain REST API)

---

## Decision 3: Session context (site ID, environment) sourcing for tool arguments

**Decision**: Pass `site_id` and `environment` as explicit string arguments to all `@tool` functions — the same pattern as `tenant` and `site` in `scan_content_project_status`. The LangGraph graph's active session context (set from the iframe at login) contains these values; the LLM is instructed by the overlay to pass them from session context to tool calls.

**Rationale**: The existing session context mechanism already surfaces `site_id` and `environment` to the LLM via the system prompt (set when the iframe initializes the session). Making them explicit tool arguments keeps the tool signatures self-contained and independently testable. The overlay's instructions explicitly tell the assistant to pass these values from the active session context — consistent with the `tenant`/`site` pattern established in spec 007.

**Alternatives considered**:
- Access session context from a global/thread-local in the service layer (rejected: hidden coupling; makes unit testing without a full graph context impossible)
- Accept only `page_id` and resolve site/environment server-side (rejected: the Pages API requires `siteId` as a query parameter for search; it is not derivable from `page_id` alone)

---

## Decision 4: Confirmation gate enforcement pattern

**Decision**: Write operations (`create_page`, `rename_page`, `duplicate_page`, `update_page_fields`, `delete_page`, `create_page_version`) are `@tool` functions that execute immediately when called — they do not check for a prior confirmation step in Python. The enforcement happens in the Track B overlay instruction file: the assistant is instructed to present a confirmation plan and wait for explicit marketer approval before calling any write tool. The `@tool` docstring includes the phrase "ONLY call this tool after the marketer has explicitly approved the operation" — consistent with `save_phase_artifact` from spec 007.

**Rationale**: Mixing conversation-state logic into Python `@tool` functions would require passing conversation history or a flag from the graph state into the tool, which is architecturally awkward and untestable. The Track B overlay is the correct place for confirmation-gate logic per the constitution (Principle IV: task behaviors in `instructions/tasks/*.md`, not in source code). The existing `save_phase_artifact` tool follows this exact pattern and has proven reliable in production.

**Alternatives considered**:
- Python-side guard that checks `confirmed=True` argument (rejected: adds a boolean parameter that the LLM could accidentally pass incorrectly; false security)
- A separate LangGraph "confirmation node" in the graph (rejected: over-engineering for a conversational confirmation pattern; the overlay handles this cleanly without graph changes)

---

## Decision 5: Page search result pagination strategy

**Decision**: `search_pages` returns the first page of results from the Pages API (up to 20 results). If more than 20 pages match, the tool returns a `has_more: true` flag and the total count. The overlay instructs the assistant to prompt the marketer to refine their search if `has_more` is true, rather than attempting to paginate automatically.

**Rationale**: The Pages API search endpoint returns paginated results. For the use case of finding a specific page to manage, returning the first 20 matches is almost always sufficient — marketers searching for a page to act on will typically use a specific enough query to get a short list. Automatic pagination (loading all pages until a match is found) would be slow and unnecessary. Surfacing `has_more: true` lets the overlay prompt the marketer to narrow their search.

**Alternatives considered**:
- Return all results via auto-pagination (rejected: potentially hundreds of pages; slow and context-token expensive)
- Return only the top 5 results with no pagination info (rejected: would silently hide results without telling the marketer there are more)
- Return a configurable limit (deferred to future iteration if marketers need more than 20 results)
