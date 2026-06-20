# Implementation Plan: Guided Page Creation & Management

**Branch**: `011-page-management` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-page-management/spec.md`

## Summary

Add guided page creation and management to the Sitecore chat assistant using the Sitecore XM Cloud Pages API (`https://xmapps-api.sitecorecloud.io/api/v1/pages/`). The assistant guides marketers through a structured conversation (parent → type → name → confirm) before creating any page. All write operations (create, rename, duplicate, update fields, delete) require explicit marketer confirmation enforced by the Track B instruction overlay. The feature adds nine new LangChain `@tool` functions in `clients/pages_api.py` backed by an async HTTP service layer in `services/pages_service.py`, registers them in the shared `clients/tools.py` registry, and ships a `page-management.md` instruction overlay. A shared `services/sitecore_auth.py` utility is extracted to eliminate the duplicate token-acquisition logic currently in `content_workflow_service.py`.

## Technical Context

**Language/Version**: Python 3.12 (unchanged)

**Primary Dependencies**:
- FastAPI + existing infrastructure (unchanged)
- LangGraph + LangChain (unchanged)
- SQLModel (unchanged — no new tables)
- `httpx` (already in use — no new package)

**New Track A client** (`backend/app/clients/`):
- `pages_api.py` — NEW: nine `@tool` functions for page operations

**New shared auth utility** (`backend/app/services/`):
- `sitecore_auth.py` — NEW: shared `get_sitecore_automation_token()` with in-process caching; eliminates duplicate token logic currently in `content_workflow_service.py`

**New Track A service helper** (`backend/app/services/`):
- `pages_service.py` — NEW: async `httpx` client that calls the Pages API; imported by `pages_api.py` tool functions

**New Track B overlay** (`backend/instructions/tasks/`):
- `page-management.md` — NEW: guided page creation and management instruction overlay

**Refactor** (minimal, non-breaking):
- `content_workflow_service.py` — update to import `get_sitecore_automation_token` from `sitecore_auth.py` instead of defining it locally

**New env vars**:
- `SITECORE_PAGES_API_BASE_URL` — base URL for the Pages API (default: `https://xmapps-api.sitecorecloud.io/api/v1/pages`)

**Existing env vars reused** (no new credentials):
- `SITECORE_CLIENT_ID_AUTOMATION` — automation client ID for Auth0 token
- `SITECORE_CLIENT_SECRET_AUTOMATION` — automation client secret

**Storage**: PostgreSQL on Railway (unchanged); no new tables. All page data is retrieved live from the Pages API.

**Testing**: pytest (existing framework)

**Target Platform**: Railway (existing deployment)

**Project Type**: Web service (Python FastAPI backend extension)

**Performance Goals**:
- Page search, state retrieval, and insert options: ≤ 2 seconds (SC-004, SC-005)
- Page write operations (create, rename, duplicate, update fields, delete): ≤ 5 seconds

**Constraints**:
- No Sitecore page write without explicit marketer confirmation (Constitution Principle I; FR-013)
- All Pages API calls wrapped in `clients/` as `@tool` functions (Constitution Principle VI)
- Guided conversation flow governed by Track B overlay — no task logic in Python (Constitution Principle IV)
- Auth token acquisition centralized in `sitecore_auth.py` (DRY — global CLAUDE.md coding principles)

**Scale/Scope**: Per-site page operations; single page created/modified per confirmation in v1

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle IV) | ✅ PASS | Guided conversation flow (parent → type → name → confirm) lives entirely in `page-management.md` overlay; no task logic in Python |
| No Sitecore write without user confirmation (Principle I) | ✅ PASS | FR-013 requires explicit confirmation for all write operations; `@tool` docstrings mark write tools "ONLY call after explicit marketer approval"; overlay enforces the confirmation step |
| New integrations use typed API client layer (Principle VI) | ✅ PASS | `pages_api.py` in `backend/app/clients/`; all Pages API HTTP calls in `pages_service.py`; no inline HTTP calls from graph nodes or route handlers |
| New task behaviors in `instructions/tasks/*.md` (Principle IV) | ✅ PASS | `page-management.md` overlay governs guided creation flow, disambiguation logic, confirmation prompts, and deletion warnings |
| No profile-switching logic (Principle IV) | ✅ PASS | Additive overlay only; base identity and guardrails unchanged |
| Guardrail coverage verified (Principle II) | ✅ PASS | Page creation and management are core Sitecore XM Cloud operations — explicitly in-scope topics; no guardrail expansion required |
| Memory writes use correct store (Principle V) | ✅ PASS | No new database tables; page data retrieved live from Pages API on demand |
| Database models use SQLModel (Technology Standards) | ✅ N/A | No new database tables required for this feature |
| LLM calls through `clients/llm.py` only (Technology Standards) | ✅ PASS | No new LLM clients; existing graph and model node unchanged |
| New multi-step workflows in LangGraph (Technology Standards) | ✅ PASS | No new graph needed — guided creation flow is encoded in the Track B overlay, driven by the existing chat graph; multi-step coordination is conversational, not a separate state machine |
| New tools bound via `.bind_tools()` in `clients/` (Technology Standards) | ✅ PASS | `pages_api.py` tools registered in `tools.py` via `get_all_tools()` list |
| MLflow tracing on all LLM/LangGraph paths (Principle VII) | ✅ PASS | Inherits from `mlflow.langchain.autolog()` called at startup; new tool calls automatically traced |

## Project Structure

### Documentation (this feature)

```text
specs/011-page-management/
├── plan.md              # This file
├── research.md          # Phase 0 technical decisions
├── data-model.md        # Runtime data shapes for Pages API responses
├── quickstart.md        # End-to-end validation guide
├── contracts/
│   └── tool-contracts.md  # @tool function signatures and return shapes
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (additions to existing layout)

```text
backend/
├── app/
│   ├── clients/
│   │   ├── pages_api.py              # NEW: @tool functions for page operations
│   │   └── tools.py                  # MODIFIED: add pages_api tools to get_all_tools()
│   └── services/
│       ├── sitecore_auth.py          # NEW: shared get_sitecore_automation_token() utility
│       ├── pages_service.py          # NEW: async httpx client for Pages API
│       └── content_workflow_service.py  # MODIFIED: import token util from sitecore_auth.py
├── instructions/
│   └── tasks/
│       └── page-management.md        # NEW: Track B guided page creation overlay
└── tests/
    └── test_pages_api.py             # NEW
```

**Structure Decision**: Minimal extension of the existing four-layer architecture. `pages_service.py` handles all async HTTP calls to the Pages API; `pages_api.py` exposes them as `@tool` functions bound to the existing LangGraph graph. The `sitecore_auth.py` extraction is a small DRY refactor — it centralizes the shared automation token-acquisition pattern used by both `content_workflow_service.py` (spec 007) and the new `pages_service.py`, consistent with the DRY principle in the global CLAUDE.md.

## Complexity Tracking

> No constitution violations. All gates pass without exceptions.
