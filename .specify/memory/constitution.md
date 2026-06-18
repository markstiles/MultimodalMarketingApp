<!--
SYNC IMPACT REPORT
==================
Version change: 4.0.0 → 4.1.0 (MINOR — SQLModel adopted as unified data modeling layer)
Modified sections (4.0.0):
  - Technology Standards: AI Provider — replaced raw OpenAI SDK with LangChain ChatModels
    (langchain-core, langchain-openai). Provider-agnostic contract preserved via LLM_* env vars.
  - Technology Standards: NEW "Orchestration" section — LangGraph (langgraph) is now the
    required framework for all multi-step workflows, tool invocation, conditional routing,
    and conversation state management in the backend.
  - Technology Standards: MCP Integration — tools MUST be defined as LangChain @tool functions
    in the clients/ layer and bound to graph model nodes via .bind_tools().
  - Technology Standards: Tracing — mlflow.openai.autolog() replaced by mlflow.langchain.autolog()
    to trace full graph traversal, tool calls, and LangChain model calls.
  - Development Workflow: Constitution Check — added gate for LangGraph graph definitions.
Modified sections (4.1.0):
  - Technology Standards: Database — SQLModel replaces raw SQLAlchemy ORM as the unified
    data modeling layer. SQLModel(table=True) classes serve as both database tables and
    Pydantic models. Separate API request/response schemas inherit from non-table SQLModel
    base classes. sqlmodel package replaces sqlalchemy[asyncio] as the direct dependency
    (SQLAlchemy remains an indirect dependency via SQLModel).
  - Development Workflow: Constitution Check — added gate for SQLModel modeling convention.
Templates requiring updates:
  - specs/001-core-chat-app/plan.md ✅ — LangChain/LangGraph and SQLModel updated
  - specs/001-core-chat-app/research.md ✅ — LLM Client and Streaming updated
  - specs/001-core-chat-app/data-model.md ⚠️ PENDING — SQLAlchemy models → SQLModel models
Deferred TODOs:
  - TODO(SCORING_MODEL): scoring schema not yet defined
  - TODO(VISUAL_DOCS_TOOL): diagramming toolchain not yet chosen — Mermaid is default candidate
-->

# Multimodal Marketing App Constitution

## Core Principles

### I. Sitecore-Embedded, Marketer-First

The application is a sidebar assistant embedded in the Sitecore AI page editor via iframe.
Its primary audience is non-technical marketers who need guidance, not raw tool output.
The assistant MUST communicate in plain, encouraging language, walk users through multi-step
tasks, and proactively suggest next actions rather than waiting to be asked.

Every feature MUST be designed around Sitecore XM Cloud as the authoritative content system.
AI-generated or AI-modified content MUST be confirmed by the user before any write operation
is submitted to Sitecore — no automated writes without explicit user approval.

### II. Guardrails Are Non-Negotiable

The assistant MUST stay on-topic. Permitted topics:

- Marketing strategy, copywriting, SEO, campaigns, analytics
- Sitecore XM Cloud usage, page editing, component management, media
- Competing or complementary products (e.g., Contentful, HubSpot, GA4) in a marketing context
- General web content best practices

The assistant MUST refuse and redirect — politely but firmly — any conversation about:
politics, personal advice, medical diagnoses, mental health, legal advice, gaming, gambling,
or any topic not materially connected to marketing or digital product management.
Refusals MUST NOT be preachy; one sentence redirect is sufficient.

### III. Multimodal Input

The system MUST support: text chat, file uploads (Word, PDF, plain text), and Sitecore media
library assets (images with alt-text, descriptions). Audio and structured data imports
(spreadsheets, CSVs) are planned future modalities and MUST NOT be blocked architecturally.
All input types MUST respect the user-confirmation gate before any Sitecore write.

### IV. Instruction Governance & Task Overlays

All system prompts, assistant instructions, and guardrail rules MUST live in Markdown files
under the `instructions/` directory tree. The application MUST load them at runtime by
convention (e.g., `instructions/tasks/{name}.md`, `instructions/guardrails/core.md`).
No prompt strings hardcoded in application code. This separation allows product owners and
content designers to tune behavior without touching source files.

The assistant MUST be a single, persistent conversational context — there is no profile
switching. Instead, the assistant dynamically augments its base instructions with
task-specific instruction files when the user's intent calls for it (e.g., an SEO audit,
a campaign brief, component population). These instruction files are additive overlays,
not replacements, so the assistant's full conversational context and memory are preserved.

Task instruction files are loaded by convention from `instructions/tasks/` (see
`instructions/` directory layout in Technology Standards). The set of active task
instructions MUST be logged so classification decisions can be reviewed and improved,
but they MUST NOT change the assistant's identity or reset the conversation.

### V. Conversation Memory & Retrieval

All conversation history MUST be persisted per authenticated user and per site in PostgreSQL.
Retrieval MUST support both keyword search and semantic (embedding-based) search so users
and the system can find prior conversations by topic or content.

A separate **user knowledge store** MUST exist for per-user personalization data: brand voice
preferences, frequently used templates, stored campaign briefs, and other marketing context
that the assistant can recall to give more relevant responses. This store MUST also support
keyword and semantic retrieval.

Conversations MUST survive page navigation and OAuth token refresh. Users MUST be able to
resume, switch between, and delete stored conversations.

### VI. Layered Service Architecture

Code MUST be organized into four layers:

1. **Route handlers** — API endpoints; thin, no business logic
2. **Services** — business logic, orchestration, intent classification
3. **API clients** — connection wrappers for Sitecore, the LLM provider, MCP servers, and
   third-party integrations (Google Analytics, search APIs)
4. **Resources** — data models, database schemas, embedding utilities

Cross-layer calls that skip a layer MUST be justified in the feature plan's Complexity
Tracking table. Shared types live at the resource layer; never duplicated upward.

### VII. Conversation Quality & Testing

**Tracing**: All LLM calls MUST be traced via MLflow. Traces MUST capture the full prompt
(system + user turns), model used, token counts, latency, and any guardrail triggers.

**Scoring**: Every completed conversation MUST be scoreable. A scoring schema (to be defined)
MUST capture metrics such as task completion, guardrail triggers, intent classification
accuracy, and user-confirmed vs. rejected suggestions. Scores MUST be queryable for trend
analysis and model/prompt improvement.

**Unit tests**: Each assistant skill or tool integration MUST have a unit test that exercises
it in isolation with a mock context.

**Conversation simulation tests**: A test harness MUST support scripted conversation
replays — a sequence of user turns with expected assistant behaviors — so that changes to
instructions, tools, or models can be evaluated against a regression suite without a live
Sitecore environment.

## Technology Standards

**Frontend**: React (via Next.js App Router), Tailwind CSS. The frontend is a thin UI layer —
no business logic. All AI, data, and integration logic lives in the Python backend.

**Backend**: Python/FastAPI. All API routes, services, LLM calls, database access, MCP
connections, and instruction loading are implemented in Python. FastAPI is chosen for its
async-native design (required for streaming), automatic OpenAPI docs, and strong typing
via Pydantic models.

**AI Provider**: The LLM client uses LangChain (`langchain-core`, `langchain-openai`) which
provides a provider-agnostic `BaseChatModel` interface. `langchain_openai.ChatOpenAI` is
the concrete implementation for OpenAI initially; switching providers requires only changing
the import in `clients/llm.py` and updating env vars — no application logic changes.
Environment variables:
- `LLM_API_KEY` — provider API key (never vendor-specific name in application code)
- `LLM_MODEL` — model identifier (e.g., `gpt-4o`, `claude-sonnet-4-6`)
- `LLM_BASE_URL` — optional; override base URL for OpenAI-compatible providers

`langchain_openai` (or any LangChain provider package) MUST be imported only inside
`backend/app/clients/llm.py`. No other module touches the provider package directly.

**Orchestration**: LangGraph (`langgraph`) is the required framework for all backend
conversational workflow logic. Multi-step task execution, tool invocation, conditional
routing (guardrail detection, intent classification, task overlay selection), and
conversation state management MUST be implemented as LangGraph `StateGraph` definitions.

- Graphs are defined in the `services/` layer
- The standard state schema is `langgraph.graph.MessagesState` or a typed subclass
- The streaming path for the chat endpoint uses LangGraph's `.astream_events()`, with
  events mapped to the SSE format defined in the API contracts
- Tools MUST be defined as LangChain `@tool`-decorated functions in the `clients/` layer
  and bound to the graph's model node via `.bind_tools()` — tools are never called
  directly from route handlers or services; only the LangGraph `ToolNode` invokes them

**Tracing & Testing**: MLflow with `mlflow.langchain.autolog()` for automatic tracing of
all LangChain and LangGraph calls. Traces capture full prompts, responses, token counts,
latency, tool invocations, and graph node traversal. MLflow is the standard for all AI
observability in this project.

**Database**: PostgreSQL, hosted on Railway. **SQLModel** is the unified data modeling layer —
`SQLModel(table=True)` classes define database tables and are simultaneously valid Pydantic
models, eliminating separate ORM and schema files. API request and response shapes that
differ from the table model MUST be defined as non-table SQLModel subclasses (inheriting
from a shared `Base` class), keeping schema definitions DRY. Migrations MUST be managed
via Alembic (`target_metadata = SQLModel.metadata`) and be idempotent. Semantic search
via `pgvector` extension. Railway PostgreSQL is a first-class Railway service provisioned
in the same project as the app.

**MCP Integration**: Two self-hosted MCP servers:
- **Sitecore Docs MCP** — read-only documentation lookup; no authentication required
- **Marketer/Agent API MCP** — Sitecore content operations; requires authentication

MCP server capabilities are exposed to the LangGraph agent as LangChain `@tool` functions
defined in the `clients/` layer. All Sitecore read operations SHOULD prefer MCP tools where
a tool exists. Third-party integrations (Google Analytics, external search APIs) MUST
likewise be wrapped as typed LangChain tools — never called inline from route handlers
or services.

**Authentication**: Sitecore OAuth 2.0 (Auth0, domain: `auth.sitecorecloud.io`). Token
refresh MUST be transparent; after login the user MUST be returned to their in-progress
conversation.

**Hosting**: Railway for all services — Python backend, Next.js frontend, and PostgreSQL.
Hosting choices MUST minimize operational overhead and fixed cost. Railway supports
containerized deployments for both the Python backend and the Next.js frontend, and
provides a native PostgreSQL service.

**Local vs. iframe context**: The app MUST run locally without an active Sitecore iframe
context, falling back to mock/stub values for iframe-injected data (page ID, site context,
OAuth token). A `RUNTIME_CONTEXT=local|iframe` environment variable MUST gate this behavior.
Integration testing against real Sitecore MUST occur in the iframe environment.

**Visual documentation**: Workspace architecture (service topology, data flows, integration
points) and chat dialogue architecture (conversation state machines, intent routing) MUST be
documented as diagrams committed to the repository.
TODO(VISUAL_DOCS_TOOL): toolchain not yet chosen — Mermaid is the default candidate.

**Instructions directory**:

```
instructions/
├── tasks/
│   ├── content-audit.md
│   ├── campaign-design.md
│   ├── seo-optimization.md
│   ├── component-population.md
│   └── site-management.md
├── guardrails/
│   └── core.md
└── system/
    └── base.md
```

`system/base.md` is always loaded. `guardrails/core.md` is always merged into the base prompt.
Files under `tasks/` are loaded additively on detected intent — overlays, never replacements.
File paths are the contract; renaming requires a code change in the instruction loader.

## Development Workflow

**Feature branches**: `###-feature-name` off `main`. PRs MUST include a Constitution Check.

**Agent context**: The single agent context file is `CLAUDE.md` at the repository root.
The `.claude/` directory is reserved for agent skills and scripts — it MUST NOT contain a
duplicate `CLAUDE.md`.

**Constitution Check gates** (verify before merging any PR):
- [ ] No prompt strings hardcoded in source code (Principle IV)
- [ ] No write to Sitecore without user confirmation step (Principle I)
- [ ] New integrations use typed API client layer, not inline calls (Principle VI)
- [ ] New task behaviors live in `instructions/tasks/*.md`, not in source code (Principle IV)
- [ ] No profile-switching logic introduced; task instructions are additive overlays (Principle IV)
- [ ] Guardrail coverage verified for any new task instruction or topic expansion (Principle II)
- [ ] Memory writes use the correct store (conversation vs. user knowledge) (Principle V)
- [ ] Database models use SQLModel(table=True); API schemas inherit from non-table SQLModel base classes — no raw SQLAlchemy declarative models (Technology Standards)
- [ ] LLM calls go through the provider-agnostic LLM client only — no LangChain provider package imported outside `clients/llm.py` (Technology Standards)
- [ ] New multi-step workflows and tool invocations are implemented as LangGraph `StateGraph` definitions in `services/`, not as ad-hoc service orchestration (Technology Standards)
- [ ] New tools are defined as LangChain `@tool` functions in `clients/` and bound to the graph via `.bind_tools()` — not called directly from services or route handlers (Technology Standards)
- [ ] MLflow tracing present on all new LLM/LangGraph call paths via `mlflow.langchain.autolog()` (Principle VII)

**Streaming**: Chat responses MUST stream to the UI. Non-streaming is not acceptable for
the primary chat path.

**Environment variables**: All secrets declared in `.env.example`. No hardcoded credentials.
Use generic names (`LLM_API_KEY`, `LLM_MODEL`) not vendor-specific ones.

**Code style**: Python backend follows PEP 8. Frontend React components are functional only.

## Governance

This constitution supersedes all other development practices for this project.

Amendments require a PR updating this file with a version bump:

- **MAJOR**: Backward-incompatible principle removal or redefinition, or foundational tech stack change
- **MINOR**: New principle or section added; structural reorganization; material expansion of existing guidance
- **PATCH**: Clarification, wording, or non-semantic refinement

All PRs and code reviews MUST verify the Constitution Check gates above. Complexity
violations (skipping an architectural layer, hardcoding a prompt, etc.) MUST be documented
in the feature plan's Complexity Tracking table with a justification.

**Version**: 4.1.0 | **Ratified**: 2026-06-17 | **Last Amended**: 2026-06-17
