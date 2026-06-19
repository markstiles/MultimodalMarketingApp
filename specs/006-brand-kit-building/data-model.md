# Data Model: Brand Kit Building

**Feature**: 006-brand-kit-building | **Date**: 2026-06-18

## Overview

This feature adds two operational tracking tables to PostgreSQL. They do not store brand content (that lives in the Sitecore brand service) — they track the outcome of upload and pipeline operations so the assistant can surface notifications without the marketer needing to ask.

---

## Tables

### `brand_document_uploads`

Tracks every document upload initiated through the assistant. Provides an audit trail and allows the assistant to reference recent uploads within a conversation.

```python
class BrandDocumentUpload(SQLModel, table=True):
    __tablename__ = "brand_document_uploads"
    __table_args__ = (
        Index("ix_brand_doc_uploads_conversation", "conversation_id"),
        Index("ix_brand_doc_uploads_brand_kit", "brand_kit_id"),
    )

    id: str = Field(default_factory=cuid, primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    brand_kit_id: str                   # Sitecore brand kit ID
    document_service_id: Optional[str]  # ID returned by the brand document service on success
    filename: str
    content_type: str                   # e.g., "application/pdf", "application/msword"
    file_size_bytes: int
    status: BrandDocumentStatus         # "uploading" | "uploaded" | "failed"
    error_message: Optional[str]        # set on status="failed"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
```

**Enum**:
```python
class BrandDocumentStatus(str, enum.Enum):
    uploading = "uploading"
    uploaded = "uploaded"
    failed = "failed"
```

**Notes**:
- `document_service_id` is `None` until the brand service confirms the upload.
- This table tracks the upload operation only. The Draft/Published lifecycle of the document in the brand service is tracked by the brand service itself; the assistant queries it on demand rather than caching it locally.

---

### `brand_pipeline_runs`

Tracks every pipeline run triggered through the assistant. This is the source of truth for the lazy-polling notification system — the `check_pipeline_notifications` graph node reads this table to find runs that need status updates.

```python
class BrandPipelineRun(SQLModel, table=True):
    __tablename__ = "brand_pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_conversation_status", "conversation_id", "status"),
        Index("ix_pipeline_runs_brand_kit_type_status", "brand_kit_id", "pipeline_type", "status"),
    )

    id: str = Field(default_factory=cuid, primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    brand_kit_id: str
    pipeline_type: BrandPipelineType      # "ingestion" | "enrichment"
    pipeline_run_id: str                  # Run ID returned by the brand pipeline service
    site_url: Optional[str]              # Set only for site-based enrichment runs
    status: BrandPipelineRunStatus       # "running" | "completed" | "failed"
    triggered_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime]
    result_summary: Optional[str]        # Plain-language summary from service response
    error_message: Optional[str]
    notification_sent: bool = Field(default=False)  # True once the in-conv notification has been injected
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
```

**Enums**:
```python
class BrandPipelineType(str, enum.Enum):
    ingestion = "ingestion"
    enrichment = "enrichment"

class BrandPipelineRunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
```

**Notes**:
- `notification_sent` prevents the same completion event from being injected into the conversation multiple times across successive turns.
- The `(brand_kit_id, pipeline_type, status)` index supports the duplicate-run guard in FR-011.
- The `(conversation_id, status)` index supports the notification check query run before each model turn.

---

## State Transitions

### BrandDocumentUpload

```
[created] → uploading → uploaded
                      → failed
```

- `uploading`: set immediately when the tool begins the multipart upload
- `uploaded`: set when the brand document service returns a success response with a document ID
- `failed`: set when the brand service returns an error; `error_message` is populated

### BrandPipelineRun

```
[created] → running → completed
                    → failed
```

- `running`: set when the pipeline service accepts the trigger and returns a run ID
- `completed`/`failed`: set by the `check_pipeline_notifications` node when polling reveals a terminal state; `completed_at` and `result_summary`/`error_message` are populated

---

## External Brand Service State (not stored locally)

The following states exist in the Sitecore brand service but are queried on-demand rather than cached in the local DB:

| Entity | States | How accessed |
|--------|--------|--------------|
| BrandDocument (service side) | Draft, Published | `list_brand_kit_documents` tool queries on each upload flow |
| BrandKitSubsection | AI-Editable, Non-AI Editable | `list_brand_kit_subsections` tool queries before pipeline confirmation |
| BrandKit | Published, Draft, In Process, Failed | Already handled by spec 005 (brand kit integration) |

---

## Alembic Migration

File: `backend/alembic/versions/{hash}_add_brand_building_tables.py`

```python
def upgrade() -> None:
    op.create_table(
        "brand_document_uploads",
        # columns per model above
    )
    op.create_index("ix_brand_doc_uploads_conversation", "brand_document_uploads", ["conversation_id"])
    op.create_index("ix_brand_doc_uploads_brand_kit", "brand_document_uploads", ["brand_kit_id"])

    op.create_table(
        "brand_pipeline_runs",
        # columns per model above
    )
    op.create_index("ix_pipeline_runs_conversation_status", "brand_pipeline_runs", ["conversation_id", "status"])
    op.create_index("ix_pipeline_runs_brand_kit_type_status", "brand_pipeline_runs", ["brand_kit_id", "pipeline_type", "status"])

def downgrade() -> None:
    op.drop_table("brand_document_uploads")
    op.drop_table("brand_pipeline_runs")
```
