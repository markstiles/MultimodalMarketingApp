# Tasks: Content Development Workflow

**Input**: Design documents from `specs/007-content-dev-workflow/`

**Prerequisites**: [plan.md](plan.md) | [spec.md](spec.md) | [research.md](research.md) | [data-model.md](data-model.md) | [contracts/tool-contracts.md](contracts/tool-contracts.md)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in all task descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `python-docx` dependency and create stub modules for the new client and service files.

- [x] T001 Add `python-docx` to `backend/requirements.txt` (or `pyproject.toml` if that is the active dependency file) — verify it does not conflict with existing packages
- [x] T002 Create `backend/app/clients/content_workflow.py` module stub: import boilerplate, `@tool` decorator import from `langchain_core.tools`, and placeholder function signatures for `scan_content_project_status`, `save_phase_artifact`, and `get_phase_artifact_content`
- [x] T003 [P] Create `backend/app/services/content_workflow_service.py` module stub: import boilerplate and placeholder function signatures for `check_media_artifact_exists`, `generate_phase_docx`, `upload_artifact_to_media_library`, and `build_artifact_media_path`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared path resolution, auth helper, and tool registration that all three `@tool` functions depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Implement `PHASE_ARTIFACT_MAP` constant and `build_artifact_media_path(tenant, site, phase)` helper in `backend/app/services/content_workflow_service.py`. `PHASE_ARTIFACT_MAP` maps each phase name to its folder and canonical filename per `data-model.md` (Research→`research-brief.docx`, Strategy→`content-strategy.docx`, etc.). `build_artifact_media_path` returns the full media library path string.
- [x] T005 Add auth token support for media library API calls — first check whether `backend/app/clients/brand_auth.py` exists (spec 006); if it does, import its `get_brand_service_token()` helper and reuse it in `content_workflow_service.py` rather than duplicating the OAuth2 pattern; only implement a new `get_sitecore_media_auth_token()` helper in `content_workflow_service.py` if `brand_auth.py` does not yet exist — in that case follow the same OAuth2 client credentials pattern (using `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION` with a 60-second pre-expiry refresh cache) as `backend/app/clients/mcp_client.py`
- [x] T006 Register the three content workflow tools in `backend/app/clients/tools.py` — import from `content_workflow` and add to the return value of `get_all_tools()` so they are bound to the LangGraph model node via `.bind_tools()`

**Checkpoint**: Foundation ready — all user story tasks can now begin.

---

## Phase 3: User Story 1 — Marketer Starts a New Content Development Project (Priority: P1) 🎯 MVP

**Goal**: Deliver intent detection, media library scan for phase state, Word doc generation, and artifact upload — the complete path from "I want a content strategy" to a saved Research Brief in the media library.

**Independent Test**: With no existing `Content Strategy` folder for the test site, tell the assistant to help build a content strategy. Verify it proposes starting at Research, runs available analysis tools first, asks marketer questions, presents the Research Brief for review, accepts revisions, and saves to the canonical path only after explicit confirmation. See [quickstart.md Scenario 1](quickstart.md).

### Implementation for User Story 1

- [x] T007 [P] [US1] Implement `check_media_artifact_exists(tenant, site, phase, auth_token) -> dict` in `backend/app/services/content_workflow_service.py` — calls the Sitecore Items API (or equivalent read endpoint) at the canonical path returned by `build_artifact_media_path`; returns `{ "exists": bool, "modified_at": str|None, "age_days": int|None }`; must handle 404 (not found) and timeout as non-error states
- [x] T008 [US1] Implement `scan_content_project_status(tenant: str, site: str) -> dict` `@tool` in `backend/app/clients/content_workflow.py` — calls `check_media_artifact_exists` concurrently for all 6 phases using `asyncio.gather`; computes `PhaseStatus` enum (`not_started` / `complete` / `stale`) and populates `ContentProjectSummary` per `data-model.md`; returns full dict including `next_recommended_phase`, `has_stale_phases`, and `stale_phase_names`
- [x] T009 [P] [US1] Implement `generate_phase_docx(phase, title, tenant, site, sections) -> bytes` in `backend/app/services/content_workflow_service.py` — builds a Word document with python-docx using heading styles H1 (title), H2 (section headings), H3 (subsection headings), and body text paragraphs; writes to `BytesIO`; returns raw bytes; section structure per `research.md` Decision 3 (each phase has defined headings)
- [x] T010 [US1] Implement `upload_artifact_to_media_library(tenant, site, phase, docx_bytes, auth_token) -> dict` in `backend/app/services/content_workflow_service.py` — uploads the provided bytes to the canonical media library path via the Sitecore Agents API media upload endpoint; creates the phase folder if it does not exist (FR-013); returns `{ "success": bool, "media_path": str, "overwrite": bool, "error": str|None }`
- [x] T011 [US1] Implement `save_phase_artifact(tenant: str, site: str, phase: str, title: str, sections: list[dict]) -> dict` `@tool` in `backend/app/clients/content_workflow.py` — calls `generate_phase_docx` then `upload_artifact_to_media_library`; returns `ArtifactSaveResult` dict per `contracts/tool-contracts.md`; validates `phase` against `PHASE_ARTIFACT_MAP` and returns a clean error message for unknown phase values
- [x] T012 [P] [US1] Write the initial Track B overlay at `backend/instructions/tasks/content-dev-workflow.md` covering: (1) intent detection triggers (content strategy, content planning, editorial calendar, campaign brief intent); (2) session-start scan instruction (always call `scan_content_project_status` first and show the project status overview); (3) Research phase guidance including tool-first approach per FR-016, the research question set (audience, competitive, content performance), and the Research Brief section structure (`research-brief.docx` headings from `research.md` Decision 3); (4) confirmation gate pattern for `save_phase_artifact` (present full artifact for review before calling the tool; require explicit marketer approval per FR-006, FR-007); (5) New project path (all phases not_started → explain workflow → propose Research); (6) tenant/site resolution fallback — if tenant or site name cannot be determined from session context, ask the marketer to confirm the site before calling any media library tool (FR-015); (7) upload failure handling — if `save_phase_artifact` returns `success: false`, inform the marketer of the specific error and offer to retry the save or skip saving for now

**Checkpoint**: US1 complete — marketer can start a new content project and save a Research Brief end to end.

---

## Phase 4: User Story 2 — Marketer Resumes an In-Progress Content Project (Priority: P2)

**Goal**: Enable the assistant to detect existing phase artifacts on session start, present a project status overview, and surface staleness warnings when a prior phase artifact is more than 12 months old.

**Independent Test**: With a Research Brief already in the media library for the test site, start a new assistant session and ask to continue the content strategy. Verify the assistant detects the artifact and presents a status overview without the marketer re-explaining history. Set the artifact date to older than 365 days; verify the staleness warning appears before any Strategy work begins. See [quickstart.md Scenario 2](quickstart.md).

### Implementation for User Story 2

- [x] T013 [P] [US2] Implement `get_phase_artifact_content(tenant: str, site: str, phase: str) -> dict` `@tool` in `backend/app/clients/content_workflow.py` — downloads the `.docx` from the canonical media library path via Sitecore media API; extracts text using the document extraction utility (spec 004 compatible; use the existing extraction helper if available, else fall back to python-docx text extraction); returns `ArtifactContentResult` dict per `contracts/tool-contracts.md`; on missing artifact or extraction failure returns `success: false` with a descriptive error
- [x] T014 [US2] Extend `backend/instructions/tasks/content-dev-workflow.md` with the resume-project flow: (1) existing-project path in the status overview (show each phase with status and artifact age); (2) staleness warning flow with all three marketer choices (proceed, return to prior phase, review stale artifact) per FR-009, FR-010; (3) instruction to call `get_phase_artifact_content` when the marketer chooses "review stale artifact"; (4) propose next incomplete phase and begin it using the existing `scan_content_project_status` result

**Checkpoint**: US2 complete — returning marketers get an automatic project status overview and staleness warnings.

---

## Phase 5: User Story 3 — Marketer Works Through a Strategy Phase (Priority: P2)

**Goal**: Enable cross-phase reference (prior artifacts injected into context) and guide the marketer through the Strategy, Structure, Content, and Variation phases — each producing a reviewed and saved artifact.

**Independent Test**: With a Research Brief present, ask the assistant to build a content strategy. Verify the assistant references the Research Brief findings without the marketer re-entering them, asks Strategy-specific questions, generates a `content-strategy.docx` that explicitly references audience and competitive context, and saves it after approval. See [quickstart.md Scenario 3](quickstart.md).

### Implementation for User Story 3

- [x] T015 [P] [US3] Extend `backend/instructions/tasks/content-dev-workflow.md` with Strategy phase guidance: (1) instruction to call `get_phase_artifact_content` for the Research phase before asking any Strategy questions; (2) summarize Research findings before the first Strategy question; (3) Strategy question set (content goals & KPIs, messaging pillars, editorial themes, audience-to-content mapping); (4) `content-strategy.docx` section headings from `research.md` Decision 3; (5) confirmation gate for `save_phase_artifact` → Strategy
- [x] T016 [P] [US3] Extend `backend/instructions/tasks/content-dev-workflow.md` with Structure, Content, and Variation phase guidance — for each: (1) which prior phase artifact to retrieve via `get_phase_artifact_content`; (2) phase-specific question set; (3) canonical artifact section headings from `research.md` Decision 3; (4) confirmation gate for `save_phase_artifact`; use the Strategy phase as the established pattern for these three phases

**Checkpoint**: US3 complete — marketers can work through any of the middle four phases with full cross-phase reference.

---

## Phase 6: User Story 4 — Marketer Skips or Returns to a Phase (Priority: P3)

**Goal**: Allow the marketer to skip phases with quality warnings and return to any prior phase to revise its artifact.

**Independent Test**: With no prior artifacts, ask to skip to Structure — verify the quality warning appears and requires confirmation before proceeding. Then ask to return to Research and revise it — verify the assistant retrieves the existing artifact, presents it, allows updates, and saves the revised version at the same path. See [quickstart.md Scenario 4](quickstart.md).

### Implementation for User Story 4

- [x] T017 [US4] Extend `backend/instructions/tasks/content-dev-workflow.md` with: (1) skip-phase warning flow — detect when marketer requests a phase that has incomplete predecessors, show quality impact warning with the specific missing phases named, require explicit confirmation before proceeding; (2) skip context note — when a phase is skipped the assistant notes it will need additional context that would normally come from the prior phase; (3) return-to-prior-phase flow — when marketer asks to revise a completed phase, call `get_phase_artifact_content` to retrieve it, present for review, update per marketer feedback, then save back via `save_phase_artifact` (overwrite = true)

**Checkpoint**: US4 complete — all four user stories are now functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Execution phase overlay, unit tests, and quickstart validation.

- [x] T018 [P] Add Execution phase guidance to `backend/instructions/tasks/content-dev-workflow.md`: (1) call `get_phase_artifact_content` for Content and Variation phases before starting; (2) Execution Checklist question set (Sitecore content actions: page creation, component population, sign-off items); (3) `execution-checklist.docx` section headings from `research.md` Decision 3; (4) after saving the checklist, invoke available authoring tools (page scaffolding, component population per spec assignments) with individual confirmation gates; (5) note that the Execution phase differs from others — it produces both an artifact AND performs Sitecore content operations
- [x] T019 [P] Write unit tests in `backend/tests/test_content_workflow.py` covering: `build_artifact_media_path` (all 6 phases produce correct paths), `scan_content_project_status` (not_started/complete/stale scenarios with mocked `check_media_artifact_exists`), `save_phase_artifact` (success path, unknown phase error, upload failure error), `get_phase_artifact_content` (success path, missing artifact, extraction failure)
- [x] T020 Run [quickstart.md](quickstart.md) validation scenarios 1–5 against the local dev environment; document pass/fail for each scenario acceptance criterion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Story Phases (3–6)**: All depend on Phase 2 completion; can proceed sequentially in P1 → P2 → P2 → P3 priority order
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories — start after Phase 2
- **US2 (P2)**: Scan tool from US1 must be complete (T008 before T013); overlay from US1 (T012) must exist before T014 extends it
- **US3 (P2)**: `get_phase_artifact_content` tool from US2 (T013) must be complete before T015/T016 (cross-phase reference in overlay)
- **US4 (P3)**: Overlay from US3 (T015/T016) must be complete before T017 extends it

### Within Each User Story

- Setup (T007, T009) → can run in parallel [P]; T008 depends on T007; T011 depends on T009, T010
- T012 (overlay) is independent of all Python tasks in Phase 3 — write in parallel
- Overlay extension tasks (T014, T015, T016, T017, T018) must be applied in order to avoid conflicts on the same file

### Parallel Opportunities

- T002 and T003 (setup stubs) can run in parallel
- T007 and T009 (service helpers) can run in parallel within US1
- T012 (initial overlay) can run in parallel with T007–T011 (Python tools)
- T013 and T014 can run in parallel within US2
- T015 and T016 can run in parallel within US3
- T018 and T019 can run in parallel within Polish

---

## Parallel Example: User Story 1

```
# These can run in parallel:
T007 — check_media_artifact_exists() service function
T009 — generate_phase_docx() service function
T012 — Track B overlay (initial, Research phase + intent detection)

# Then sequentially:
T008 — scan_content_project_status @tool (depends on T007)
T010 — upload_artifact_to_media_library() service function (depends on T009)
T011 — save_phase_artifact @tool (depends on T009, T010)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T006) — CRITICAL
3. Complete Phase 3: User Story 1 (T007–T012)
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 — marketer starts new project, saves Research Brief
5. The MVP delivers: intent detection → scan → Research phase → artifact saved to media library

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → marketer can start a new project and complete the Research phase (MVP)
3. US2 → marketers can resume across sessions with status overview and staleness warnings
4. US3 → marketers can work through all six phases with cross-phase reference
5. US4 → experienced marketers can skip or revise phases
6. Polish → Execution phase guidance, full test coverage, validated quickstart

---

## Notes

- No new database migrations — the media library is the state store; verify no DB changes sneak in
- Track B overlay (`.md` file) tasks are independent of Python tasks and can be drafted early
- The overlay tasks (T012, T014, T015, T016, T017, T018) all modify the same file — run these sequentially to avoid merge conflicts
- `python-docx` generates `.docx` files only; `.docx` → text extraction uses the existing spec 004 document extraction utility if available
- Auth for media API follows the `mcp_client.py` token-cache pattern exactly; do not introduce a new auth approach
- All three tools must appear in `get_all_tools()` (T006) before the LangGraph graph can invoke them
