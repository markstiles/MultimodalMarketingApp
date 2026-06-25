# Tasks: Media Asset Management

**Input**: Design documents from `specs/015-assets/`

**Prerequisites**: spec.md ✅

**Organization**: Foundational phase creates the API client and service module. US1 (search/view) and US2 (upload/update) can proceed in parallel after the foundational layer is complete since they touch different service functions and tools.

---

## Phase 1: Setup

- [X] T001 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `.env.example` — `.env.example`
- [X] T002 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `docker/.env.example` — `docker/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Create `backend/app/clients/assets_api.py` — `backend/app/clients/assets_api.py`
- [X] T004 Create `backend/app/services/assets_service.py` — `backend/app/services/assets_service.py`

---

## Phase 3: User Story 1 — Search and View Assets

- [X] T005 [P] Add `search_assets_api(query, language, asset_type)` to `assets_service.py` — calls `GET {base_url}/api/v1/assets/search` — `backend/app/services/assets_service.py`
- [X] T006 [P] Add `get_asset_info_api(asset_id)` to `assets_service.py` — calls `GET {base_url}/api/v1/assets/{assetId}` — `backend/app/services/assets_service.py`
- [X] T007 Implement `search_assets` @tool in `assets_api.py` — read-only; accepts query, language, asset_type — `backend/app/clients/assets_api.py`
- [X] T008 Implement `get_asset_info` @tool in `assets_api.py` — read-only — `backend/app/clients/assets_api.py`
- [X] T009 Register `search_assets` and `get_asset_info` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 4: User Story 2 — Upload Assets and Update Metadata

- [X] T010 [P] Add `upload_asset_api(file_content, filename, item_path, extension, site_name, language)` to `assets_service.py` — calls `POST {base_url}/api/v1/assets/upload` as multipart/form-data; upload_request sent as JSON string — `backend/app/services/assets_service.py`
- [X] T011 [P] Add `update_asset_api(asset_id, fields, language, name)` to `assets_service.py` — calls `PUT {base_url}/api/v1/assets/{assetId}` — `backend/app/services/assets_service.py`
- [X] T012 Implement `upload_asset` @tool in `assets_api.py` — confirmation-gated; added to `_WRITE_TOOLS` in `chat_service.py` — `backend/app/clients/assets_api.py`
- [X] T013 Implement `update_asset` @tool in `assets_api.py` — confirmation-gated — `backend/app/clients/assets_api.py`
- [X] T014 Register `upload_asset` and `update_asset` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 5: Polish

- [ ] T015 [P] Add unit tests for all 4 @tool functions in `backend/tests/test_assets_api.py` — `backend/tests/test_assets_api.py`
- [ ] T016 [P] Add unit tests for all service functions in `backend/tests/test_assets_service.py` — mock httpx responses; verify multipart form construction for upload — `backend/tests/test_assets_service.py`
