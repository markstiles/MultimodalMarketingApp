# Data Model: Content Development Workflow

**Feature**: 007-content-dev-workflow | **Date**: 2026-06-19

> No new SQLModel tables. The Sitecore media library is the persistent state store.
> This document defines runtime data shapes (Python dataclasses/Pydantic-compatible dicts)
> and the media library path schema used by the @tool functions.

---

## Media Library Path Schema

The content development workflow uses a deterministic, convention-based path structure in the Sitecore media library. All paths are resolvable at runtime from the active session context.

```
/sitecore/media library/
  └── Project/
        └── {tenant-name}/
              └── {site-name}/
                    └── Content Strategy/
                          ├── Research/
                          │     └── research-brief.docx
                          ├── Strategy/
                          │     └── content-strategy.docx
                          ├── Structure/
                          │     └── content-structure.docx
                          ├── Content/
                          │     └── content-plan.docx
                          ├── Variation/
                          │     └── variation-plan.docx
                          └── Execution/
                                └── execution-checklist.docx
```

**Phase-to-filename mapping** (canonical, fixed):

| Phase | Folder Name | Canonical Filename |
|-------|-------------|-------------------|
| Research | `Research` | `research-brief.docx` |
| Strategy | `Strategy` | `content-strategy.docx` |
| Structure | `Structure` | `content-structure.docx` |
| Content | `Content` | `content-plan.docx` |
| Variation | `Variation` | `variation-plan.docx` |
| Execution | `Execution` | `execution-checklist.docx` |

---

## Runtime Data Shapes

These are Python `TypedDict`-compatible shapes returned by the `@tool` functions. They are not database models.

### PhaseStatus (enum)

```python
class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"   # No artifact at canonical path
    COMPLETE    = "complete"      # Artifact exists, age <= 12 months
    STALE       = "stale"         # Artifact exists, age > 12 months
```

### PhaseInfo

Returned per-phase inside `ContentProjectSummary`.

```python
class PhaseInfo(TypedDict):
    phase: str              # e.g. "Research"
    folder_name: str        # e.g. "Research"
    canonical_filename: str # e.g. "research-brief.docx"
    media_path: str         # Full media library path to the canonical file
    status: PhaseStatus     # not_started | complete | stale
    modified_at: str | None # ISO-8601 UTC, None if not_started
    age_days: int | None    # Days since last modification, None if not_started
```

### ContentProjectSummary

Return type of `scan_content_project_status`.

```python
class ContentProjectSummary(TypedDict):
    tenant: str
    site: str
    phases: list[PhaseInfo]          # All 6 phases in order
    last_completed_phase: str | None # Phase name of the most recently completed phase
    next_recommended_phase: str | None  # Phase name of the next phase to work on
    has_stale_phases: bool           # True if any complete phase is stale
    stale_phase_names: list[str]     # Names of stale phases
```

**Staleness rule**: A phase artifact is stale if `age_days > 365`. Computed at scan time. The `next_recommended_phase` is the first `NOT_STARTED` phase in sequence; if all phases are complete, returns `None`.

### ArtifactSaveResult

Return type of `save_phase_artifact`.

```python
class ArtifactSaveResult(TypedDict):
    success: bool
    phase: str
    media_path: str      # Full media library path where artifact was saved
    filename: str        # Canonical filename (e.g., "research-brief.docx")
    overwrite: bool      # True if an existing artifact was overwritten
    error: str | None    # None on success
```

### ArtifactContentResult

Return type of `get_phase_artifact_content`.

```python
class ArtifactContentResult(TypedDict):
    success: bool
    phase: str
    media_path: str
    text_content: str | None  # Extracted plain text, None if retrieval failed
    modified_at: str | None   # ISO-8601 UTC
    error: str | None
```

---

## State Transitions

Phase artifacts follow a simple two-state external lifecycle (from the workflow's perspective):

```
Absent → [save_phase_artifact] → Present (complete)
Present (complete) → [12+ months pass] → Present (stale)
Present (stale)    → [save_phase_artifact] → Present (complete)  ← overwrite
```

No explicit "In Progress" state is persisted — phase work in progress lives only in the conversation context. A phase is only `COMPLETE` once its artifact is successfully saved to the media library.

---

## WordDoc Generation Shape

The service helper (`content_workflow_service.py`) generates Word docs using this internal structure (passed to `python-docx`):

```python
class PhaseArtifactContent(TypedDict):
    phase: str           # e.g. "Research"
    title: str           # e.g. "Research Brief — Acme Corp / US Site"
    generated_at: str    # ISO-8601 UTC
    tenant: str
    site: str
    sections: list[ArtifactSection]

class ArtifactSection(TypedDict):
    heading: str         # Section title (H2)
    content: str         # Body text (may include newlines for paragraphs)
    subsections: list[ArtifactSubsection]  # Optional H3 items

class ArtifactSubsection(TypedDict):
    heading: str
    content: str
```
