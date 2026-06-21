# Tasks: Marketing Pipeline

**Input**: Design documents from `specs/012-marketing-pipeline/`

**Prerequisites**: plan.md ✅, spec.md ✅

**Organization**: Tasks grouped by user story (US1–US7). Most tasks are complete — remaining work is the manual quickstart validation (T019).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency and environment configuration

- [X] T001 Add `tavily-python` to backend/requirements.txt
- [X] T002 Add `SITECORE_ORGANIZATION_ID` to .env.example with documentation comment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core registry and tool registration changes required before any user-story implementation

**⚠️ CRITICAL**: All user-story work depends on these completing first

- [X] T003 Update `PHASE_ARTIFACT_MAP` to 5-phase flat structure (remove `folder` key, add `CONTENT_STRATEGY_FOLDER` constant) in backend/app/services/content_workflow_service.py
- [X] T004 Update `build_artifact_media_path` to flat path (`/Content Strategy/{item_name}`) in backend/app/services/content_workflow_service.py
- [X] T005 Update `ensure_phase_upload_folders` to create only `Content Strategy` folder (no per-phase subfolders) in backend/app/services/content_workflow_service.py
- [X] T006 Update `scan_content_project_status` to use `CONTENT_STRATEGY_FOLDER` constant for `folder_name` in backend/app/clients/content_workflow.py
- [X] T007 Register all new client tools (`search_market_research`, `list_org_brand_kits`, `get_brand_voice_summary`, `create_org_brand_kit`, `import_brand_document`, `review_content_against_brand`) in backend/app/clients/tools.py

**Checkpoint**: Phase registry is flat, new tools are wired — user story implementation can proceed

---

## Phase 3: User Story 1 — AI-Assisted Research (Priority: P1) 🎯 MVP

**Goal**: Marketer can request AI web research and receive a synthesized Research Brief

**Independent Test**: Ask the assistant to research "project management SaaS" competitors; confirm it calls `search_market_research`, synthesizes results, and produces a Research Brief artifact for approval

- [X] T008 [P] [US1] Implement `web_search()` TavilyClient wrapper (reads `TAVILY_API_KEY`, returns `{url, title, content, score}` list) in backend/app/services/marketing_research_service.py
- [X] T009 [US1] Implement `search_market_research` `@tool` (iterates queries, aggregates results, returns `{success, query_count, result_count, results, errors}`) in backend/app/clients/marketing_research.py
- [X] T010 [US1] Add Research phase guidance to overlay (intent check → gather context → web search → synthesize; do not present raw results) in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: Research phase fully functional; marketer can produce a Research Brief with or without AI research

---

## Phase 4: User Story 2 — Marketing Strategy (Priority: P2)

**Goal**: Marketer can define positioning and goals informed by Research Brief context

**Independent Test**: With a Research Brief artifact present, start the Strategy phase; confirm the assistant surfaces research findings without asking the marketer to re-enter them

- [X] T011 [US2] Add Strategy phase guidance to overlay (reads Research artifact via `get_phase_artifact_content`, strategy questions, artifact sections) in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: Strategy phase reads Research artifact automatically; marketer produces Marketing Strategy document

---

## Phase 5: User Story 3 — Brand Voice via Sitecore Stream (Priority: P2)

**Goal**: Marketer can connect an existing brand kit or create one to anchor the pipeline's brand voice

**Independent Test**: Call `list_org_brand_kits` (returns empty list), then `create_org_brand_kit`, then `get_brand_voice_summary`; confirm each succeeds and the Brand Voice Summary artifact is produced

- [X] T012 [P] [US3] Implement `list_brand_kits()` and `create_brand_kit()` (Brand Management API CRUD) in backend/app/services/brand_kit_service.py
- [X] T013 [P] [US3] Implement `get_brand_kit_voice_sections()` (reads Brand Context, Tone of Voice, Do's and Don'ts sections), `upload_brand_document()` (Document Management API multipart upload), and `run_brand_review()` (Brand Review API scoring) in backend/app/services/brand_kit_service.py
- [X] T014 [US3] Implement all five brand kit `@tool` functions (`list_org_brand_kits`, `get_brand_voice_summary`, `create_org_brand_kit`, `import_brand_document`, `review_content_against_brand`) in backend/app/clients/brand_kit.py
- [X] T015 [US3] Add Brand Voice phase guidance to overlay (kit lookup → select/create → read sections → Brand Voice Summary artifact) in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: Brand Voice phase can connect to or create a Sitecore Stream brand kit; produces Brand Voice Summary

---

## Phase 6: User Story 4 — Campaign Brief & Flexible Entry Point (Priority: P1)

**Goal**: Marketer can create a Campaign Brief from prior phases, or jump directly to Brief with a pre-existing brief

**Independent Test**: Tell the assistant "I already have a brief" at session start; confirm it skips Research/Strategy/Brand Voice and goes directly to Brief with compensating questions

- [X] T016 [US4] Add Brief phase guidance (flexible entry point detection, compensating questions, reads Strategy + BrandVoice artifacts) and entry-point detection section to overlay in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: Brief can be created from prior context or entered directly; Campaign Brief artifact produced

---

## Phase 7: User Story 5 — Campaign Tactics (Priority: P2)

**Goal**: Marketer can produce Funnel & Persona Blueprint, Personalization Rules, and A/B Testing Plan from the Campaign Brief

**Independent Test**: With a Campaign Brief artifact present, start the Campaign phase and request all three tactic documents; confirm each reads the brief and produces distinct content sections

- [X] T017 [US5] Add Campaign phase guidance (tactic selection, Funnel/Persona Blueprint, Personalization Rules, A/B Testing Plan sections) to overlay in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: All three campaign tactic documents producible from the Campaign Brief

---

## Phase 8: User Story 6 — Session Scan & Skip Flow (Priority: P1)

**Goal**: Assistant scans project status at session start and allows skipping any phase with a warning

**Independent Test**: Start a session with Research and Strategy artifacts present; confirm the status table shows both as complete and suggests Brand Voice as the next phase

- [X] T018 [US6] Add session-start scan flow (status table, next recommended phase), entry point detection, skip/return flow, and staleness warnings to overlay in backend/instructions/tasks/content-dev-workflow.md

**Checkpoint**: Session always opens with a status scan; marketer can skip or return to any phase

---

## Phase 9: User Story 7 — Overwrite Resilience & Tests (Priority: P2)

**Goal**: Re-saving a phase artifact silently overwrites the previous version; test suite validates all five phases

**Independent Test**: Save a Research Brief, then save again; confirm the second save returns `overwrite: true` and the confirmation message says "previous version replaced"

- [X] T019 [P] [US7] Update `test_all_five_phases_produce_correct_paths` with flat path expectations in backend/tests/test_content_workflow.py
- [X] T020 [P] [US7] Update `test_tenant_and_site_interpolated` and `test_extraction_failure` to use valid new phase names in backend/tests/test_content_workflow.py
- [X] T021 [US7] Update tool docstrings (`scan_content_project_status`, `save_phase_artifact`, `get_phase_artifact_content`) to list new phase names in backend/app/clients/content_workflow.py

**Checkpoint**: All 42 tests pass; overwrite behavior confirmed via existing upload tests

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T022 Run quickstart validation: start the local dev environment, trigger the marketing pipeline overlay, scan project status for a test site, save a Research Brief, retrieve it, and invoke `list_org_brand_kits` — confirm each step completes without errors (manual integration test against a live Sitecore instance)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user story phases
- **US1–US7 (Phases 3–9)**: All depend on Foundational; can be developed sequentially
- **Polish (Phase 10)**: Depends on all implementation phases — manual validation only

### User Story Dependencies

- **US1 (Research)**: Independent after Foundational — no upstream dependencies
- **US2 (Strategy)**: Independent; reads US1 artifact at runtime but does not depend on US1 implementation
- **US3 (Brand Voice)**: Independent; parallel implementation with US1/US2
- **US4 (Brief)**: Independent; reads US2+US3 artifacts at runtime
- **US5 (Campaign)**: Depends on US4 artifact at runtime; implementation is independent
- **US6 (Session Scan)**: Cross-cutting; the overlay change covers all phases in one file
- **US7 (Overwrite/Tests)**: Independent; verifies infrastructure already in place

### Parallel Opportunities

- T008 (`marketing_research_service.py`) and T012–T013 (`brand_kit_service.py`) are fully parallel — different files, no shared state
- T009 (`marketing_research.py` client) and T014 (`brand_kit.py` client) are parallel after their respective services
- T019 and T020 (test updates) are parallel — both in the same file but non-overlapping sections

---

## Parallel Example: US3 Brand Kit Services

```
# These two groups run in parallel (different files):
Task T012: list_brand_kits, create_brand_kit → brand_kit_service.py
Task T013: get_brand_kit_voice_sections, upload_brand_document, run_brand_review → brand_kit_service.py

# After both complete:
Task T014: All five brand kit @tool functions → brand_kit.py
```

---

## Implementation Strategy

### MVP (US1 + US4 + US6)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1 — Research with web search)
3. Complete Phase 6 (US4 — Brief entry point)
4. Complete Phase 8 (US6 — Session scan)
5. **Validate**: Marketer can go from zero to Campaign Brief in one session

### Full Pipeline

Continue from MVP:
6. Phase 4 (US2 — Strategy) → context flows from Research automatically
7. Phase 5 (US3 — Brand Voice) → brand kit connected
8. Phase 7 (US5 — Campaign Tactics) → three tactic documents
9. Phase 9 (US7 — Overwrite + Tests) → regression safety net
10. Phase 10 (Polish) — manual integration validation

---

## Notes

- [P] = different files, no blocking dependencies — can run concurrently
- All tasks T001–T021 are complete as of 2026-06-21
- T022 (quickstart validation) requires a live Sitecore instance with `SITECORE_ORGANIZATION_ID` set
- Constitution check: all new tools follow `@tool` in `clients/`; all phase guidance lives in `instructions/tasks/content-dev-workflow.md`; no prompts hardcoded in Python
