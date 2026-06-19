# Implementation Plan: Brand Kit Building

**Branch**: `006-brand-kit-building` | **Date**: 2026-06-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-brand-kit-building/spec.md`

## Summary

Add three brand-kit-building capabilities to the marketing assistant: (1) upload brand documents (PDF, Word) to the Sitecore brand document library; (2) trigger the brand ingestion and enrichment pipelines and surface completion notifications automatically in the conversation; (3) generate brand kit content from a live website URL via the enrichment pipeline. All writes require marketer confirmation. Documents begin in Draft status and only influence brand context after a 10–20 minute processing run completes. Pipeline run IDs are persisted in PostgreSQL so notifications survive across turns; the LangGraph graph checks for completed runs before the model node on every turn, injecting status updates without requiring the marketer to ask.

## Technical Context

**Backend**:
- Python 3.12 (unchanged)
- FastAPI + existing infrastructure (unchanged)
- New Sitecore service clients (`backend/app/clients/`):
  - `brand_auth.py` — shared token-cache helper for all brand service APIs (extracted to avoid duplication)
  - `brand_documents.py` — Document Management API: list + upload documents; LangChain `@tool` functions
  - `brand_pipeline.py` — Pipeline API: trigger + poll ingestion/enrichment runs; `@tool` functions
  - `brand_sections.py` — Brand Management API: list subsections + toggle Non-AI Editable; `@tool` functions
- `backend/app/services/chat_graph.py` — extended with a `check_pipeline_notifications` pre-model node
- New SQLModel tables: `brand_document_uploads`, `brand_pipeline_runs` (see data-model.md)
- Alembic migration for new tables
- New Track B overlay: `backend/instructions/tasks/brand-kit-building.md`

**Auth**: Sitecore OAuth2 client credentials — same flow as `mcp_client.py`. Shared `get_brand_service_token()` helper in `brand_auth.py` reuses `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION` with a cached token refreshed 60 seconds before expiry.

**New env vars**:
- `BRAND_SERVICE_ORG_ID` — Sitecore organization ID for all brand service API paths (required)
- `BRAND_DOC_API_BASE_URL` — Document Management API base (default: `https://edge-platform.sitecorecloud.io/stream/ai-document-api`)
- `BRAND_PIPELINE_API_BASE_URL` — Pipeline API base (default: `https://edge-platform.sitecorecloud.io/stream/ai-pipeline-api`)
- `BRAND_MGMT_API_BASE_URL` — Brand Management API base (default: `https://edge-platform.sitecorecloud.io/stream/ai-brands-api`)

**Storage**: PostgreSQL on Railway (existing service); two new tables via Alembic migration.

**Testing**: pytest (existing framework); new tests in `backend/tests/` per tool module.

**Target Platform**: Railway (existing deployment).

**Performance Goals**:
- Document upload confirmation ≤ 30 seconds (SC-001)
- Pipeline notification check overhead ≤ 200ms per conversation turn (DB query + conditional brand service call)

**Constraints**:
- No brand service write without marketer confirmation gate (Constitution Principle I; FR-003, FR-007, FR-008, FR-017)
- All brand service calls wrapped in `clients/` as `@tool` functions bound to the graph via `.bind_tools()`
- `check_pipeline_notifications` graph node calls service-layer functions directly (not tools) — this is a coordination mechanism, not a user-invokable capability, so it does not go through ToolNode
- Track B overlay governs intent detection and pipeline confirmation flow; no task logic hardcoded in Python (Constitution Principle IV)

**Scale/Scope**: Per-org brand kit operations; expected concurrency same as core chat (<100 users v1).

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle IV) | ✅ PASS | Brand building task overlay in `backend/instructions/tasks/brand-kit-building.md`; confirmation prompts are in the overlay, not in Python |
| No Sitecore write without user confirmation (Principle I) | ✅ PASS | Document upload, pipeline triggers, and Non-AI Editable toggle all require explicit marketer confirmation before the tool call executes (FR-003, FR-007, FR-008, FR-017) |
| New integrations use typed API client layer (Principle VI) | ✅ PASS | `brand_documents.py`, `brand_pipeline.py`, `brand_sections.py` all in `backend/app/clients/`; no inline service calls from graph nodes or route handlers |
| New task behaviors in `instructions/tasks/*.md` (Principle IV) | ✅ PASS | `brand-kit-building.md` overlay governs task detection, confirmation phrasing, and document library display limits; no task logic in Python |
| No profile-switching logic (Principle IV) | ✅ PASS | Additive overlay only; base assistant identity unchanged |
| Guardrail coverage verified (Principle II) | ✅ PASS | Brand kit management is a Sitecore content operations topic; existing guardrails cover it |
| Memory writes use correct store (Principle V) | ✅ PASS | `brand_document_uploads` and `brand_pipeline_runs` are operational tracking tables, not conversation history or user knowledge |
| LLM calls only through `clients/llm.py` (Technology Standards) | ✅ PASS | No new LLM calls introduced; existing graph model node unchanged |
| LangGraph graphs in `services/`, tools in `clients/` (Technology Standards) | ✅ PASS | New `@tool` functions in `clients/`; `check_pipeline_notifications` node extension in `services/chat_graph.py` |
| MLflow tracing present on all LLM/LangGraph paths (Principle VII) | ✅ PASS | Inherits from `mlflow.langchain.autolog()` called at startup; new tool calls are traced automatically |

## Project Structure

### Documentation (this feature)

```text
specs/006-brand-kit-building/
├── plan.md              # This file
├── research.md          # Phase 0 technical decisions
├── data-model.md        # SQLModel table schemas and state transitions
├── quickstart.md        # End-to-end validation guide
├── contracts/
│   └── tool-contracts.md  # LangChain @tool function signatures and return shapes
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (additions to existing layout)

```text
backend/
├── app/
│   ├── clients/
│   │   ├── brand_auth.py          # NEW: shared OAuth token helper for brand service APIs
│   │   ├── brand_documents.py     # NEW: Document Management API + @tool functions
│   │   ├── brand_pipeline.py      # NEW: Pipeline API + @tool functions
│   │   └── brand_sections.py      # NEW: Brand Management API sections + @tool functions
│   ├── services/
│   │   ├── chat_graph.py          # MODIFIED: add check_pipeline_notifications node
│   │   └── brand_building_service.py  # NEW: pipeline status poll + notification injection
│   └── resources/
│       └── models.py              # MODIFIED: add BrandDocumentUpload + BrandPipelineRun tables
├── instructions/
│   └── tasks/
│       └── brand-kit-building.md  # NEW: Track B task overlay
├── alembic/
│   └── versions/
│       └── {hash}_add_brand_building_tables.py  # NEW: migration
└── tests/
    ├── test_brand_documents.py    # NEW
    ├── test_brand_pipeline.py     # NEW
    └── test_brand_sections.py     # NEW
```

**Structure Decision**: Extends the existing layered structure (clients → services → resources). No new layers. `brand_auth.py` avoids duplicating the token-cache pattern already in `mcp_client.py` — it is a shared helper, not a third-party integration wrapper.

## Complexity Tracking

| Exception | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `check_pipeline_notifications` node calls service functions directly (not through ToolNode) | Pipeline status checks must run on every turn automatically — they are not user-invokable tools and must not depend on the LLM deciding to call them | Making it a tool means the LLM might not call it; marking it as always-called violates the tool-only invocation pattern; a dedicated graph node is the correct LangGraph pattern for cross-cutting pre-model logic |
