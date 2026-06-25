# Tasks: Component & Datasource Management

**Input**: Design documents from `specs/014-components/`

**Prerequisites**: spec.md ✅

**Organization**: Foundational phase creates the API client and service module. US1 (browse components) and US2 (datasources) can proceed in parallel after the foundational layer is complete since they touch different service functions and tools.

---

## Phase 1: Setup

- [X] T001 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `.env.example` — `.env.example`
- [X] T002 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `docker/.env.example` — `docker/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Create `backend/app/clients/components_api.py` — `backend/app/clients/components_api.py`
- [X] T004 Create `backend/app/services/components_service.py` — `backend/app/services/components_service.py`

---

## Phase 3: User Story 1 — Browse Components

- [X] T005 [P] Add `list_components_api(site_name)` to `components_service.py` — calls `GET {base_url}/api/v1/components?site_name=...` — `backend/app/services/components_service.py`
- [X] T006 [P] Add `get_component_api(component_id)` to `components_service.py` — calls `GET {base_url}/api/v1/components/{componentId}` — `backend/app/services/components_service.py`
- [X] T007 Implement `list_components` @tool in `components_api.py` — read-only — `backend/app/clients/components_api.py`
- [X] T008 Implement `get_component` @tool in `components_api.py` — read-only — `backend/app/clients/components_api.py`
- [X] T009 Register `list_components` and `get_component` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 4: User Story 2 — Datasource Management

- [X] T010 [P] Add `create_component_datasource_api(component_id, site_name, data_fields, language)` to `components_service.py` — calls `POST {base_url}/api/v1/components/{componentId}/datasources` — `backend/app/services/components_service.py`
- [X] T011 [P] Add `search_component_datasources_api(component_id, term)` to `components_service.py` — calls `GET {base_url}/api/v1/components/{componentId}/datasources/search?term=...` — `backend/app/services/components_service.py`
- [X] T012 Implement `create_component_ds` @tool in `components_api.py` — confirmation-gated — `backend/app/clients/components_api.py`
- [X] T013 Implement `search_component_datasources` @tool in `components_api.py` — read-only — `backend/app/clients/components_api.py`
- [X] T014 Register `create_component_ds` and `search_component_datasources` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 5: Polish

- [ ] T015 [P] Add unit tests for all 4 @tool functions in `backend/tests/test_components_api.py` — `backend/tests/test_components_api.py`
- [ ] T016 [P] Add unit tests for all service functions in `backend/tests/test_components_service.py` — `backend/tests/test_components_service.py`
