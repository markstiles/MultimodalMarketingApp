# Tasks: Personalization & A/B Testing

**Input**: Design documents from `specs/016-personalization-ab-testing/`

**Prerequisites**: spec.md ✅

**Organization**: Foundational phase creates the API client and service module. US1 (personalization variants) and US2 (A/B tests) can proceed in parallel after the foundational layer is complete since they touch different service functions and tools.

---

## Phase 1: Setup

- [X] T001 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `.env.example` — `.env.example`
- [X] T002 [P] Verify `SITECORE_AGENTS_API_BASE_URL` is present in `docker/.env.example` — `docker/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Create `backend/app/clients/personalization_api.py` — `backend/app/clients/personalization_api.py`
- [X] T004 Create `backend/app/services/personalization_service.py` — `backend/app/services/personalization_service.py`

---

## Phase 3: User Story 1 — Personalization Variants

- [X] T005 [P] Add `get_personalization_versions_api(page_id, language)` — GET /api/v2/personalization/by-page/{pageId} — `backend/app/services/personalization_service.py`
- [X] T006 [P] Add `create_personalization_version_api(page_id, name, variant_name, audience_name, condition_groups, language)` — POST /api/v2/personalization/{pageId}/versions — `backend/app/services/personalization_service.py`
- [X] T007 [P] Add `update_personalization_version_api(page_id, variant_id, ...)` — PUT /api/v1/personalization/{pageId}/versions/{variantId} — `backend/app/services/personalization_service.py`
- [X] T008 [P] Add `get_condition_templates_api()` — GET /api/v1/personalization/condition-templates — `backend/app/services/personalization_service.py`
- [X] T009 [P] Add `get_condition_template_by_id_api(template_id)` — GET /api/v1/personalization/condition-templates/{template_id} — `backend/app/services/personalization_service.py`
- [X] T010 Implement `get_personalization_versions` @tool — read-only — `backend/app/clients/personalization_api.py`
- [X] T011 Implement `create_perso_version` @tool — confirmation-gated — `backend/app/clients/personalization_api.py`
- [X] T012 Implement `create_perso_version_multi` @tool — confirmation-gated; same endpoint as create_perso_version, intended for complex multi-condition targeting — `backend/app/clients/personalization_api.py`
- [X] T013 Implement `update_perso_version` @tool — confirmation-gated — `backend/app/clients/personalization_api.py`
- [X] T014 [P] Implement `get_condition_templates` @tool — read-only — `backend/app/clients/personalization_api.py`
- [X] T015 [P] Implement `get_condition_template_by_id` @tool — read-only — `backend/app/clients/personalization_api.py`
- [X] T016 Register all 6 personalization tools in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Phase 4: User Story 2 — A/B Tests

- [X] T017 [P] Add `create_component_ab_test_api(site_id, page_id, component_id, name, goal_type, variants, language)` — POST /api/v1/experiments/flows — `backend/app/services/personalization_service.py`
- [X] T018 [P] Add `update_ab_test_api(flow_id, name, variants, archived)` — PUT /api/v1/experiments/{flowId} — `backend/app/services/personalization_service.py`
- [X] T019 Implement `create_component_ab_test` @tool — confirmation-gated; variants must sum to 100, exactly one control — `backend/app/clients/personalization_api.py`
- [X] T020 Implement `update_ab_test` @tool — confirmation-gated — `backend/app/clients/personalization_api.py`
- [X] T021 Register `create_component_ab_test` and `update_ab_test` in `backend/app/clients/tools.py` — `backend/app/clients/tools.py`

---

## Deferred

- [ ] `set_component_variant` — listed in `_WRITE_TOOLS` but no corresponding Agent API endpoint found in agent-api.json; deferred pending API spec clarification.

---

## Phase 5: Polish

- [ ] T022 [P] Add unit tests in `backend/tests/test_personalization_api.py` — `backend/tests/test_personalization_api.py`
- [ ] T023 [P] Add unit tests in `backend/tests/test_personalization_service.py` — `backend/tests/test_personalization_service.py`
