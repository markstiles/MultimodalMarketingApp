# Research: Brand Kit Building

**Feature**: 006-brand-kit-building | **Date**: 2026-06-18

## Decision Log

### 1. Brand Service Authentication

**Decision**: Reuse the existing Sitecore OAuth2 client credentials flow from `mcp_client.py`, extracted into a shared `brand_auth.py` helper module rather than duplicating it in each new client.

**Rationale**: The brand service APIs (Document Management, Pipeline, Brand Management) all use the same `https://auth.sitecorecloud.io/oauth/token` endpoint with `audience=https://api.sitecorecloud.io`. Centralizing the token cache in one helper avoids three independent caches with different expiry windows that could produce redundant token requests.

**Alternatives considered**:
- Duplicate token logic in each client — rejected; violates DRY and creates drift risk
- Use the user's session token (passed from the frontend) — rejected; brand service operations are server-side automations, not user-session operations; client credentials are the correct grant type

**Env vars**: `SITECORE_CLIENT_ID_AUTOMATION`, `SITECORE_CLIENT_SECRET_AUTOMATION` (already in `.env.example` from MCP client work)

---

### 2. Pipeline Notification Strategy

**Decision**: Lazy polling — pipeline run IDs are persisted in `brand_pipeline_runs` at trigger time; a `check_pipeline_notifications` graph node queries the DB for pending runs belonging to the current conversation and calls the brand service status API for each. Status updates and notifications are injected as system messages before the model node runs.

**Rationale**: The constitution requires no blocking of the conversation during pipeline execution. A background scheduler (APScheduler, Celery) would handle proactive notifications but adds significant operational overhead (new Railway service, broker dependency) for v1. The lazy approach satisfies SC-003 ("notifications appear without the marketer asking") as long as the marketer sends any message — the notification appears in that response. For a 10–20 min pipeline, the marketer will typically interact again before completion.

**Trade-off**: If the marketer never returns to the conversation, the notification is never delivered. This is an acceptable v1 limitation — the brand kit is still updated; only the in-conversation notification is delayed.

**Alternatives considered**:
- Background APScheduler task polling every 2 minutes — rejected for v1; adds Railway service + broker complexity
- WebSocket push from backend → frontend — rejected; not in the current architecture and adds frontend state management complexity
- Webhook registration with the brand service — rejected; brand service webhooks are not confirmed as available in the current API documentation

**Implementation note**: The notification check node runs before the model node. If no pending runs exist (the common case), it returns immediately with no overhead. The DB query uses an index on `(conversation_id, status)`.

---

### 3. Org ID Resolution

**Decision**: `BRAND_SERVICE_ORG_ID` environment variable, set per Railway deployment. Not derived from the user's auth token.

**Rationale**: The Sitecore organization is a deployment-level concept (one org per installation of the marketing app). Deriving it from the JWT would require parsing the token on every request and assumes the org ID is always present in standard claims. An env var is simpler, more explicit, and consistent with how Railway services are configured.

**Alternatives considered**:
- Parse org ID from Auth0 JWT claims — rejected; org ID is not a standard OIDC claim; would require custom claim mapping in Auth0
- Derive from existing `sitecore_id` on the User model — rejected; the sitecore_id is a user-level identifier, not an org-level one

---

### 4. Non-AI Editable Toggle API

**Decision**: Use `PATCH /api/brands/v1/organizations/{org}/brandkits/{id}/sections/{sectionId}/subsections/{subsectionId}` with a body setting the `isAiEditable` field to `false`. This is inferred from the Brand Management API OpenAPI spec pattern (update subsection properties).

**Rationale**: The OpenAPI spec for the Brand Management API includes a PATCH endpoint for subsection updates. The `isAiEditable` field name is consistent with how Sitecore documents the Non-AI Editable flag in their UI documentation.

**Risk**: If the PATCH endpoint or field name differs from this assumption, the tool will fail with a 404 or 422. The implementation should handle these errors gracefully and surface a clear message to the marketer.

**Alternatives considered**:
- Expose only list subsections, not toggle — rejected; FR-017 requires the toggle capability
- Build the toggle as a separate UI action (not chat) — rejected; the spec requires all three workflows to be available through the assistant

---

### 5. Document Upload Encoding

**Decision**: Documents are uploaded to the brand document service as multipart/form-data. The `@tool` function for document upload receives the file as base64-encoded content (since LangChain tool parameters are JSON-serializable) and decodes it before sending to the brand service.

**Rationale**: LangChain `@tool` function parameters must be JSON-serializable for the LLM to produce valid tool calls. Binary file content must be base64-encoded in the tool call. The tool function decodes back to bytes before the multipart upload.

**Note**: The actual file bytes reach the tool from the chat service, which receives the upload from the frontend via an existing or new multipart route. The LLM does not produce file bytes — it only names the file from the conversation context.

---

### 6. Duplicate Pipeline Guard

**Decision**: Before triggering a pipeline, query `brand_pipeline_runs` for any run with matching `(brand_kit_id, pipeline_type, status='running')`. If found, return the existing run details rather than triggering a new one (FR-011). Cross-type simultaneous runs (ingestion + enrichment at the same time) are allowed (Clarification Q1).

**Rationale**: The spec explicitly allows ingestion and enrichment to run simultaneously but prohibits same-type duplicates. A simple DB query on the indexed `(brand_kit_id, pipeline_type, status)` tuple handles the guard without calling the brand service unnecessarily.

---

### 7. Document Library Truncation

**Decision**: When listing the brand kit document library before upload, return up to 5 document names. If the total count exceeds 5, include the count of remaining documents in the response (FR-002, Clarification Q2). The tool returns the full list from the brand service; truncation to 5+remainder is applied in the instruction overlay's framing guidance, not in the tool itself.

**Rationale**: Keeping truncation in the instruction overlay (not the tool) means the tool returns complete data for any other use case, while the conversational presentation follows the display rule. This avoids coupling a UX constraint into a reusable data-fetching tool.
