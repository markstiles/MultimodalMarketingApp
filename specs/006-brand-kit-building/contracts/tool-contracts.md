# Tool Contracts: Brand Kit Building

**Feature**: 006-brand-kit-building | **Date**: 2026-06-18

All functions are LangChain `@tool`-decorated functions defined in `backend/app/clients/`. They are bound to the graph's model node via `.bind_tools()` through `get_all_tools()`. The LLM invokes them; only `ToolNode` executes them.

`conversation_id` is injected into tool calls via `RunnableConfig["configurable"]["conversation_id"]` — it is not a parameter the LLM provides.

---

## `brand_documents.py`

### `list_brand_kit_documents`

```python
@tool
def list_brand_kit_documents(brand_kit_id: str) -> dict:
    """
    List the documents currently in the brand kit's document library.
    Returns the total count and up to all document names with their Draft/Published status.
    Call this before uploading a document so the marketer can see what is already there.
    """
```

**Returns**:
```json
{
  "brand_kit_id": "bk_abc123",
  "total_count": 12,
  "documents": [
    {"document_id": "doc_1", "filename": "brand-guide.pdf", "status": "Published"},
    {"document_id": "doc_2", "filename": "tone-of-voice.docx", "status": "Draft"}
  ]
}
```

**Error cases**:
- `{"error": "brand_service_unavailable", "message": "..."}`
- `{"error": "brand_kit_not_found", "message": "..."}`

---

### `upload_brand_document`

```python
@tool
def upload_brand_document(
    brand_kit_id: str,
    filename: str,
    file_content_base64: str,
    content_type: str,
) -> dict:
    """
    Upload a document to the brand kit's document library.
    The document will be in Draft status after upload and will not affect brand guidelines
    until the processing pipeline is run.
    Only call this after the marketer has explicitly confirmed the upload.
    """
```

**Returns (success)**:
```json
{
  "document_id": "doc_xyz",
  "filename": "brand-guide.pdf",
  "status": "Draft",
  "message": "Document uploaded successfully. It is now in Draft status and will not affect brand guidelines until you run the processing pipeline."
}
```

**Returns (duplicate name warning — returned before upload, tool aborts)**:
```json
{
  "warning": "duplicate_filename",
  "existing_document_id": "doc_abc",
  "filename": "brand-guide.pdf",
  "message": "A document named 'brand-guide.pdf' already exists in this brand kit. Confirm to replace it, or provide a different filename."
}
```

**Error cases**:
- `{"error": "unsupported_format", "supported_formats": ["pdf", "docx", "doc"], "message": "..."}`
- `{"error": "file_too_large", "max_size_mb": 50, "message": "..."}`
- `{"error": "brand_service_unavailable", "message": "..."}`

---

## `brand_pipeline.py`

### `trigger_brand_ingestion`

```python
@tool
def trigger_brand_ingestion(brand_kit_id: str) -> dict:
    """
    Trigger the brand ingestion pipeline for the selected brand kit.
    This processes uploaded Draft documents into brand guidelines (~10-20 minutes).
    WARNING: Processing overwrites existing AI-Editable brand kit sections.
    Only call this after the marketer has explicitly confirmed, including acknowledging
    the overwrite risk and reviewing Non-AI Editable settings if needed.
    """
```

**Returns (success)**:
```json
{
  "pipeline_run_id": "run_abc123",
  "pipeline_type": "ingestion",
  "status": "running",
  "message": "Brand ingestion pipeline started. Processing typically takes 10–20 minutes. You'll be notified here when it completes."
}
```

**Returns (duplicate guard)**:
```json
{
  "warning": "already_running",
  "pipeline_run_id": "run_existing",
  "pipeline_type": "ingestion",
  "message": "The brand ingestion pipeline is already running for this brand kit. You'll be notified when it completes."
}
```

**Error cases**:
- `{"error": "no_draft_documents", "message": "No Draft documents found. Upload documents first before running ingestion."}`
- `{"error": "brand_service_unavailable", "message": "..."}`

---

### `trigger_brand_enrichment`

```python
@tool
def trigger_brand_enrichment(brand_kit_id: str, site_url: Optional[str] = None) -> dict:
    """
    Trigger the brand enrichment pipeline for the selected brand kit.
    Optionally provide a site_url to generate brand kit content from an existing website.
    Processing overwrites existing AI-Editable brand kit sections (~10-20 minutes).
    Only call this after the marketer has explicitly confirmed the action.
    If site_url is provided, validate it is reachable before calling this tool.
    """
```

**Returns (success)**:
```json
{
  "pipeline_run_id": "run_def456",
  "pipeline_type": "enrichment",
  "status": "running",
  "site_url": "https://example.com",
  "message": "Brand enrichment pipeline started from https://example.com. Processing typically takes 10–20 minutes. You'll be notified here when it completes."
}
```

**Returns (duplicate guard)**:
```json
{
  "warning": "already_running",
  "pipeline_run_id": "run_existing",
  "pipeline_type": "enrichment",
  "message": "The brand enrichment pipeline is already running for this brand kit."
}
```

**Error cases**:
- `{"error": "site_unreachable", "site_url": "...", "message": "The site could not be reached. Check the URL and try again."}`
- `{"error": "brand_service_unavailable", "message": "..."}`

---

## `brand_sections.py`

### `list_brand_kit_subsections`

```python
@tool
def list_brand_kit_subsections(brand_kit_id: str) -> dict:
    """
    List the sections and subsections of a brand kit, including each subsection's
    AI-editability status (AI-Editable or Non-AI Editable).
    Call this before triggering a processing pipeline so the marketer can review
    which subsections are protected from overwrite.
    """
```

**Returns**:
```json
{
  "brand_kit_id": "bk_abc123",
  "sections": [
    {
      "section_id": "sec_1",
      "section_name": "Tone of Voice",
      "subsections": [
        {"subsection_id": "sub_1a", "name": "Brand Voice", "is_ai_editable": true},
        {"subsection_id": "sub_1b", "name": "Writing Style", "is_ai_editable": false}
      ]
    }
  ]
}
```

---

### `set_subsection_non_ai_editable`

```python
@tool
def set_subsection_non_ai_editable(
    brand_kit_id: str,
    section_id: str,
    subsection_id: str,
) -> dict:
    """
    Mark a brand kit subsection as Non-AI Editable so it is not overwritten
    during the next processing pipeline run.
    Only call this after the marketer has confirmed which subsection to protect.
    """
```

**Returns (success)**:
```json
{
  "subsection_id": "sub_1a",
  "subsection_name": "Brand Voice",
  "is_ai_editable": false,
  "message": "Subsection 'Brand Voice' is now protected and will not be overwritten during processing."
}
```

**Error cases**:
- `{"error": "subsection_not_found", "message": "..."}`
- `{"error": "brand_service_unavailable", "message": "..."}`

---

## `brand_building_service.py` (service layer — not a tool)

### `check_and_inject_pipeline_notifications`

This is a service-layer function called from the `check_pipeline_notifications` graph node — not a `@tool` function.

```python
async def check_and_inject_pipeline_notifications(
    conversation_id: str,
    db: AsyncSession,
) -> list[str]:
    """
    Query brand_pipeline_runs for running pipeline runs belonging to this conversation.
    For each, call the brand service to check current status.
    Update DB records for completed/failed runs.
    Return a list of notification strings to inject as system messages before the model turn.
    Returns an empty list if no notifications are pending.
    """
```

**Notification message format** (injected as system message):

- Completion: `"[Brand Kit Update] The brand ingestion pipeline for brand kit '{name}' completed successfully. {result_summary}"`
- Failure: `"[Brand Kit Update] The brand ingestion pipeline for brand kit '{name}' failed. {error_message}"`

---

## Tool Registration

All `@tool` functions in `brand_documents.py`, `brand_pipeline.py`, and `brand_sections.py` are registered in `backend/app/clients/tools.py` via `set_mcp_tools()` at application startup (alongside the existing MCP tools). They are bound to the graph's model node when `build_chat_graph()` is called.
