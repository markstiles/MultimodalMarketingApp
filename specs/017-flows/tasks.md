# Tasks: Flows & Variants

**Input**: Design documents from `specs/017-flows/`

**Prerequisites**: plan.md ✅ | spec.md ✅

**Organization**: Foundational phase creates the service and client. US1 (browse flows) and US2 (configure variant) can run in parallel after foundational work.

---

## Phase 1: Setup

- [X] T001 Verify `SITECORE_AGENTS_API_BASE_URL` env var is present — `.env.example`

---

## Phase 2: Foundational

- [X] T002 Create `backend/app/services/flows_service.py` — async httpx helpers; all service functions call get_sitecore_automation_token() internally — `backend/app/services/flows_service.py`
- [X] T003 Create `backend/app/clients/flows_api.py` — @tool wrappers for flow and variant operations — `backend/app/clients/flows_api.py`

---

## Phase 3: User Story 1 — Browse Page Flows (Priority: P1)

- [X] T004 [US1] Implement `list_flow_definitions_by_page_api(page_id, language)` — GET /api/v1/flows/by-page/{pageId} — `backend/app/services/flows_service.py`
- [X] T005 [US1] Implement `get_flow_definition_api(flow_id)` — GET /api/v1/flows/{flowId} — `backend/app/services/flows_service.py`
- [X] T006 [P] [US1] Implement `list_page_flows` @tool — read-only — `backend/app/clients/flows_api.py`
- [X] T007 [P] [US1] Implement `get_flow_definition` @tool — read-only — `backend/app/clients/flows_api.py`
- [X] T008 [US1] Register `list_page_flows` and `get_flow_definition` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 4: User Story 2 — Configure a Variant (Priority: P1)

- [X] T009 [US2] Implement `setup_variant_api(flow_id, variant_id, page_id, component_id, variant_strategy, ...)` — POST /api/v1/flows/{flowId}/variants/{variantId} — `backend/app/services/flows_service.py`
- [X] T010 [US2] Implement `get_variant_api(flow_id, variant_id, language)` — GET /api/v1/flows/{flowId}/variants/{variantId} — `backend/app/services/flows_service.py`
- [X] T011 [P] [US2] Implement `get_flow_variant` @tool — read-only — `backend/app/clients/flows_api.py`
- [X] T012 [P] [US2] Implement `setup_flow_variant` @tool — confirmation-gated; variant_strategy is HIDE, SWAP, or COPY — `backend/app/clients/flows_api.py`
- [X] T013 [US2] Register `get_flow_variant` and `setup_flow_variant` in `backend/app/clients/tools.py`; add `setup_flow_variant` to `_WRITE_TOOLS` in `backend/app/services/chat_service.py` — `backend/app/clients/tools.py`

---

## Phase 5: Polish

- [ ] T014 Create `backend/instructions/tasks/flows.md` — overlay covering: list flows (read-only), get flow definition (read-only), setup variant (confirm flow + variant + config before calling `setup_flow_variant`)
