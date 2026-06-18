# Implementation Plan: Core Chat Application

**Branch**: `001-core-chat-app` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-core-chat-app/spec.md`

## Summary

Build a split-stack chat sidebar that embeds into the Sitecore XM Cloud Pages Editor via the Marketplace SDK. The **Python/FastAPI backend** handles all AI calls, streaming, instruction loading, database persistence, and MLflow tracing. The **Next.js frontend** is a thin UI layer that proxies all API calls to the backend over Railway's internal network. Users authenticate through Sitecore Auth0 (PKCE); the app operates in both iframe (production) and local (development) modes.

## Technical Context

**Backend**:
- Python 3.12
- FastAPI + Uvicorn (`uvicorn[standard]`)
- `langchain-core` + `langchain-openai` — provider-agnostic LLM interface (`BaseChatModel`)
- `langgraph` — graph-based workflow orchestration, tool invocation, streaming
- `sqlmodel` — unified data modeling: SQLModel(table=True) classes are both ORM models and Pydantic models
- `asyncpg` — async PostgreSQL driver (used by SQLModel/SQLAlchemy under the hood)
- `alembic` — database migrations (`target_metadata = SQLModel.metadata`)
- `mlflow>=2.21.0` — LangGraph/LangChain tracing via `mlflow.langchain.autolog()`
- `python-jose` — JWT validation for Auth0 tokens
- `cuid2` — CUID string primary keys

**Frontend**:
- Next.js 15 (App Router, Node.js runtime)
- React 19
- `@sitecore-marketplace-sdk/client` — client-side only (`'use client'`, `useEffect`)
- `@auth0/auth0-react` — Sitecore OAuth (Auth0 PKCE, `auth.sitecorecloud.io`)
- Tailwind CSS

**Storage**: PostgreSQL on Railway (native service); `DATABASE_URL` provided by Railway as `postgresql://...` — converted to `postgresql+asyncpg://` in Python.

**Tracing**: MLflow with `mlflow.langchain.autolog()`; local: `file:./mlruns`; production: self-hosted Railway MLflow stack.

**Target Platform**: Railway — separate services for Next.js, FastAPI, and PostgreSQL in the same Railway project. FastAPI has no public domain (internal only). Next.js is the public entry point.

**Performance Goals**:
- First streaming token ≤ 2 seconds p95
- FastAPI `/chat` route handler overhead ≤ 50ms (model latency dominates)

**Constraints**:
- No LLM SDK imported outside `backend/app/clients/llm.py`
- All instruction text in Markdown files under `backend/instructions/`, never hardcoded in Python
- No Sitecore writes without explicit user confirmation step
- `RUNTIME_CONTEXT=local` MUST NOT be set in any deployed Railway service
- FastAPI service must not have a public Railway domain — exposed only via Next.js proxy

**Scale/Scope**: Single-tenant per Sitecore Cloud installation; expected concurrent users <100 for v1.

## Constitution Check

*GATE: Must pass before implementation begins. Re-checked post-design below.*

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle VI) | ✅ PASS | All prompts in `backend/instructions/*.md`; loaded by `InstructionLoaderService` |
| No Sitecore write without user confirmation (Principle I) | ✅ PASS | No writes in core chat scope; confirmation pattern established for future features |
| New integrations use typed API client layer (Principle VII) | ✅ PASS | `backend/app/clients/` wraps LLM, Marketplace SDK path, and Auth0 JWT verification |
| New task behaviors in `instructions/tasks/*.md` (Principle VI) | ✅ PASS | Task overlay files are the only mechanism for task-specific behavior |
| No profile-switching logic (Principle IV) | ✅ PASS | Single persistent context; task instructions are additive overlays only |
| Guardrail coverage verified (Principle II) | ✅ PASS | Guardrail rules in `backend/instructions/guardrails/core.md`; included in every request |
| Memory writes use correct store (Principle V) | ✅ PASS | Only Conversation + Message in this feature; user knowledge store is feature #2 |
| LLM calls only through `clients/llm.py` (Technology Standards) | ✅ PASS | `langchain_openai.ChatOpenAI` imported only in `backend/app/clients/llm.py` |
| LangGraph graphs in `services/`, tools in `clients/` (Technology Standards) | ✅ PASS | `ChatGraph` defined in `services/`; `@tool` functions in `clients/` |
| MLflow tracing on all LLM/LangGraph call paths (Principle VII) | ✅ PASS | `mlflow.langchain.autolog()` called in FastAPI lifespan startup |

## Project Structure

### Documentation (this feature)

```text
specs/001-core-chat-app/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # Entity schemas and SQLAlchemy models
├── quickstart.md        # Validation guide
├── contracts/
│   └── api-contracts.md # HTTP API + SSE event + instruction loader contracts
└── tasks.md             # Created by /speckit-tasks
```

### Source Code

```text
backend/                                 # Python/FastAPI service
├── app/
│   ├── main.py                         # FastAPI app init, CORS, MLflow autolog, lifespan
│   ├── api/
│   │   ├── chat.py                     # POST /chat — SSE streaming endpoint
│   │   ├── conversations.py            # GET/DELETE /conversations[/{id}]
│   │   └── auth.py                     # GET /auth/status, /auth/token-verify
│   ├── services/
│   │   ├── chat_graph.py               # LangGraph StateGraph — model → tools → END
│   │   ├── chat_service.py             # FastAPI handler logic: instructions → graph → persist
│   │   ├── conversation_service.py     # Conversation + message CRUD
│   │   ├── instruction_loader.py       # Markdown file loader + overlay assembly
│   │   └── guardrails.py              # Topic classification + logging
│   ├── clients/
│   │   ├── llm.py                      # langchain_openai.ChatOpenAI factory (provider-agnostic)
│   │   ├── tools.py                    # LangChain @tool definitions (MCP, Sitecore, third-party)
│   │   └── auth_verifier.py           # Auth0 JWT verification via JWKS
│   └── resources/
│       ├── models.py                   # SQLModel table models (table=True) — DB + Pydantic in one
│       ├── schemas.py                  # Non-table SQLModel subclasses for API request/response shapes
│       └── database.py                 # Async engine + session factory
├── alembic/
│   ├── env.py                          # Async Alembic config
│   └── versions/
├── instructions/
│   ├── system/
│   │   └── base.md                     # Always-loaded base system prompt
│   ├── guardrails/
│   │   └── core.md                     # Topic guardrails (merged into base)
│   └── tasks/
│       ├── content-audit.md
│       ├── campaign-design.md
│       ├── seo-optimization.md
│       ├── component-population.md
│       └── site-management.md
├── tests/
│   ├── unit/
│   │   ├── test_instruction_loader.py
│   │   ├── test_guardrails.py
│   │   └── test_chat_service.py
│   └── conversation/
│       └── test_basic_chat.py          # Scripted conversation simulation
├── requirements.txt
├── alembic.ini
└── railway.toml                        # Start command: alembic upgrade head && uvicorn...

frontend/                                # Next.js service
├── app/
│   ├── api/
│   │   ├── chat/route.ts              # Proxy POST → FastAPI /chat (streams SSE)
│   │   ├── conversations/
│   │   │   ├── route.ts               # Proxy GET/DELETE → FastAPI
│   │   │   └── [id]/route.ts
│   │   └── auth/
│   │       ├── login/route.ts         # Initiate Auth0 PKCE flow
│   │       ├── callback/route.ts      # Auth0 redirect handler
│   │       ├── refresh/route.ts       # Token refresh proxy
│   │       └── status/route.ts        # Session status check
│   ├── layout.tsx
│   └── page.tsx                        # Sidebar shell
├── components/
│   ├── ChatPanel.tsx
│   ├── MessageList.tsx
│   ├── MessageBubble.tsx
│   ├── ChatInput.tsx
│   └── AuthGate.tsx
├── lib/
│   ├── hooks/
│   │   ├── useChat.ts                  # SSE consumer + client-side message state
│   │   └── useSitecoreContext.ts       # iframe vs local context provider
│   └── types.ts                        # Shared frontend types
├── package.json
└── railway.toml
```

## Key Implementation Decisions

### Streaming Architecture

`POST /api/chat` on the Next.js side proxies to FastAPI's `POST /chat`. FastAPI returns a `StreamingResponse` with `media_type="text/event-stream"`. The async generator:

1. Saves the user message to the database
2. Assembles the instruction set (system + guardrails + optional task overlay)
3. Invokes the LangGraph chat graph via `.astream_events()`
4. Yields `data: {"type": "conversationId", "id": "..."}` first (if new conversation)
5. Filters `on_chat_model_stream` events → yields `data: {"type": "delta", "text": "..."}` per token chunk
6. On graph completion: yields `data: {"type": "done"}`, saves complete assistant message to DB
7. Catches exceptions: yields `data: {"type": "error", "code": "..."}` before returning

Next.js proxy route: pipes the FastAPI `ReadableStream` body directly to the browser response.

React client: reads via `fetch` POST + `ReadableStream.getReader()`. Buffers partial chunks; processes complete `data: {...}\n\n` SSE lines.

Header `X-Accel-Buffering: no` on FastAPI response prevents Railway nginx from buffering.

### LangGraph Chat Graph

`backend/app/services/chat_graph.py` defines the `StateGraph` for the core chat loop:

```
[START] → model_node → <conditional> → tool_node → model_node (loop)
                      ↘ [END]
```

- `model_node`: calls the bound `ChatOpenAI` model with accumulated `MessagesState`
- Conditional edge: if the model emitted tool calls → route to `tool_node`; otherwise → END
- `tool_node`: `langgraph.prebuilt.ToolNode` executes bound LangChain tools and injects results back into state
- Graph is compiled once at module level and reused across requests

### LLM Client

`backend/app/clients/llm.py` is the only module that imports `langchain_openai`. It reads `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` (optional) from environment and returns a configured `ChatOpenAI` instance. Swapping providers (e.g., to `langchain_anthropic.ChatAnthropic`) requires only changing this file.

### MLflow Tracing

`mlflow.langchain.autolog()` called once in FastAPI's lifespan startup. This automatically traces all LangChain model calls, LangGraph node executions, and tool invocations — including the full prompt, response, token counts, latency, and graph traversal path. `chat_service.py` opens a custom span with `conversation_id`, `user_id`, `task_name`, and `guardrail_triggered` attributes.

### Instruction Loading

`backend/app/services/instruction_loader.py`:
- `BASE_DIR = Path(__file__).resolve().parent.parent.parent` (points to `backend/`)
- Always loads: `instructions/system/base.md` + `instructions/guardrails/core.md`
- Task overlay appended when `task_name` is in allowlist and file exists
- Task name validated against `^[a-z0-9_-]{1,64}$` before any path construction
- Resolved path verified inside `instructions/tasks/` via `.parents` check
- Module-level `_cache: dict[str, str]` — populated on first request, reused for process lifetime

### Auth Flow

Auth0 PKCE handled at the Next.js layer. `@auth0/auth0-react` manages the token lifecycle client-side. Auth tokens forwarded to FastAPI via `Authorization: Bearer <token>` header on every proxied request. FastAPI's `auth_verifier.py` validates the JWT against Auth0's JWKS endpoint. In local mode (`RUNTIME_CONTEXT=local`), Next.js injects a stub `user_id` header; FastAPI skips JWT verification.

### Runtime Context Switching

`RUNTIME_CONTEXT=local|iframe` env var read by Next.js frontend only. `iframe` mode: `@sitecore-marketplace-sdk/client` initialized in a `'use client'` component's `useEffect`; `pages.context` subscription provides `pageId`, `siteId`, `language`. `local` mode: stub values from `LOCAL_PAGE_ID`, `LOCAL_SITE_ID`, `LOCAL_LANGUAGE` env vars. Both modes produce the same `RuntimeContext` shape — downstream code is mode-agnostic.

### Railway Internal Networking

FastAPI service URL accessed by Next.js via `API_URL=http://api.railway.internal:8000` (NOT `NEXT_PUBLIC_API_URL` — server-side only). Next.js API route handlers proxy to this URL. FastAPI has no Railway public domain assigned.

## Complexity Tracking

> No constitution violations. No complexity justifications required.

## Post-Design Constitution Check

All gates re-verified after Phase 1 design — all pass. See Constitution Check table above.
