# Implementation Plan: Marketing Pipeline

**Branch**: `012-marketing-pipeline` | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

---

## Summary

Replace the six-phase generic content workflow with a five-phase marketing pipeline: **Research** (with Tavily web search), **Strategy**, **Brand Voice** (Sitecore Stream brand kit), **Brief** (flexible entry point), **Campaign** (three tactic documents). The existing media library upload/download infrastructure remains unchanged; only the phase registry, LangChain tools, and instruction overlay are updated. Three new service files and two new client files are added for brand kit operations and web search.

---

## Technical Context

**Language/Version**: Python 3.12 (unchanged)

**Primary New Dependencies**:
- `tavily-python` (NEW) — Tavily web search client; reads `TAVILY_API_KEY` from env

**New env vars**:

| Variable | Purpose |
|----------|---------|
| `TAVILY_API_KEY` | Tavily web search API key (already set) |
| `SITECORE_ORGANIZATION_ID` | Sitecore Stream organization ID — required for Brand Management and Document Management API path params |

**Auth**: The existing `get_sitecore_automation_token()` in `sitecore_auth.py` already uses `audience=https://api.sitecorecloud.io`. The same token is accepted by the Brand Management API, Document Management API, and Brand Review API — no auth changes needed.

---

## Files Changed

### Modified

| File | Change |
|------|--------|
| `backend/requirements.txt` | Add `tavily-python` |
| `backend/app/services/content_workflow_service.py` | Replace `PHASE_ARTIFACT_MAP` with 5-phase model; update all phase references |
| `backend/app/clients/content_workflow.py` | Update tool docstrings and valid phase lists in all three tools |
| `backend/instructions/tasks/content-dev-workflow.md` | Complete rewrite: new 5-phase marketing pipeline overlay |
| `backend/tests/test_content_workflow.py` | Update phase names, path expectations, and mutation assertions |

### New Files

| File | Purpose |
|------|---------|
| `backend/app/services/brand_kit_service.py` | Stream API: list/create brand kits, read sections/fields, upload documents, run brand review |
| `backend/app/services/marketing_research_service.py` | Tavily web search wrapper |
| `backend/app/clients/brand_kit.py` | LangChain `@tool` functions for brand kit operations |
| `backend/app/clients/marketing_research.py` | LangChain `@tool` function for web search |

---

## Phase Artifact Registry

All five phase artifacts live **flat** under a single `Content Strategy` folder — no per-phase subfolders. Each artifact has a unique filename so the flat layout is unambiguous and simpler to navigate in the Sitecore media library.

```python
PHASE_ARTIFACT_MAP: dict[str, dict[str, str]] = {
    "Research":   {"filename": "research-brief.docx"},
    "Strategy":   {"filename": "marketing-strategy.docx"},
    "BrandVoice": {"filename": "brand-voice-summary.docx"},
    "Brief":      {"filename": "campaign-brief.docx"},
    "Campaign":   {"filename": "campaign-plan.docx"},
}

CONTENT_STRATEGY_FOLDER = "Content Strategy"
```

Resulting media paths (example tenant `acme-corp`, site `us-site`):
```
/sitecore/Media Library/Project/acme-corp/us-site/Content Strategy/research-brief
/sitecore/Media Library/Project/acme-corp/us-site/Content Strategy/marketing-strategy
/sitecore/Media Library/Project/acme-corp/us-site/Content Strategy/brand-voice-summary
/sitecore/Media Library/Project/acme-corp/us-site/Content Strategy/campaign-brief
/sitecore/Media Library/Project/acme-corp/us-site/Content Strategy/campaign-plan
```

**Key notes**:
- `ensure_phase_upload_folders` now only creates the `Content Strategy` folder — no per-phase subfolders
- `build_artifact_media_path` strips the `.docx` extension (this instance's `InvalidItemNameChars` includes `.`)

---

## New Services

### `backend/app/services/marketing_research_service.py`

```python
async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web via Tavily. Returns list of {url, title, content} dicts."""
```

- Reads `TAVILY_API_KEY` from env; raises `RuntimeError` if missing
- Uses `tavily-python` client: `TavilyClient.search(query, max_results=max_results)`
- Returns cleaned results; catches and re-raises as `RuntimeError` on API errors

### `backend/app/services/brand_kit_service.py`

All functions accept a `stream_token: str` parameter (obtained via `get_sitecore_automation_token()`). All use `SITECORE_ORGANIZATION_ID` from env. Base URL: `https://edge-platform.sitecorecloud.io/stream/ai-brands-api`.

```python
async def list_brand_kits(stream_token: str) -> list[dict]:
    """GET /api/brands/v1/organizations/{orgId}/brandkits — returns list of {id, name, status}"""

async def create_brand_kit(name: str, stream_token: str) -> dict:
    """POST /api/brands/v1/organizations/{orgId}/brandkits — returns {id, name}"""

async def get_brand_kit_voice_sections(kit_id: str, stream_token: str) -> dict:
    """Read Brand Context, Tone of Voice, and Do's and Don'ts fields from the kit.
    
    Steps:
    1. GET /api/brands/v1/organizations/{orgId}/brandkits/{kitId}/sections
    2. For each of the three target sections, GET /api/brands/v2/.../fields
    3. Return {brand_context: str, tone_of_voice: str, dos_and_donts: str}
    """

async def upload_brand_document(
    kit_id: str,
    pdf_bytes: bytes,
    filename: str,
    stream_token: str,
) -> dict:
    """POST /api/documents/v2/organizations/{orgId}/documents (multipart)
    
    create_request JSON includes:
    - setMetadata: true
    - references: [{type: "brandkit", id: kit_id, path: "..."}]
    Returns {id, status, title}
    """

async def run_brand_review(
    kit_id: str,
    content: str,
    stream_token: str,
) -> dict:
    """POST https://edge-platform.sitecorecloud.io/stream/ai-skills-api/api/skills/v1/brandreview/generate
    
    input: {content: <text>}
    Returns {overall_score, reviews: [{sectionId, score, reason, suggestion}]}
    """
```

---

## New Client Tools

### `backend/app/clients/marketing_research.py`

```python
@tool
async def search_market_research(queries: list[str]) -> dict:
    """
    Search the web for competitive intelligence and market data.
    
    Call this when the marketer has requested AI-assisted research. Pass a list
    of search queries — typically 3-5 targeted queries covering competitor
    positioning, market trends, and audience pain points.
    
    Args:
        queries: List of search query strings (3-5 recommended)
    
    Returns research_results with per-query results and a synthesized summary.
    """
```

### `backend/app/clients/brand_kit.py`

```python
@tool
async def list_org_brand_kits() -> dict:
    """
    List all brand kits in the Sitecore Stream organization.
    
    Call this at the start of the Brand Voice phase to check for existing
    brand kits. Returns a list with id, name, and status for each kit.
    """

@tool
async def get_brand_voice_summary(kit_id: str) -> dict:
    """
    Read the Brand Context, Tone of Voice, and Do's & Don'ts from a brand kit.
    
    Call this after the marketer has selected a brand kit. Returns the key
    brand voice guidelines needed to inform content generation.
    
    Args:
        kit_id: Brand kit UUID from list_org_brand_kits
    """

@tool
async def import_brand_document(kit_id: str, file_url: str, filename: str) -> dict:
    """
    Upload a PDF brand document to a Sitecore Stream brand kit.
    
    Call this when the marketer wants to import brand guidelines. The document
    is attached to the brand kit and can be used by Sitecore to populate brand
    kit sections during brand ingestion.
    
    Args:
        kit_id: Brand kit UUID to attach the document to
        file_url: URL or base64-encoded content of the PDF
        filename: Display name for the document (e.g. "Brand Guidelines 2025.pdf")
    """

@tool
async def review_content_against_brand(kit_id: str, content: str) -> dict:
    """
    Score content against brand kit guidelines using the Sitecore Brand Review API.
    
    Use this optionally before saving a Brief or Campaign artifact to check brand
    alignment. Returns a 1-5 compliance score per section with reasons and suggestions.
    
    Args:
        kit_id: Brand kit UUID to evaluate against
        content: The text content to review (markdown or plain text)
    """
```

---

## Instruction Overlay Rewrite

`backend/instructions/tasks/content-dev-workflow.md` is completely replaced. Key behaviors in the new overlay:

### Activation triggers (same as before, broader marketing language)
Content strategy, campaign planning, marketing brief, brand voice, competitor research, audience targeting, campaign tactics

### Session start flow
1. Call `scan_marketing_project_status` (the renamed `scan_content_project_status`)
2. Present project status table with 5 new phases
3. Detect entry point (marketer already has brief / strategy / etc.)

### Research phase
- Ask: "Do you already have competitive analysis data, or would you like me to research your market and competitors?"
- If research requested: ask for product category and competitor names, then call `search_market_research` with targeted queries
- Synthesize results; do not present raw search output
- Supplement with marketer input questions if needed

### Brand Voice phase
- Call `list_org_brand_kits` first
- If kits exist: present list and ask which to use, or offer to import new docs
- If no kits: offer to create one and import brand PDF documents
- After kit selection: call `get_brand_voice_summary`; use findings to produce Brand Voice Summary artifact

### Brief entry point
If marketer says they already have a brief (or any similar phrasing), jump directly to Brief phase with compensating questions.

### Campaign phase
Offer three tactic documents. Marketer selects one, some, or all. Each reads the Campaign Brief automatically.

### Cross-phase context injection
Before each phase (except Research), call `get_phase_artifact_content` for the previous phase(s) and surface findings as context automatically.

---

## Test Updates

`backend/tests/test_content_workflow.py` changes:

1. Update `PHASE_ARTIFACT_MAP` expectations to 5 new phases
2. Update `test_all_phases_produce_correct_paths` with new phase names and item names:
   - `"Research"` → `"research-brief"`
   - `"Strategy"` → `"marketing-strategy"`
   - `"BrandVoice"` → `"brand-voice-summary"` (folder path uses `"Brand Voice"`)
   - `"Brief"` → `"campaign-brief"`
   - `"Campaign"` → `"campaign-plan"`
3. Remove tests for old phases: Structure, Content, Variation, Execution
4. Update `scan_content_project_status` tool tests for 5-phase output
5. Add basic `brand_kit_service` tests (mocked httpx) for list_brand_kits and get_brand_kit_voice_sections

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle IV) | ✅ PASS | All phase guidance, search intent detection, entry point logic live in `content-dev-workflow.md` overlay |
| No Sitecore write without user confirmation (Principle I) | ✅ PASS | `save_phase_artifact` and `import_brand_document` both require explicit marketer approval per overlay |
| No web search without marketer request (FR-003) | ✅ PASS | Overlay asks intent before calling `search_market_research`; tool may not be called speculatively |
| New integrations use typed API client layer (Principle VI) | ✅ PASS | `brand_kit.py` and `marketing_research.py` in `clients/`; service helpers in `services/` |
| New task behaviors in `instructions/tasks/*.md` (Principle IV) | ✅ PASS | Overlay completely governs phase sequencing, entry point detection, skip/resume flows |

---

## Implementation Order

1. `requirements.txt` — add `tavily-python`
2. `content_workflow_service.py` — update `PHASE_ARTIFACT_MAP` (breaks nothing downstream immediately)
3. `marketing_research_service.py` — new; no dependencies on other changes
4. `brand_kit_service.py` — new; depends only on `sitecore_auth.py` (unchanged)
5. `content_workflow.py` — update tool docstrings and phase lists
6. `marketing_research.py` client — new tool; depends on service
7. `brand_kit.py` client — new tools; depends on service
8. `content-dev-workflow.md` — rewrite overlay
9. `test_content_workflow.py` — update tests for new phases
10. Add `SITECORE_ORGANIZATION_ID` to `.env.example` and Railway env var docs
