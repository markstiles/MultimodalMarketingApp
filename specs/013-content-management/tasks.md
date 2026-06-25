# Tasks: Content Item CRUD

**Input**: Design documents from `specs/013-content-management/`

**Prerequisites**: spec.md ✅

**Organization**: Foundational phase creates the API client and service module. US1 (create), US2 (read), and US3 (update/delete) follow. US2 can begin as soon as the foundational layer is in place; US1 and US3 require service functions from the foundational phase as well.

---

## Phase 1: Setup

- [X] T001 [P] Add `SITECORE_AGENTS_API_BASE_URL` to `.env.example` if not already present — `.env.example`
- [X] T002 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `docker/.env.example` — `docker/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Create `backend/app/clients/content_api.py` — `backend/app/clients/content_api.py`
- [X] T004 Create `backend/app/services/content_service.py` — `backend/app/services/content_service.py`

---

## Phase 3: User Story 1 — Create Content Item

- [X] T005 [P] Add `create_content_item_api()` to `content_service.py` — calls `POST {base_url}/api/v1/content/create` — `backend/app/services/content_service.py`
- [X] T006 [P] Add `list_content_insert_options_api()` to `content_service.py` — calls `GET {base_url}/api/v1/content/{itemId}/insert-options` — `backend/app/services/content_service.py`
- [X] T007 Implement `create_content_item` @tool in `content_api.py` — confirmation-gated — `backend/app/clients/content_api.py`
- [X] T008 Implement `list_content_insert_options` @tool in `content_api.py` — read-only — `backend/app/clients/content_api.py`
- [X] T009 Register `create_content_item` and `list_content_insert_options` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 4: User Story 2 — Read Content Items

- [X] T010 [P] Add `get_content_item_by_id_api()` to `content_service.py` — calls `GET {base_url}/api/v1/content/{itemId}` — `backend/app/services/content_service.py`
- [X] T011 [P] Add `get_content_item_by_path_api()` to `content_service.py` — calls `GET {base_url}/api/v1/content` with `item_path` query param — `backend/app/services/content_service.py`
- [X] T012 Implement `get_content_item` @tool in `content_api.py` — single tool accepting either item_id or item_path; read-only — `backend/app/clients/content_api.py`
- [X] T013 Register `get_content_item` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 5: User Story 3 — Update and Delete Content Items

- [X] T015 [P] Add `update_content_api()` to `content_service.py` — calls `PUT {base_url}/api/v1/content/{itemId}` — `backend/app/services/content_service.py`
- [X] T016 [P] Add `delete_content_api()` to `content_service.py` — calls `DELETE {base_url}/api/v1/content/{itemId}` — `backend/app/services/content_service.py`
- [X] T017 Implement `update_content` @tool in `content_api.py` — confirmation-gated — `backend/app/clients/content_api.py`
- [X] T018 Implement `update_fields_on_item` @tool in `content_api.py` — simplified field-only wrapper; confirmation-gated — `backend/app/clients/content_api.py`
- [X] T019 Implement `delete_content` @tool in `content_api.py` — IRREVERSIBLE; confirmation-gated; warns ALL language versions deleted — `backend/app/clients/content_api.py`
- [X] T020 Register `update_content`, `update_fields_on_item`, `delete_content` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 6: Polish

- [ ] T021 [P] Add unit tests for all @tool functions in `backend/tests/test_content_api.py` — mock service functions; verify return shapes and error propagation — `backend/tests/test_content_api.py`
- [ ] T022 [P] Add unit tests for all service functions in `backend/tests/test_content_service.py` — mock httpx responses; verify endpoint URLs and request bodies — `backend/tests/test_content_service.py`
