# Implementation Plan: Content Development Workflow

**Branch**: `007-content-dev-workflow` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-content-dev-workflow/spec.md`

## Summary

Add a guided, intent-driven content development workflow that helps marketers move through six structured phases (Research → Strategy → Structure → Content → Variation → Execution) with the assistant as guide. Phase state is determined by scanning the Sitecore media library for canonical artifact files at known paths — no new database tables are needed. The assistant generates Word document artifacts at the end of each phase, saves them to the media library with explicit marketer confirmation, and references prior artifacts in downstream phases. The Research phase uses available analysis tools first (site analytics, SEO, competitive analysis) then supplements with marketer questions. Track B overlay handles all intent detection, phase guidance, staleness warnings, and confirmation flows. Track A tools handle media library scanning, artifact upload, and cross-phase content retrieval.

## Technical Context

**Language/Version**: Python 3.12 (unchanged)

**Primary Dependencies**:
- FastAPI + existing infrastructure (unchanged)
- LangGraph + LangChain (unchanged)
- SQLModel (unchanged — no new tables)
- `python-docx` (NEW) — Word document generation for phase artifacts

**New Track A client** (`backend/app/clients/`):
- `content_workflow.py` — NEW: three `@tool` functions for content project state management

**New Track A service helper** (`backend/app/services/`):
- `content_workflow_service.py` — NEW: Word doc generation (python-docx) + Agents API media upload helper; NOT a `@tool`, called by the tools in `content_workflow.py`

**New Track B overlay** (`backend/instructions/tasks/`):
- `content-dev-workflow.md` — NEW: phase workflow instruction overlay

**No new SQLModel tables** — the Sitecore media library is the persistent state store for phase artifacts per the spec design.

**New env vars**: None — tenant/site resolved from session context; media library auth reuses existing `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION`.

**Storage**: PostgreSQL on Railway (unchanged); no new tables. Phase artifacts stored in Sitecore media library via Agents API.

**Testing**: pytest (existing framework)

**Target Platform**: Railway (existing deployment)

**Performance Goals**:
- Content project status scan (FR-002) ≤ 3 seconds (6 concurrent media library checks)
- Phase artifact save ≤ 30 seconds (includes Word doc generation + Agents API upload)

**Constraints**:
- No media library write without explicit marketer confirmation (Constitution Principle I; FR-007, FR-008)
- All Sitecore API calls wrapped in `clients/` as `@tool` functions (Constitution Principle VI)
- Track B overlay governs intent detection, phase guidance, staleness warnings, confirmation prompts — no task logic in Python (Constitution Principle IV)
- Research phase tools must degrade gracefully if unavailable (FR-016)

**Scale/Scope**: Per-site content project; single active project per site in v1 (<100 users v1)

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle IV) | ✅ PASS | All phase guidance, staleness warnings, skip warnings, and confirmation prompts live in `content-dev-workflow.md` overlay |
| No Sitecore write without user confirmation (Principle I) | ✅ PASS | FR-007 and FR-008 require explicit marketer approval before any artifact is saved; `save_phase_artifact` tool may not be called without a preceding confirmation step per the overlay |
| New integrations use typed API client layer (Principle VI) | ✅ PASS | `content_workflow.py` in `backend/app/clients/`; media API calls in service helper; no inline calls from graph nodes or route handlers |
| New task behaviors in `instructions/tasks/*.md` (Principle IV) | ✅ PASS | `content-dev-workflow.md` overlay governs all workflow logic — phase sequencing, artifact naming, staleness threshold, skip warnings |
| No profile-switching logic (Principle IV) | ✅ PASS | Additive overlay only; base identity and guardrails unchanged |
| Guardrail coverage verified (Principle II) | ✅ PASS | Content strategy and marketing planning are explicitly permitted topics; no topic expansion required |
| Memory writes use correct store (Principle V) | ✅ PASS | No new DB tables; media library is the state store — distinct from conversation history and user knowledge store |
| Database models use SQLModel (Technology Standards) | ✅ N/A | No new database tables required for this feature |
| LLM calls through `clients/llm.py` only (Technology Standards) | ✅ PASS | No new LLM clients; existing graph and model node unchanged |
| New multi-step workflows in LangGraph (Technology Standards) | ✅ PASS | No new graph needed — the content development workflow is encoded in the Track B overlay, driven by the existing chat graph; multi-phase coordination is conversational, not a separate state machine |
| New tools bound via `.bind_tools()` in `clients/` (Technology Standards) | ✅ PASS | `content_workflow.py` tools registered via existing `tools.py` registry pattern |
| MLflow tracing on all LLM/LangGraph paths (Principle VII) | ✅ PASS | Inherits from `mlflow.langchain.autolog()` called at startup; new tool calls automatically traced |

## Project Structure

### Documentation (this feature)

```text
specs/007-content-dev-workflow/
├── plan.md              # This file
├── research.md          # Phase 0 technical decisions
├── data-model.md        # Runtime data shapes and media library path schema (no DB tables)
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
│   │   └── content_workflow.py           # NEW: @tool functions for content project management
│   └── services/
│       └── content_workflow_service.py   # NEW: Word doc generation + Agents API upload helper
├── instructions/
│   └── tasks/
│       └── content-dev-workflow.md       # NEW: Track B phase workflow overlay
└── tests/
    └── test_content_workflow.py          # NEW
```

**Structure Decision**: Minimal extension of the existing four-layer architecture (route handlers → services → clients → resources). No new DB tables. `content_workflow_service.py` handles I/O-heavy operations (python-docx generation, Agents API upload); `content_workflow.py` exposes the `@tool` surface to the LangGraph agent. This separation keeps tool functions thin and the service helper independently testable.

## Complexity Tracking

> No constitution violations. All gates pass without exceptions.
