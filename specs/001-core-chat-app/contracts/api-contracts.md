# API Contracts: Core Chat Application

**Feature**: `001-core-chat-app`
**Date**: 2026-06-17 (revised for Python/FastAPI backend)

All endpoints listed here are **Next.js proxy routes** (browser-facing). They forward to the corresponding FastAPI internal endpoints. The FastAPI service is not publicly accessible.

Base URL (public, Next.js): `/api`
Internal FastAPI base: `http://api.railway.internal:8000` (Railway internal only)

---

## Authentication

All endpoints except `/api/auth/*` require a valid session. The Next.js proxy reads the session cookie, validates it, and forwards `Authorization: Bearer <access_token>` to FastAPI. FastAPI validates the JWT against Auth0's JWKS endpoint.

In `RUNTIME_CONTEXT=local`, auth checks are bypassed. Next.js forwards `X-Local-User-Id: <LOCAL_USER_ID>` and FastAPI skips JWT verification.

---

## Endpoints

### POST /api/chat

Sends a user message and streams the assistant response via SSE.

**Request body**:
```json
{
  "message": "string (required, max 32000 chars)",
  "conversationId": "string | null",
  "context": {
    "pageId": "string",
    "siteId": "string",
    "language": "string"
  }
}
```

**Response**: `Content-Type: text/event-stream`

Headers set by FastAPI:
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no`

**SSE event stream** (in order):

```
data: {"type": "conversationId", "id": "<cuid>"}

data: {"type": "delta", "text": "Hello"}

data: {"type": "delta", "text": ", how"}

data: {"type": "done"}
```

| Event type | When emitted | Fields |
|------------|--------------|--------|
| `conversationId` | First event; always sent | `id: string` — CUID of the conversation (new or existing) |
| `delta` | Once per LLM token chunk | `text: string` — partial response text |
| `done` | Stream complete; assistant message saved to DB | — |
| `error` | On any error before or during stream | `code: string` — see error codes below |

**Error codes**:

| Code | Meaning |
|------|---------|
| `rate_limit` | LLM provider rate limit hit |
| `invalid_request` | Malformed request (also returned as HTTP 422 before stream starts) |
| `unauthorized` | Session invalid or expired |
| `upstream_error` | LLM provider returned an error |
| `internal_error` | Unexpected server error |

**HTTP errors** (before stream begins):
- `400` — message empty or whitespace-only
- `401` — no valid session
- `422` — Pydantic validation failure

---

### GET /api/conversations

Lists non-deleted conversations for the authenticated user and current site.

**Query params**:
- `siteId` (required) — filter by Sitecore site
- `limit` (optional, default 20, max 100)
- `offset` (optional, default 0)

**Response** `200`:
```json
{
  "conversations": [
    {
      "id": "string",
      "title": "string | null",
      "siteId": "string",
      "createdAt": "ISO 8601",
      "updatedAt": "ISO 8601"
    }
  ],
  "total": 0
}
```

---

### GET /api/conversations/{id}

Returns a single conversation with its full message history.

**Path params**: `id` — conversation CUID

**Response** `200`:
```json
{
  "id": "string",
  "title": "string | null",
  "siteId": "string",
  "createdAt": "ISO 8601",
  "updatedAt": "ISO 8601",
  "messages": [
    {
      "id": "string",
      "role": "user | assistant",
      "content": "string",
      "createdAt": "ISO 8601"
    }
  ]
}
```

**Error responses**: `401` unauthorized; `404` conversation not found or not owned by user

---

### DELETE /api/conversations/{id}

Soft-deletes a conversation (sets `deleted_at`). The conversation is excluded from list results but retained in the database.

**Response**: `204 No Content`

**Error responses**: `401`; `404`

---

### GET /api/auth/status

Returns the current session status.

**Response** `200`:
```json
{
  "authenticated": true,
  "user": {
    "id": "string",
    "email": "string"
  },
  "expiresAt": "ISO 8601 | null"
}
```

When unauthenticated: `{ "authenticated": false, "user": null, "expiresAt": null }`

---

### GET /api/auth/login

Initiates the Auth0 PKCE authorization flow. Redirects to `auth.sitecorecloud.io/authorize`.

**Query params**:
- `returnTo` (optional) — URL to redirect to after login
- `conversationId` (optional) — preserved through OAuth round-trip via `state` param

**Response**: `302 Redirect` → Auth0 authorize URL

---

### GET /api/auth/callback

Auth0 redirect handler. Exchanges the authorization code for tokens, upserts `User` and `UserSession`, then redirects to `returnTo` with `conversationId` preserved.

**Response**: `302 Redirect` → `returnTo` (or `/` if not set)

---

### POST /api/auth/refresh

Exchanges the stored refresh token for a new access token. Called transparently by the frontend when `expiresAt` is within 5 minutes.

**Response** `200`:
```json
{
  "expiresAt": "ISO 8601"
}
```

**Error responses**: `401` — refresh token invalid or expired (user must re-login)

---

## Instruction Loader Contract

The instruction loader is an internal service (`backend/app/services/instruction_loader.py`). Not exposed as an HTTP endpoint.

**Function signature**:
```python
def load_instructions(task_name: str | None = None) -> str:
    """
    Returns assembled system prompt string.
    Always includes: instructions/system/base.md + instructions/guardrails/core.md
    Appends: instructions/tasks/{task_name}.md if task_name is in ALLOWED_TASKS and file exists.
    Raises: never — missing task file returns base+guardrails only (logged as warning).
    """
```

**ALLOWED_TASKS** (allowlist, enforced before path construction):
```python
ALLOWED_TASKS = {
    "content-audit",
    "campaign-design",
    "seo-optimization",
    "component-population",
    "site-management",
}
```

**Security**: `task_name` validated against `^[a-z0-9_-]{1,64}$` regex. Resolved path verified to be inside `instructions/tasks/` via `pathlib` `.parents` check before any file I/O.

**Caching**: Module-level `_cache: dict[str, str]` populated on first read per key. Cache is per-process; Railway restarts clear it.

---

## SSE Consumption Pattern (React Client)

```typescript
// frontend/lib/hooks/useChat.ts (pattern reference)

const response = await fetch("/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, conversationId, context }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const lines = buffer.split("\n");
  buffer = lines.pop()!; // keep incomplete last line

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const event = JSON.parse(line.slice(6));

    if (event.type === "conversationId") setConversationId(event.id);
    if (event.type === "delta") setStreaming(prev => prev + event.text);
    if (event.type === "done") { finalizeMessage(); setStreaming(""); }
    if (event.type === "error") handleError(event.code);
  }
}
```

**Key rules**:
- `setStreaming` accumulates delta text; displayed as in-progress bubble
- `finalizeMessage()` moves `streaming` text to `messages[]` state and clears `streaming`
- `messages[]` state is not updated until `done` is received — no render churn during stream
- On `error` event: `messages[]` preserved; user sees error banner with retry button
