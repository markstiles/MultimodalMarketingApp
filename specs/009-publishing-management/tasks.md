# Tasks: Publishing Management

**Input**: Design documents from `specs/009-publishing-management/`

**Prerequisites**: spec.md ✅

**Organization**: Phase 1 covers the service layer that has been implemented. Phase 2 covers the tool client layer and registration that is not yet built.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)

---

## Phase 1: Publishing Service Layer (Implemented)

**Purpose**: All functions in this phase exist in `backend/app/services/publishing_service.py`. The service layer is complete but no `@tool` wrappers or `tools.py` registrations exist yet.

- [X] T001 Add `create_publishing_job` service function — `POST /authoring/publishing/v1/jobs`; creates a publishing job with configurable options (item, site, or republish scope); `backend/app/services/publishing_service.py`
- [X] T002 Add `get_publishing_job` service function — `GET /authoring/publishing/v1/jobs/{id}`; retrieves a single job by ID including status and statistics; `backend/app/services/publishing_service.py`
- [X] T003 Add `list_publishing_jobs` service function — `GET /authoring/publishing/v1/jobs`; lists jobs with optional source/status filters and offset pagination; `backend/app/services/publishing_service.py`
- [X] T004 Add `get_publishing_summary` service function — `GET /authoring/publishing/v1/jobs/summary`; returns job counts by status (queued, running, completed, failed, canceled, canceling); `backend/app/services/publishing_service.py`
- [X] T005 Add `cancel_publishing_job` service function — `POST /authoring/publishing/v1/jobs/{jobId}/cancel`; cancels a queued or running job (marked `exposed=False` — needs @tool wrapper in Phase 2); `backend/app/services/publishing_service.py`
- [X] T006 Add `get_publishing_permissions` service function — `GET /authoring/publishing/v1/jobs/permissions`; retrieves current user publishing permissions (internal utility, not exposed as a tool); `backend/app/services/publishing_service.py`

---

## Phase 2: Publishing Tool Client Layer (Gap — Not Yet Built)

**Purpose**: Create `@tool`-decorated wrapper functions and register them in `tools.py`. The service layer exists; this phase wires it to the LangGraph tool surface.

- [X] T007 [P] Create `backend/app/clients/publishing_api.py` — module to house all `@tool`-decorated publishing functions
- [X] T008 [P] Implement `publish_content` @tool in `backend/app/clients/publishing_api.py` — wraps `create_publishing_job`; user-facing name `publish_content`; confirmation-gated; supports item-scoped, site-scoped, and republish modes
- [X] T009 [P] Implement `get_publishing_job` @tool in `backend/app/clients/publishing_api.py` — read-only, no confirmation required
- [X] T010 [P] Implement `list_publishing_jobs` @tool in `backend/app/clients/publishing_api.py` — read-only, supports source and status filters
- [X] T011 [P] Implement `get_publishing_summary` @tool in `backend/app/clients/publishing_api.py` — read-only, returns job counts by status
- [X] T012 `cancel_publishing_job` — skipped intentionally; service marked `exposed=False`; not surfaced to the LLM
- [X] T013 Register `publish_content`, `get_publishing_job`, `list_publishing_jobs`, `get_publishing_summary` in `backend/app/clients/tools.py`
- [X] T014 Add `publish_content` to `_WRITE_TOOLS` in `backend/app/services/chat_service.py`
