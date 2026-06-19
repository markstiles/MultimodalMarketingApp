# Research: Content Development Workflow

**Feature**: 007-content-dev-workflow | **Date**: 2026-06-19

---

## Decision 1: Media library artifact detection approach

**Decision**: Detect existing phase artifacts by calling the Sitecore XM Cloud Items API (or equivalent path-based content lookup endpoint) directly from `content_workflow.py` — one call per phase folder, run concurrently.

**Rationale**: Phase detection must be deterministic and reliable — it cannot depend on the LLM deciding when to invoke a tool. A direct API call to check for a file at a canonical path is the most reliable approach. The path is fully determined at runtime (`/sitecore/media library/Project/{tenant}/{site}/Content Strategy/{phase}/{canonical-filename}`), so no fuzzy search is needed. The 6 concurrent async calls keep scan time under 3 seconds. Auth reuses the existing `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION` credentials (consistent with `mcp_client.py` pattern).

**Alternatives considered**:
- Use existing Marketer MCP `search_content_items` tool (rejected: MCP tool invocation is LLM-controlled, not deterministic; would require LLM to issue 6 tool calls on every session start)
- Single GraphQL path-filter query for all 6 artifacts (rejected: more complex to construct; error in one path would fail the whole scan)
- Store phase state in PostgreSQL (rejected: spec explicitly uses media library as state store; a DB mirror would create a dual-source-of-truth)

---

## Decision 2: Phase artifact file format and generation

**Decision**: Generate phase artifacts as `.docx` files using `python-docx` in memory (`BytesIO`), then upload to the media library via the Sitecore Agents API media upload endpoint.

**Rationale**: The spec requires `.docx` (Word) format for marketer familiarity and editability outside the assistant. `python-docx` is the standard Python library for programmatic Word document generation — lightweight, well-maintained, no external service dependency. Generating in memory (BytesIO, then base64 for upload) avoids disk I/O and follows the same pattern established in spec 006 for binary content uploads. The Agents API is confirmed as the correct upload path per project memory (GraphQL not needed).

**Alternatives considered**:
- Plain text or Markdown upload (rejected: spec explicitly requires `.docx`)
- HTML-to-Word conversion (rejected: additional dependency; `python-docx` is simpler for structured documents)
- PDF generation (rejected: PDFs are not marketer-editable)
- docxtpl templates (rejected: overkill; the assistant generates the content structure dynamically)

---

## Decision 3: Word document structure for phase artifacts

**Decision**: Each phase artifact is a structured Word document with: (1) a title heading (phase name + site name), (2) metadata block (generated date, site, tenant), (3) section headings corresponding to the phase's key outputs, (4) assistant-generated content under each section. Documents use heading styles (H1, H2, H3) and body text only — no tables, charts, or embedded objects in v1.

**Rationale**: Simple heading + body structure is reliable with `python-docx`, renders consistently across Word/Google Docs/LibreOffice, and is easy for the marketer to review and edit. More complex formatting (tables, charts) can be added in a future iteration.

**Phase artifact structure by type**:
- `research-brief.docx` — Sections: Executive Summary, Audience Analysis, Competitive Landscape, Content Performance Insights, Key Opportunities
- `content-strategy.docx` — Sections: Executive Summary, Content Goals & KPIs, Messaging Pillars, Editorial Themes, Audience-to-Content Mapping
- `content-structure.docx` — Sections: Executive Summary, Site Architecture Recommendations, Content Types & Templates, Page Hierarchy, Navigation Structure
- `content-plan.docx` — Sections: Executive Summary, Editorial Calendar (text-based), Content Briefs by Theme, Distribution Channels
- `variation-plan.docx` — Sections: Executive Summary, Personalization Segments, A/B Testing Candidates, Experimentation Roadmap
- `execution-checklist.docx` — Sections: Executive Summary, Sitecore Content Actions (page creation, component population), Implementation Sequence, Sign-off Checklist

**Alternatives considered**:
- Single template for all phases (rejected: section headings are phase-specific; a single template would need too many conditional sections)
- Richer formatting with tables (deferred to future iteration)

---

## Decision 4: Cross-phase artifact reference approach

**Decision**: When a downstream phase begins, retrieve the prior phase artifact via `get_phase_artifact_content` (which calls the existing document extraction capability from spec 004) and inject the key findings as context into the conversation before the LLM generates the next artifact.

**Rationale**: The spec requires (FR-005) that "phase artifacts MUST incorporate findings from prior completed phases." Injecting extracted content into the conversation context is the simplest, most reliable approach — it doesn't require a separate RAG pipeline and keeps the context window manageable if only key sections are extracted. Spec 004's document extraction handles the `.docx` → text conversion.

**Alternatives considered**:
- Re-upload prior artifact to vector store for semantic retrieval (rejected: overkill for 6 sequential documents; full-document injection is sufficient given typical brief sizes)
- LLM reads artifact summary from the overlay (rejected: the overlay can't contain dynamic artifact content)
- Always re-read all prior artifacts at phase start (rejected: context window cost; only the immediately prior phase needs full content; earlier phases are summarized in the overlay's running summary)

---

## Decision 5: Research phase tool integration

**Decision**: The `scan_content_project_status` tool (and the Research phase) leverages existing analysis tool outputs from the MCP server where available (content audit, SEO tools, competitive analysis). If the relevant MCP tools are unavailable or return empty results, the Research phase falls back gracefully to a marketer questionnaire — no error, no blocking. The overlay tracks which data sources succeeded and instructs the assistant to note gaps in the Research Brief.

**Rationale**: FR-016 explicitly requires graceful degradation. The existing Marketer MCP provides content analysis capabilities. Making tool availability non-blocking ensures the workflow can be used before all analysis specs are implemented. The overlay (not the Python tool) decides what questions to ask based on tool availability.

**Alternatives considered**:
- Hard-require all analysis tools before Research phase can proceed (rejected: would block the workflow; FR-016 prohibits this)
- Build dedicated analysis tool calls into `content_workflow.py` (rejected: those tools belong to their own specs; this spec should leverage existing MCP capabilities, not duplicate them)

---

## Decision 6: Media library folder creation

**Decision**: Before uploading an artifact, `save_phase_artifact` checks if the phase folder exists (part of the same scan logic) and creates it via the Agents API if missing — this is an implicit precondition of the upload, not a separate user-visible step.

**Rationale**: FR-013 requires folder creation before save. Handling it transparently inside the upload tool keeps the conversation flow clean — the marketer confirms the artifact save, not the folder creation. The Agents API media upload endpoint typically creates parent folders automatically on upload; if not, an explicit folder-create call is prepended.

**Alternatives considered**:
- Require marketer to create folders manually (rejected: poor UX, unnecessary friction)
- Create all folders on project start (rejected: unnecessary; many projects may not reach all phases)
- Separate `create_phase_folder` tool (rejected: folder creation is a side effect of upload, not a user-facing action)
