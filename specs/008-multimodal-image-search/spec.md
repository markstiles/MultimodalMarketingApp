# Feature Specification: Multimodal Image Search

**Feature Branch**: `008-multimodal-image-search`

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Multimodal image search — catch a Sitecore webhook event to extract the item ID of a newly uploaded/updated media image, retrieve the image via GraphQL, vectorize it with the Cohere multimodal embedding API, and store the vector + item ID reference in PostgreSQL. The chat interface can then embed a natural-language query with Cohere text embeddings and perform a similarity search against the stored image vectors to return matching Sitecore media items. A separate initialization flow crawls the Sitecore media library via GraphQL (either the global media library or a user-specified folder) and backfills embeddings for all existing images."

---

## Clarifications

### Session 2026-06-19

- Q: Should image search results be scoped to the marketer's current tenant and site, or global across all indexed images? → A: Scoped to environment + tenant + site — no crossover between environments, tenants, or sites.
- Q: If the backend is temporarily unavailable when Sitecore fires a webhook, how should missed events be handled? → A: Out of scope for v1 — rely on Sitecore's built-in webhook retry behavior; document as a known limitation; marketer can re-crawl to reconcile if needed.
- Q: Does the concurrent crawl prevention lock (FR-011) apply globally or per environment+tenant+site? → A: Per environment+tenant+site — different tenants/sites can crawl concurrently.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Marketer Searches for Images by Description (Priority: P1)

A marketer is building a campaign and wants to find images already in the Sitecore media library that match a concept or scene. They type a description into the chat (e.g., "find an image of a person using a laptop outdoors") and receive a list of matching Sitecore media items they can use directly.

**Why this priority**: This is the primary user-facing value of the feature — without it, the indexing work has no visible benefit.

**Independent Test**: With at least 10 images indexed, send a natural language image search query in the chat. Verify the assistant returns relevant Sitecore item IDs and media paths within 2 seconds.

**Acceptance Scenarios**:

1. **Given** images are indexed, **When** the marketer asks "find images of people in a meeting room," **Then** the assistant returns up to 5 Sitecore media items ranked by visual and semantic relevance, each showing the item name and media path.
2. **Given** no images are indexed yet, **When** the marketer sends an image search query, **Then** the assistant informs them the image index is empty and suggests running the initialization crawl.
3. **Given** a search query that matches no images, **When** the marketer searches, **Then** the assistant says no matching images were found and suggests refining the search.

---

### User Story 2 — Admin Initializes the Image Index (Priority: P1)

Before image search can be used, the media library must be crawled and all existing images embedded. An admin (or any authenticated marketer) triggers this from the chat by asking the assistant to index images, optionally scoping it to a specific media library folder. The assistant crawls the folder, embeds each image, and reports progress and completion.

**Why this priority**: The index must be populated before any search is possible. This story enables the full feature for existing content.

**Independent Test**: With an empty image index and at least one image in the Sitecore media library, trigger the initialization crawl via the chat. Verify images are indexed and searchable afterward.

**Acceptance Scenarios**:

1. **Given** images exist in the Sitecore media library, **When** the marketer says "index all images in the media library," **Then** the assistant crawls the global media library, embeds each image, stores the vector with its item ID, and reports the total count of images indexed.
2. **Given** a specific folder path is provided, **When** the marketer says "index images in /sitecore/media library/Project/acme/brand-assets," **Then** only images within that folder are crawled and indexed.
3. **Given** an image cannot be processed (unsupported format, inaccessible), **When** the crawl encounters it, **Then** it is skipped with an error logged and the crawl continues — the final report notes how many images succeeded and how many were skipped.
4. **Given** a folder with hundreds of images, **When** the crawl runs, **Then** it processes them in batches without timing out and reports incremental progress.

---

### User Story 3 — New and Updated Images Are Automatically Indexed (Priority: P2)

When a marketer uploads a new image or updates an existing one in Sitecore, the image is automatically added to or updated in the search index without any manual action. This keeps the index current so newly uploaded images are immediately searchable.

**Why this priority**: Keeps the index fresh after initialization without requiring repeated manual crawls.

**Independent Test**: Upload a new image to Sitecore. Within 30 seconds, search for it in the chat by description. Verify it appears in results.

**Acceptance Scenarios**:

1. **Given** a Sitecore webhook is configured, **When** a new image is saved in Sitecore, **Then** the webhook triggers the backend to embed and index the new image within 30 seconds.
2. **Given** an existing indexed image is updated in Sitecore, **When** the webhook fires, **Then** the stored embedding is updated and the old vector is replaced — no duplicate entries are created.
3. **Given** a webhook fires for a non-image item (e.g., a Word document), **When** the backend receives it, **Then** the item is ignored gracefully with no error.
4. **Given** the webhook fires but the image is temporarily unretrievable, **When** the backend processes it, **Then** the failure is logged and the existing index entry (if any) is preserved.
5. **Given** an indexed image is deleted from Sitecore, **When** the deletion webhook fires, **Then** the embedding is removed from the index and the image no longer appears in search results.

---

### Edge Cases

- What happens when a previously indexed image is deleted from Sitecore? The system receives a deletion webhook event and removes the embedding from the index so stale results do not appear in search.
- What if the Cohere embedding service is temporarily unavailable? Webhook processing and crawl batches should retry with backoff; unprocessable items are logged and skipped.
- What if the same item is webhoooked multiple times in rapid succession (e.g., a bulk save)? Processing must be idempotent — the last successful embedding wins; no duplicate vectors stored per item ID.
- What if a crawl is triggered while another crawl is already running? The system should reject the second request and inform the marketer.
- Images with no alt text or description: embed the visual content only; search still works based on visual similarity.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept natural language image search queries from the chat and return ranked Sitecore media items scoped to the marketer's current environment, tenant, and site — results from other environments, tenants, or sites MUST NOT be returned.
- **FR-002**: Search results MUST include the Sitecore item ID, item name, and media library path for each match.
- **FR-003**: System MUST provide an initialization command (triggerable from the chat) that crawls the Sitecore media library and indexes all images in the global library or a specified folder path.
- **FR-004**: System MUST automatically index newly uploaded or updated Sitecore images within 30 seconds of a webhook event being received.
- **FR-005**: Image indexing MUST use multimodal embeddings that capture both the visual content of the image and any associated text metadata (alt text, item name, description field).
- **FR-006**: The initialization crawl MUST process images in batches and handle pagination so that large media libraries (hundreds or thousands of images) complete without timeout.
- **FR-007**: The initialization crawl MUST report: total images found, successfully indexed, and skipped due to errors.
- **FR-008**: Webhook processing MUST be idempotent — receiving the same event twice MUST update the stored embedding rather than create a duplicate entry.
- **FR-009**: Images that cannot be processed (unsupported format, inaccessible URL, embedding API error) MUST be skipped individually — they MUST NOT halt the crawl or webhook pipeline.
- **FR-010**: The webhook endpoint MUST verify the request origin using a shared secret before processing any payload.
- **FR-011**: System MUST prevent concurrent crawl runs for the same environment+tenant+site — a second crawl request for the same environment+tenant+site while one is already running MUST be rejected with a clear message. Crawls for different environment+tenant+site combinations MAY run concurrently.
- **FR-012**: Search MUST return results in ranked order by similarity score, with a configurable maximum result count (default: 5).
- **FR-013**: System MUST remove the stored embedding from the index when a Sitecore deletion webhook event is received for a previously indexed image. If the item was not indexed, the deletion event MUST be ignored gracefully.

### Key Entities

- **ImageEmbedding**: Sitecore item ID, environment, tenant ID, site ID (composite unique key: item ID + environment + tenant + site), media library path, item name, alt text, description, embedding vector, indexed timestamp, last updated timestamp.
- **IndexingJob**: ID, environment, tenant ID, site ID, scope (folder path or "global"), status (pending / running / complete / failed), total image count, indexed count, failed count, started at, completed at, triggered by (user ID or "webhook").

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Marketers receive image search results within 2 seconds of submitting a natural language query.
- **SC-002**: The initialization crawl indexes at least 50 images per minute under normal conditions.
- **SC-003**: Webhook-triggered images are searchable within 30 seconds of the event being received.
- **SC-004**: At least 95% of images in the crawled folder are successfully indexed during initialization (excluding genuinely inaccessible or unsupported-format items).
- **SC-005**: Marketers can describe what they want visually (e.g., "outdoor lifestyle photo," "product on white background") and receive relevant results without knowing the image's filename or alt text.
- **SC-006**: Re-indexing the same image (via webhook or repeated crawl) does not increase the total record count — updates are in-place.

---

## Assumptions

- pgvector is already enabled on the project's PostgreSQL instance (established in the constitution).
- Supported image formats for indexing: JPEG, PNG, GIF, WebP. Other formats are skipped with a log entry.
- The Cohere multimodal embedding model accepts an image URL for visual embedding and a separate text string for metadata embedding; both are combined into a single vector per image.
- The webhook is a Sitecore XM Cloud item:saved event scoped to the media library; Sitecore sends a JSON payload containing the item ID and item path.
- Webhook authenticity is verified using a shared secret passed in a request header (e.g., `X-Sitecore-Webhook-Secret`); the secret is stored as an environment variable.
- The initialization crawl is triggered manually from the chat by any authenticated marketer — it is not run automatically on app startup.
- A single PostgreSQL table stores embeddings for all environments, tenants, and sites. Each record is scoped by environment + tenant + site; search queries always filter by these three fields from the active iframe context. The composite key (item ID + environment + tenant + site) is the unique constraint — the same Sitecore item ID may appear in multiple environments (e.g., staging and production) as separate records.
- Search results are presented as a text list in the chat (item name + media path + item ID); inline image previews are out of scope for v1.
- Deletion webhook events (`item:deleted`) are handled in v1 — the embedding is removed from the index when an image is deleted from Sitecore.
- Missed webhook events due to backend unavailability are out of scope for v1. The system relies on Sitecore XM Cloud's built-in webhook retry behavior for transient failures. Marketers can run the initialization crawl at any time to reconcile the index. This is a known limitation of the v1 webhook approach.
