<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 2.0.0 (MAJOR — Principle IV redefined; switching profiles removed)
Modified principles:
  - IV. Specialized Assistant Profiles → IV. Task-Scoped Instructions (breaking redefinition)
    Reason: switching profiles mid-conversation proved too rigid and disruptive; the assistant
    is now a single persistent context that pulls targeted instruction sets per task.
Added sections: none
Removed sections: none
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ — Constitution Check gates updated (profile → task-instruction)
  - .specify/templates/spec-template.md ✅ — no structural changes needed
  - .specify/templates/tasks-template.md ✅ — profile-creation task type removed; instruction-file task type added
Deferred TODOs:
  - TODO(SCORING_MODEL): scoring schema for conversation quality not yet defined — tracked in feature backlog
  - TODO(VISUAL_DOCS_TOOL): diagramming toolchain (Mermaid, draw.io, etc.) not yet chosen
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

### IV. Task-Scoped Instructions, Not Switching Profiles

The assistant MUST be a single, persistent conversational context — there is no profile
switching. Instead, the assistant dynamically augments its base instructions with
task-specific instruction files when the user's intent calls for it (e.g., an SEO audit,
a campaign brief, component population). These instruction files are additive overlays,
not replacements, so the assistant's full conversational context and memory are preserved.

Task instruction files are loaded by convention from `instructions/tasks/` (see Principle VI).
The set of active task instructions MUST be logged so classification decisions can be
reviewed and improved, but they MUST NOT change the assistant's identity or reset the
conversation.

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

### VI. Prompt & Instruction Governance

All system prompts, assistant instructions, profile definitions, and guardrail rules MUST
live in Markdown files under a designated `instructions/` directory tree. The application
MUST load them at runtime by convention (e.g., `instructions/profiles/{profile-name}.md`,
`instructions/guardrails/core.md`). No prompt strings hardcoded in application code.

This separation allows product owners and content designers to tune behavior without
touching TypeScript source files.

### VII. Layered Service Architecture

Code MUST be organized into four layers:

1. **Route handlers** — Next.js API routes; thin, no business logic
2. **Services** — business logic, orchestration, profile selection
3. **API clients** — connection wrappers for Sitecore, Anthropic, MCP servers, and
   third-party integrations (Google Analytics, search APIs)
4. **Resources** — data models, Prisma schemas, embedding utilities

Cross-layer calls that skip a layer MUST be justified in the feature plan's Complexity
Tracking table. Shared types live at the resource layer; never duplicated upward.

### VIII. Conversation Quality & Testing

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

**Runtime**: Next.js 15 (App Router), TypeScript strict mode, React, Tailwind CSS.

**AI Provider**: Anthropic Claude (claude-sonnet-4-6 or newer) via the Anthropic SDK.
All LLM calls MUST go through the Anthropic SDK. Legacy OpenAI references MUST be migrated
on any file touched.

**Database**: PostgreSQL via Prisma ORM. Migrations MUST be idempotent and run via
`npm run db:setup`. No raw SQL outside migration files. Semantic search MUST use
`pgvector` (or equivalent Postgres-native extension) so the vector store co-locates
with the relational store.

**MCP Integration**: Sitecore Search MCP + Marketer/Agent API MCP (Railway). All Sitecore
read operations SHOULD prefer MCP tools where a tool exists. Third-party integrations
(Google Analytics, external search APIs) MUST also be exposed as MCP tools or typed
API clients — not inline fetch calls in route handlers.

**Authentication**: Sitecore OAuth 2.0. Token refresh MUST be transparent; after login
the user MUST be returned to their in-progress conversation.

**Hosting**: Vercel (Next.js app) + Railway (MCP server) + managed Postgres (Vercel
Postgres or Supabase). Hosting choices MUST minimize operational overhead and fixed cost.
Compute that can be serverless MUST be serverless.

**Local vs. iframe context**: The app MUST run locally without an active Sitecore iframe
context, falling back to mock/stub values for iframe-injected data (page ID, site context,
OAuth token). A `RUNTIME_CONTEXT=local|iframe` environment variable MUST gate this
behavior. Integration testing against real Sitecore MUST occur in the iframe environment.

**Visual documentation**: Workspace architecture (service topology, data flows, integration
points) and chat dialogue architecture (conversation state machines, profile routing logic)
MUST be documented as diagrams. Diagram source MUST be committed to the repository
(TODO(VISUAL_DOCS_TOOL): toolchain not yet chosen — Mermaid is the default candidate).

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

`system/base.md` is always loaded. Files under `tasks/` are loaded additively when the
assistant detects a matching intent — they overlay the base, never replace it. File paths
are the contract; renaming requires a corresponding code change in the instruction loader.

## Development Workflow

**Feature branches**: `###-feature-name` off `main`. PRs MUST include a Constitution Check.

**Constitution Check gates** (verify before merging any PR):
- [ ] No prompt strings hardcoded in TypeScript (Principle VI)
- [ ] No write to Sitecore without user confirmation step (Principle I)
- [ ] New integrations use typed API client layer, not inline fetch (Principle VII)
- [ ] New task behaviors live in `instructions/tasks/*.md`, not in TypeScript (Principle VI)
- [ ] No profile-switching logic introduced; task instructions are additive overlays (Principle IV)
- [ ] Guardrail coverage verified for any new task instruction or topic expansion (Principle II)
- [ ] Memory writes use the correct store (conversation vs. user knowledge) (Principle V)

**Streaming**: Chat responses MUST stream to the UI. Non-streaming is not acceptable for
the primary chat path.

**Environment variables**: All secrets declared in `.env.example`. No hardcoded credentials.

**Code style**: TypeScript strict mode. No `any` without a justifying comment.
Functional React components only.

## Governance

This constitution supersedes all other development practices for this project.

Amendments require a PR updating this file with a version bump:

- **MAJOR**: Backward-incompatible principle removal or redefinition
- **MINOR**: New principle or section added; material expansion of existing guidance
- **PATCH**: Clarification, wording, or non-semantic refinement

All PRs and code reviews MUST verify the Constitution Check gates above. Complexity
violations (skipping an architectural layer, hardcoding a prompt, etc.) MUST be documented
in the feature plan's Complexity Tracking table with a justification.

**Version**: 2.0.0 | **Ratified**: 2026-06-17 | **Last Amended**: 2026-06-17
