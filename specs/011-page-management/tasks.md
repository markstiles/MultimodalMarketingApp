# Tasks: Guided Page Creation & Management

**Input**: Design documents from `specs/011-page-management/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/tool-contracts.md ✅ | quickstart.md ✅

**Organization**: Tasks are grouped by user story. US1 (guided creation) and US2 (page management) are P1 and can be worked in order. US3 (search flow) is P2. The foundational phase must complete before any user story work begins.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Verify prerequisites and complete env configuration.

- [X] T001 Verify `SITECORE_PAGES_API_BASE_URL` is present in `.env.example` and `docker/.env.example` (add to docker env file if missing) — `.env.example` / `docker/.env.example`
- [X] T002 Verify `SITECORE_PAGES_API_BASE_URL` is documented in any Railway or deployment environment config

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared auth utility, base HTTP client, and page search tool — required by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Create `backend/app/services/sitecore_auth.py` — implement `get_sitecore_automation_token() -> str` with in-process `_token_cache` dict (refresh 60s before expiry); copies the existing cache/Auth0 pattern from `content_workflow_service.py` but without any media-specific logic
- [X] T004 Refactor `backend/app/services/content_workflow_service.py` — remove the local `_token_cache` and `get_sitecore_media_auth_token()` function; replace all call sites with `from app.services.sitecore_auth import get_sitecore_automation_token`; keep a one-line alias `get_sitecore_media_auth_token = get_sitecore_automation_token` if any external import relies on the old name
- [X] T005 Create `backend/app/services/pages_service.py` — async httpx functions: `search_pages_api(site_id, environment, query, language, base_url) -> dict` calling `GET {base_url}/search`; implement `_get_base_url() -> str` helper that reads `SITECORE_PAGES_API_BASE_URL` env var; all functions accept `auth_token: str` parameter; return typed dicts matching `PageSearchResult` and `PageSummary` shapes from data-model.md
- [X] T006 Implement `search_pages` @tool in `backend/app/clients/pages_api.py` — accepts `site_id`, `environment`, `query`, `language`; calls `get_sitecore_automation_token()` then `pages_service.search_pages_api()`; returns `PageSearchResult`; returns up to 20 results with `has_more` flag per research Decision 5; match docstring in contracts/tool-contracts.md exactly
- [X] T007 Register `search_pages` in `backend/app/clients/tools.py` — add import and include in `get_all_tools()` return list

**Checkpoint**: `search_pages` tool is callable from the LangGraph graph. Auth refactor passes existing behavior for content workflow tools.

---

## Phase 3: User Story 1 — Guided Page Creation (Priority: P1) 🎯 MVP

**Goal**: Marketer can describe a page, get guided through parent selection and page type selection, review a creation plan, and create the page after explicit confirmation.

**Independent Test**: Quickstart Scenario 1 — ask assistant to create "Summer Campaign" under Blog; verify insert options appear before creation plan; verify creation only after `"yes"`.

- [X] T008 [P] Add `get_insert_options_api(parent_page_id, auth_token, base_url) -> dict` to `backend/app/services/pages_service.py` — calls `GET {base_url}/{parent_page_id}/insertoptions`; returns `{"success": bool, "insert_options": list[InsertOption], "error": str | None}`
- [X] T009 [P] Add `create_page_api(site_id, parent_page_id, template_id, display_name, language, auth_token, base_url) -> dict` to `backend/app/services/pages_service.py` — calls `POST {base_url}/` with JSON body; returns `PageWriteResult`
- [X] T010 [P] [US1] Implement `get_insert_options` @tool in `backend/app/clients/pages_api.py` — match signature and docstring in contracts/tool-contracts.md; calls `pages_service.get_insert_options_api()`; returns empty `insert_options` list (not an error) when parent has no allowed templates
- [X] T011 [P] [US1] Implement `create_page` @tool in `backend/app/clients/pages_api.py` — match signature and docstring in contracts/tool-contracts.md; docstring MUST include "ONLY call this tool after the marketer has explicitly approved the creation plan"; calls `pages_service.create_page_api()`
- [X] T012 [US1] Register `get_insert_options` and `create_page` in `backend/app/clients/tools.py` — add imports and append to `get_all_tools()` return list
- [X] T013 [US1] Create `backend/instructions/tasks/page-management.md` — guided creation flow overlay covering: (1) ask for parent location before any action, (2) call `search_pages` to find parent page ID, (3) call `get_insert_options` and present types to marketer, (4) gather display name, (5) present full creation plan (parent path, type, name) for confirmation, (6) call `create_page` only after marketer approves; include session context note (site_id, environment, language sourced from active session)

**Checkpoint**: Guided page creation works end-to-end. The assistant asks for parent and type before proposing creation, and calls `create_page` only after explicit confirmation.

---

## Phase 4: User Story 2 — Page Management (Priority: P1)

**Goal**: Marketer can get page state, rename, duplicate, update fields, create versions, and delete pages — all with explicit confirmation before each write.

**Independent Test**: Quickstart Scenarios 3–6 — rename, state retrieval, delete with warning, version creation.

- [X] T014 [P] Add `get_page_state_api(page_id, auth_token, base_url) -> dict` to `backend/app/services/pages_service.py` — calls `GET {base_url}/{page_id}/state`; returns `PageState` shape from data-model.md
- [X] T015 [P] Add `rename_page_api`, `duplicate_page_api`, `update_page_fields_api`, `create_page_version_api`, `delete_page_api` to `backend/app/services/pages_service.py` — each calls the corresponding Pages API endpoint per data-model.md endpoint mapping table; all return `PageWriteResult`
- [X] T016 [P] [US2] Implement `get_page_state` @tool in `backend/app/clients/pages_api.py` — match signature and docstring in contracts/tool-contracts.md; read-only, no confirmation required
- [X] T017 [P] [US2] Implement `rename_page`, `duplicate_page`, `update_page_fields`, `create_page_version`, `delete_page` @tools in `backend/app/clients/pages_api.py` — match signatures and docstrings in contracts/tool-contracts.md; each write tool docstring MUST include "ONLY call this tool after the marketer has explicitly approved"; `delete_page` docstring MUST include "IRREVERSIBLE"
- [X] T018 [US2] Register `get_page_state`, `rename_page`, `duplicate_page`, `update_page_fields`, `create_page_version`, `delete_page` in `backend/app/clients/tools.py`
- [X] T019 [US2] Extend `backend/instructions/tasks/page-management.md` — add management overlay sections: (1) rename: confirm target page + new name before calling `rename_page`; (2) duplicate: confirm target before calling `duplicate_page`, present new page ID in response; (3) update fields: confirm page + field name + new value before calling `update_page_fields`; (4) version: confirm page + language before calling `create_page_version`, present new version number; (5) delete: present IRREVERSIBLE WARNING explicitly, require second explicit confirmation before calling `delete_page`; (6) state: call `get_page_state` directly, no confirmation needed

**Checkpoint**: All page management operations work. Every write tool is confirmation-gated by the overlay. Delete shows an irreversibility warning before confirming.

---

## Phase 5: User Story 3 — Page Search Flow (Priority: P2)

**Goal**: Marketer can search for pages by name as a standalone action, with disambiguation when multiple results are returned.

**Independent Test**: Quickstart Scenario 2 — search for "campaign", verify results include display name and parent path; search for "Home", verify disambiguation prompt.

- [X] T020 [US3] Extend `backend/instructions/tasks/page-management.md` — add standalone search flow: (1) when marketer asks to "find" or "search for" pages without a follow-up action, call `search_pages` and present results as a list with display name and parent path; (2) when `has_more: true`, tell marketer "there are more results — try a more specific search term"; (3) when results list has multiple entries and marketer wants to act on one, ask them to confirm which page they mean before calling any write tool; (4) when no results found, offer to create a new page instead

**Checkpoint**: Search works as a standalone capability. Disambiguation is triggered when multiple pages share the same name. `has_more` surfaces gracefully.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T021 [P] Add unit tests for all 9 `@tool` functions in `backend/tests/test_pages_api.py` — mock `pages_service` functions; verify return shapes match contracts/tool-contracts.md TypedDicts; verify error propagation when service layer raises; tests MUST NOT require a live Pages API
- [X] T022 [P] Add unit tests for `get_sitecore_automation_token()` in `backend/tests/test_sitecore_auth.py` — verify cache hit (no second Auth0 call within expiry window), cache miss (token re-fetched after expiry), and missing env var raises `RuntimeError`
- [ ] T023 Run quickstart.md Scenarios 1–8 against a live Sitecore XM Cloud environment and record pass/fail results; Scenario 8 (auth regression) must pass before marking T004 complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational completion (T003–T007)
- **US2 (Phase 4)**: Depends on Foundational completion; can run in parallel with US1 after T007
- **US3 (Phase 5)**: Depends on Foundational completion; can run independently of US1 and US2
- **Polish (Phase 6)**: Depends on all desired stories being complete; T023 requires a live environment

### Within Each Phase

- T003 (sitecore_auth.py) must complete before T004 and T005
- T004 (content_workflow_service.py refactor) and T005 (pages_service.py) can run in parallel after T003
- T006 (search_pages tool) depends on T005
- Within US1: T008–T009 (service functions) can run in parallel; T010–T011 depend on them; T012 and T013 follow
- Within US2: T014–T015 (service functions) can run in parallel; T016–T017 depend on them; T018 and T019 follow

### Parallel Opportunities

```
# After T003 completes:
T004 [P]  # Refactor content_workflow_service.py
T005 [P]  # Create pages_service.py base + search_pages_api

# After T007 (search tool registered), within US1:
T008 [P]  # get_insert_options_api in pages_service.py
T009 [P]  # create_page_api in pages_service.py

# Within US2 (after T007):
T014 [P]  # get_page_state_api in pages_service.py
T015 [P]  # all 5 write API functions in pages_service.py
T016 [P]  # get_page_state @tool in pages_api.py
T017 [P]  # 5 write @tools in pages_api.py
```

---

## Implementation Strategy

### MVP (Phase 2 + Phase 3 only)

1. Complete Phase 1: Setup (verify env vars)
2. Complete Phase 2: Foundational (auth + search)
3. Complete Phase 3: US1 (guided creation)
4. **STOP and VALIDATE**: Run Quickstart Scenario 1 end-to-end
5. This gives: create any page type at any location from chat

### Full P1 Delivery (Phases 1–4)

1. MVP above
2. Complete Phase 4: US2 (all management operations)
3. Run Quickstart Scenarios 3–6
4. All P1 requirements delivered

### Complete Delivery (All Phases)

1. Full P1 Delivery above
2. Complete Phase 5: US3 (standalone search flow)
3. Complete Phase 6: Polish (tests + quickstart validation)

---

## Notes

- No new database migrations required (this feature makes no schema changes)
- `content_workflow_service.py` refactor (T004) is purely mechanical — the Auth0 call, token shape, and cache behavior are identical; only the module location changes
- The `page-management.md` overlay is built incrementally: T013 (creation flow), T019 (management flows), T020 (search flow) — each task adds to the same file; do not overwrite previous sections
- `search_pages` in the foundational phase is intentional — it is a prerequisite for both US1 (finding parent page by name) and US2 (finding a page to manage), so it must be available before either story's tools are registered
