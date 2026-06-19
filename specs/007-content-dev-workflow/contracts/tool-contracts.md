# Tool Contracts: Content Development Workflow

**Feature**: 007-content-dev-workflow | **Date**: 2026-06-19

All functions are defined in `backend/app/clients/content_workflow.py` as LangChain `@tool`-decorated functions, registered via the existing `tools.py` registry, and bound to the LangGraph model node via `.bind_tools()`.

---

## `scan_content_project_status`

Scans all six phase folders in the Sitecore media library and returns the current content project state for the active site. Called at the start of any content development session to detect existing artifacts and compute the recommended next phase.

**Signature**:
```python
def scan_content_project_status(tenant: str, site: str) -> dict
```

**Parameters**:
- `tenant` — tenant name from active session context (e.g., `"acme-corp"`)
- `site` — site name from active session context (e.g., `"us-site"`)

**Returns** (`ContentProjectSummary`):
```json
{
  "tenant": "acme-corp",
  "site": "us-site",
  "phases": [
    {
      "phase": "Research",
      "folder_name": "Research",
      "canonical_filename": "research-brief.docx",
      "media_path": "/sitecore/media library/Project/acme-corp/us-site/Content Strategy/Research/research-brief.docx",
      "status": "complete",
      "modified_at": "2026-05-15T09:22:00Z",
      "age_days": 35
    },
    {
      "phase": "Strategy",
      "folder_name": "Strategy",
      "canonical_filename": "content-strategy.docx",
      "media_path": "/sitecore/media library/Project/acme-corp/us-site/Content Strategy/Strategy/content-strategy.docx",
      "status": "not_started",
      "modified_at": null,
      "age_days": null
    }
    // ... remaining 4 phases
  ],
  "last_completed_phase": "Research",
  "next_recommended_phase": "Strategy",
  "has_stale_phases": false,
  "stale_phase_names": []
}
```

**Error response** (media library unreachable):
```json
{
  "success": false,
  "error": "Unable to scan media library: {details}",
  "phases": []
}
```

**Notes**:
- Makes 6 concurrent async checks (one per phase folder) to minimize scan latency
- A phase is `"stale"` if its artifact is older than 365 days (`age_days > 365`)
- If the `Content Strategy` root folder doesn't exist for this site, all phases return `"not_started"` — this is not an error

---

## `save_phase_artifact`

Generates a Word document (`.docx`) from the provided structured content and saves it to the canonical media library path for the specified phase. Overwrites any existing artifact at that path after the LangGraph flow has received explicit marketer confirmation (the overlay enforces the confirmation gate — this tool does not re-prompt).

**Signature**:
```python
def save_phase_artifact(
    tenant: str,
    site: str,
    phase: str,
    title: str,
    sections: list[dict]
) -> dict
```

**Parameters**:
- `tenant` — tenant name from active session context
- `site` — site name from active session context
- `phase` — one of: `"Research"`, `"Strategy"`, `"Structure"`, `"Content"`, `"Variation"`, `"Execution"`
- `title` — document title (e.g., `"Research Brief — Acme Corp / US Site"`)
- `sections` — list of `{ "heading": str, "content": str, "subsections": [] }` objects that map to the document body

**Returns** (`ArtifactSaveResult`):
```json
{
  "success": true,
  "phase": "Research",
  "media_path": "/sitecore/media library/Project/acme-corp/us-site/Content Strategy/Research/research-brief.docx",
  "filename": "research-brief.docx",
  "overwrite": false
}
```

**Error responses**:
```json
// Unknown phase
{ "success": false, "error": "Unknown phase: 'InvalidPhase'. Must be one of: Research, Strategy, Structure, Content, Variation, Execution." }

// Upload failed
{ "success": false, "error": "Media library upload failed: {details}", "phase": "Research", "filename": "research-brief.docx" }
```

**Notes**:
- `content_workflow_service.py` handles `.docx` generation (python-docx) and Agents API upload
- Phase folder is created automatically if it doesn't exist (FR-013)
- The `overwrite` field is `true` if a previous artifact was replaced at the same path
- This tool MUST only be called after explicit marketer confirmation — the Track B overlay enforces this

---

## `get_phase_artifact_content`

Retrieves the text content of an existing phase artifact from the Sitecore media library. Used to inject prior phase findings into the assistant's context at the start of downstream phases (FR-005: cross-phase reference without re-input from the marketer).

**Signature**:
```python
def get_phase_artifact_content(tenant: str, site: str, phase: str) -> dict
```

**Parameters**:
- `tenant` — tenant name from active session context
- `site` — site name from active session context
- `phase` — one of the six phase names

**Returns** (`ArtifactContentResult`):
```json
{
  "success": true,
  "phase": "Research",
  "media_path": "/sitecore/media library/Project/acme-corp/us-site/Content Strategy/Research/research-brief.docx",
  "text_content": "# Research Brief — Acme Corp / US Site\n\n## Executive Summary\n...",
  "modified_at": "2026-05-15T09:22:00Z"
}
```

**Error responses**:
```json
// Artifact not found
{ "success": false, "error": "No artifact found for phase 'Research'. The phase may not be complete yet.", "phase": "Research", "text_content": null }

// Unreadable artifact
{ "success": false, "error": "Artifact exists but could not be extracted: {details}", "phase": "Research", "text_content": null }
```

**Notes**:
- Uses the document extraction capability (spec 004 compatible) to convert `.docx` → plain text
- On `success: false`, the overlay instructs the assistant to inform the marketer and offer to regenerate the phase from scratch (edge case 2 in spec)
- Read-only; does not require marketer confirmation

---

## Track B Overlay Contract

**Path**: `backend/instructions/tasks/content-dev-workflow.md`

The overlay is loaded by the instruction loader when the assistant detects content development intent. It governs:

| Concern | Overlay Responsibility |
|---------|----------------------|
| Intent detection | Activate when marketer expresses content strategy, content planning, editorial planning intent |
| Session start | Always call `scan_content_project_status` first; present `ContentProjectSummary` to marketer |
| Staleness warnings | If `has_stale_phases: true` and advancing to next phase — warn and offer three choices before proceeding |
| Skip warnings | If marketer skips a phase — confirm with quality impact warning; record skip in conversation context |
| Phase guidance | Per-phase question sets and artifact structure (section headings per phase from research.md Decision 3) |
| Research phase data | Call available analysis tools first; note gaps; supplement with marketer questions |
| Confirmation gate | Require explicit approval before calling `save_phase_artifact`; show artifact preview first (FR-006, FR-007) |
| Cross-phase reference | Call `get_phase_artifact_content` for immediately prior phase before generating next artifact |
| Execution phase | Produce Execution Checklist artifact AND invoke available authoring tools (page scaffolding, component population) with individual confirmation gates |
