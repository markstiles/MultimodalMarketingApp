# Implementation Plan: Multimodal Image Search

**Branch**: `main` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

## Summary

Semantic image search over the Sitecore XM Cloud media library using Cohere multimodal embeddings stored in pgvector. Images are crawled via the Sitecore SSC REST API and indexed with 1024-dimensional float vectors. Chat users describe what they're looking for in natural language; a Cohere text embedding is compared against stored image vectors with cosine similarity, and results are shown in a paginated thumbnail grid with selection capability.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 (frontend)

**Primary Dependencies**:
- `cohere` SDK — `embed-english-v3.0` model, 1024-dimensional, shared text+image embedding space
- `pgvector` PostgreSQL extension — cosine similarity via `<=>` operator
- `httpx` — async HTTP for SSC REST API crawling
- LangChain `@tool` decorator — chat tool integration
- Next.js React — thumbnail grid UI component

**Storage**: PostgreSQL with pgvector — `image_embeddings` table, unique on `(item_id, environment, site_id)`

**Target Platform**: XM Cloud (SaaS Sitecore)

## Media Library Crawl — SSC REST API

XM Cloud Edge GraphQL (`/sitecore/api/graph/edge`) does **not** index media library items. The correct approach is the Sitecore SSC REST API:

- Resolve folder by path: `GET {cm_host}/sitecore/api/ssc/item/?path={path}&database=master`
- List children (paginated): `GET {cm_host}/sitecore/api/ssc/item/{id}/children?database=master&skip={n}&take=50`
- Auth: `Authorization: Bearer {oauth_token}` — no `sc_apikey` needed for SSC

**BFS traversal**: non-image template items are queued as folders; image items are embedded.

### XM Cloud Image Template IDs

Six templates must be recognised (3 versioned, 3 unversioned):

| Variant | Template ID |
|---------|------------|
| Versioned webp | `F6F72B6B-F5D5-4ED0-8701-45266461F77B` |
| Versioned jpeg | `EB3FB96C-D56B-4AC9-97F8-F07B24BB9BF7` |
| Versioned image | `C97BA923-8009-4858-BDD5-D8BE5FCCECF7` |
| Unversioned webp | `309EB383-99B6-4722-9FAB-58D8AE802D72` |
| Unversioned jpeg | `DAF085E8-602E-43A6-8299-038FF171349F` |
| Unversioned image | `F1828A2C-7E5D-4BBD-98CA-320474871548` |

Fallback: also match `TemplateName.lower() == "image"`.

### Default folder path

When no explicit folder is given, scope to the site's media folder to avoid crawling unrelated projects:

```
/sitecore/media library/Project/{collection}/{site_name}
```

`collection` is resolved via `GET /api/v1/collections/{collectionId}` (the Sites API only returns `collectionId`, not a name).

## SQL Patterns

`::type` PostgreSQL cast syntax after a named SQLAlchemy `text()` parameter (`:param::vector`) causes an asyncpg `ProgrammingError`. Workaround: inline vector literals as f-string SQL:

```python
embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"
sql = text(f"... '{embedding_literal}'::vector ...")
```

`site_id` values must be normalised to uppercase before storage and query — the Sitecore SDK returns lowercase GUIDs but indexing typically uses uppercase.

## Collection Resolution

The XM Cloud Sites API (`GET /api/v1/sites/{id}`) returns `collectionId` (GUID) but not a human-readable collection name. Resolution chain:

1. Check explicit name fields (`collectionName`, `collection`, `tenantName`) in the site response
2. `GET /api/v1/collections/{collectionId}` — authoritative lookup
3. Fall back to raw `collectionId` GUID

Results are cached in `_collection_cache` to avoid repeated API calls.

## Cohere Rate Limiting

The Cohere `/v2/embed` endpoint enforces rate limits during bulk indexing. `_cohere_post()` retries up to 5 times with exponential backoff (1 s → 2 s → 4 s → 8 s), honouring the `Retry-After` response header when present.

## Chat Integration — SSE event flow

```
search_site_images tool completes
  → LangGraph on_tool_end event
  → chat_service.py emits {"type": "image_results", "results": [...]}
  → useChat.ts stores results in pendingImageResultsRef
  → on "done" event, attaches imageResults to the finalized Message
  → MessageBubble renders <ImageResultsPanel> below the text response
```

## Hybrid Search

Images support three simultaneous search modes, combined into a single SQL query.

### Index-time (per image during crawl)

1. **Cohere multimodal embedding** (existing) — 1024-d float vector for semantic search
2. **OpenAI Vision description** (new) — GPT-4o-mini generates a ≤100-word caption; stored in `description TEXT` column
3. **tsvector** (new) — computed from `description || alt_text || item_name` and stored in `search_vector TSVECTOR` column

### Query-time SQL

```sql
WITH fts AS (SELECT plainto_tsquery('english', :query) AS q)
SELECT ie.item_id, ie.item_name, ie.media_path, ie.alt_text,
       ROUND((1 - (ie.embedding <=> '{vec}'::vector)) * 0.7 +
             COALESCE(ts_rank(ie.search_vector, fts.q), 0.0) * 0.3, 4) AS score
FROM image_embeddings ie, fts
WHERE ie.site_id = :site_id AND ie.collection = :collection AND ie.environment = :environment
  AND (
    (1 - (ie.embedding <=> '{vec}'::vector)) > 0.25   -- semantic match
    OR (ie.search_vector IS NOT NULL AND ie.search_vector @@ fts.q)  -- FTS match
    OR (ie.description IS NOT NULL AND ie.description % :query)      -- trigram fallback
  )
ORDER BY score DESC LIMIT :limit
```

- **Semantic weight**: 70% cosine similarity
- **Text weight**: 30% `ts_rank` FTS score
- Trigram `%` operator (pg_trgm) acts as a fallback for typo tolerance
- `plainto_tsquery` used (safe with arbitrary input, no syntax errors)

### Database changes

Migration `f7a8b9c1d2e3` adds:
- `pg_trgm` extension
- `description TEXT` column
- `search_vector TSVECTOR` column
- GIN index on `search_vector` (FTS)
- GIN trigram index on `description` (fuzzy keyword)

## UI — ImageResultsPanel

- **Grid**: 4 columns × 3 rows = 12 items per page, square aspect-ratio thumbnails
- **Pagination**: previous/next arrows, "X / Y pages", "Showing A–B of N images" header
- **Selection**: click thumbnail to toggle; selected items show purple checkmark ring; "Use N selected" button appears
- **Open in new tab**: external link icon top-right of each tile, visible on hover (avoids overlap with path label at bottom)
- **Path label**: `media_path` shown at bottom of tile on hover
- **Fallback**: placeholder image icon when `media_url` is unavailable
- **Use selected**: sends `"Use these images: {media_path, ...}"` as a chat message

## Project Structure

```text
backend/
├── app/
│   ├── clients/
│   │   └── image_search.py          # LangChain tool wrappers
│   └── services/
│       └── image_search_service.py  # Cohere embed, SSC crawl, pgvector upsert/search
└── scripts/
    └── index_images.py              # Standalone CLI indexer

frontend/
└── components/
    └── ImageResultsPanel.tsx        # Paginated thumbnail grid with selection
```
