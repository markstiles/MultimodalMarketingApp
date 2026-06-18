# Research: Core Chat Application

**Feature**: `001-core-chat-app`
**Date**: 2026-06-17 (revised for Python/FastAPI/Railway stack)

---

## 1. FastAPI SSE Streaming

**Decision**: `StreamingResponse` with an async generator yielding SSE-formatted strings.

**Rationale**: FastAPI's `StreamingResponse` with `media_type="text/event-stream"` is the idiomatic pattern. OpenAI's `AsyncOpenAI` client supports `stream=True` and returns an async iterable of chunks. Errors are caught inside the generator and emitted as a final `error` event before the generator returns — the stream closes cleanly.

The `X-Accel-Buffering: no` response header must be set to prevent Railway's nginx proxy from buffering the stream.

**React client**: `EventSource` only supports GET. Chat uses POST, so the client reads the stream via `fetch()` + `ReadableStream.getReader()`. SSE events can split across network packets — the client must buffer partial lines and parse complete `data: ...\n\n` blocks before processing.

**Alternatives considered**: WebSockets — rejected for added complexity; the request/response pattern of chat fits SSE well and requires no persistent connection management.

---

## 2. LLM Client & Orchestration Framework

**Decision**: LangChain (`langchain-core`, `langchain-openai`) for the provider-agnostic LLM interface; LangGraph (`langgraph`) for all backend workflow orchestration.

**LLM client**: `langchain_openai.ChatOpenAI` constructed in `backend/app/clients/llm.py` using `LLM_API_KEY`, `LLM_MODEL`, and optional `LLM_BASE_URL`. Swapping to Anthropic, Azure OpenAI, or any other LangChain-supported provider requires only changing the import and env vars — no orchestration code changes. The `BaseChatModel` interface is the contract; all graphs program to that interface.

**Orchestration**: LangGraph `StateGraph` with `MessagesState` drives the chat loop. The graph handles: model call → conditional tool invocation (`ToolNode`) → guardrail routing → response streaming. This replaces ad-hoc service orchestration with an explicit, inspectable graph structure.

**Streaming**: LangGraph's `.astream_events()` emits token-level events. The FastAPI async generator filters for `on_chat_model_stream` events and maps them to the SSE `delta` format.

**Tools**: MCP server capabilities and third-party integrations are wrapped as LangChain `@tool` functions in the `clients/` layer and bound to the model node via `.bind_tools()`. The `ToolNode` handles invocation and result injection automatically.

**Alternatives considered**:
- Raw `AsyncOpenAI` SDK — rejected; no built-in tool invocation, no graph state, streaming requires manual event mapping with no inspection capability.
- LiteLLM — broad provider support but adds heavyweight dependency on top of what LangChain already provides.
- LangChain LCEL chains without LangGraph — chains are linear; LangGraph is required for conditional routing (guardrails, intent classification) and cycles (tool → model loops).

---

## 3. MLflow Tracing

**Decision**: `mlflow.langchain.autolog()` for automatic tracing of all LangChain and LangGraph calls; manual `mlflow.start_span()` for custom attributes (conversation ID, user ID, task name, guardrail trigger). MLflow ≥ 2.21.0 required; traces capture full graph traversal, tool calls, and token counts automatically.

**Local tracking**: `mlflow.set_tracking_uri("file:./mlruns")` — zero config, writes to `./mlruns`.

**Production tracking**: Self-hosted Railway MLflow stack (Caddy + MLflow server + PostgreSQL backend + MinIO artifacts). Set `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` env vars in the backend service.

**Experiment structure**: experiment name `chatbot-conversation-quality`; run naming `{task_name}-{conv_id[:8]}-{YYYYMMDD}`; logged metrics: `token_count`, `latency_ms`, `guardrail_score`; params: `task_name`, `model`, `guardrail_triggered`.

**Alternatives considered**: LangSmith — vendor lock-in; Weights & Biases — heavier ML focus than needed. MLflow is open-source and already in use for testing.

---

## 4. Database & ORM

**Decision**: SQLAlchemy async (`sqlalchemy[asyncio]`, `asyncpg`) with Alembic migrations. Railway PostgreSQL native service.

**Connection string**: Railway provides `DATABASE_URL=postgresql://...` — must replace scheme with `postgresql+asyncpg://` for asyncpg driver.

**Connection pool**: `pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600` — Railway runs persistent containers (not serverless), so `QueuePool` is correct. `NullPool` is for Alembic migrations only.

**Migrations**: Railway start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Migrations apply before traffic is served.

**ID generation**: `cuid2` Python package for CUID-format string primary keys (matches prior data model design).

**Alternatives considered**: Prisma Python client — immature; `databases` library — less full-featured than SQLAlchemy.

---

## 5. Instruction File Loader

**Decision**: `Path(__file__).resolve().parent` anchored path resolution; module-level `dict` cache; regex allowlist + `pathlib` resolve-and-contain security.

**Path resolution**: `__file__` is reliable in Railway Nixpacks deployments (full project tree copied to `/app`). `os.getcwd()` is fragile and varies by launch method.

**Caching**: Module-level `_cache: dict[str, str]` — reliable for Railway's persistent single-worker container. Files are read from disk once per worker process lifetime.

**Security**: Task name validated against `^[a-z0-9_-]{1,64}$` regex before any path construction. Resolved path verified to be inside `instructions/tasks/` via `pathlib` `.parents` check.

**Vercel note**: N/A — hosting is Railway. No `outputFileTracingIncludes` config needed.

**Alternatives considered**: Redis cache for instructions — overkill for static files read once per process.

---

## 6. Frontend Architecture

**Decision**: Next.js 15 (App Router, Node.js runtime) as a thin UI layer. All API calls proxied through Next.js Route Handlers to the FastAPI backend on the Railway internal network (`http://api.railway.internal:8000`). The FastAPI backend has no public Railway domain.

**Rationale**: Proxy pattern keeps the FastAPI URL off the internet, avoids CORS configuration, and allows Next.js to attach session cookies server-side before forwarding. Railway private networking (`*.railway.internal`) connects services at zero cost with no public exposure.

**Sitecore SDK**: `@sitecore-marketplace-sdk/client` is client-side only (`'use client'` components, `useEffect` init). No server-side usage possible or needed.

**Streaming**: React consumes FastAPI SSE via `fetch` POST + `ReadableStream.getReader()`. Partial SSE chunks are buffered in a string accumulator; `setState` is called per complete event to avoid render storms.

**Alternatives considered**: Direct browser → FastAPI calls — rejected because it requires FastAPI to have a public domain and permissive CORS headers.

---

## 7. Sitecore OAuth

**Decision**: Auth0 Authorization Code + PKCE (`auth.sitecorecloud.io`). `@auth0/auth0-react` client-side in Next.js for token management. Auth state passed to Next.js proxy routes via `Authorization` header; forwarded to FastAPI.

**FastAPI auth**: FastAPI validates the Bearer token on protected routes using Auth0's JWKS endpoint. No Auth0 SDK in Python — use `python-jose` or `authlib` for JWT verification.

**Rationale**: Auth happens at the browser/Next.js layer; FastAPI trusts validated tokens forwarded by the proxy. This keeps the Auth0 client secret in Next.js server-side environment only.

**Local mode**: Auth skipped entirely when `RUNTIME_CONTEXT=local`. FastAPI accepts a stub `user_id` from the proxy.
