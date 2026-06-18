---
description: "Task list for Core Chat Application"
---

# Tasks: Core Chat Application

**Input**: Design documents from `specs/001-core-chat-app/`

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

> **Architecture note**: Tasks T001–T052 were planned for a Next.js-only/Prisma stack.
> The actual implementation follows `plan.md`: Python/FastAPI backend + Next.js frontend +
> SQLModel/asyncpg + Alembic + LangGraph. All features are implemented; file paths differ
> from the original task descriptions in some cases.

---

## Phase 1: Setup

**Purpose**: Initialize the Next.js project with all dependencies, configuration, and directory structure before any feature work begins.

- [X] T001 Initialize Next.js 15 App Router project with TypeScript strict mode at repository root (`package.json`, `tsconfig.json`, `next.config.ts`)
- [X] T002 [P] Install all primary dependencies: `@anthropic-ai/sdk`, `@sitecore-marketplace-sdk/client`, `@auth0/auth0-react`, `prisma`, `@prisma/client`, `tailwindcss`, `react` 19
- [X] T003 [P] Create directory structure: `app/api/`, `components/`, `lib/clients/`, `lib/services/`, `lib/resources/`, `lib/hooks/`, `instructions/system/`, `instructions/guardrails/`, `instructions/tasks/`, `tests/unit/`, `tests/conversation/`, `prisma/`
- [X] T004 [P] Configure `next.config.ts` with Node.js runtime default, `outputFileTracingIncludes` for `./instructions/**` on all `/api/**` routes, and CSP header `frame-ancestors https://pages.sitecorecloud.io https://*.sitecorecloud.io`
- [X] T005 [P] Create `.env.example` documenting all required variables: `RUNTIME_CONTEXT`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `LOCAL_PAGE_ID`, `LOCAL_SITE_ID`, `LOCAL_LANGUAGE`, `DATABASE_URL`, `AUTH0_SECRET`, `AUTH0_BASE_URL`, `AUTH0_ISSUER_BASE_URL`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`
- [X] T006 [P] Configure Tailwind CSS (`tailwind.config.ts`, `app/globals.css`)
- [X] T007 Configure Docker local Postgres in `docker/docker-compose.yml` and `docker/README.md` (use existing `docker/` setup if already present)

---

## Phase 2: Foundational

**Purpose**: Shared infrastructure that all user stories depend on — types, Prisma schema, and the Prisma singleton. MUST be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 Create shared TypeScript types in `lib/resources/types.ts`: `RuntimeContext`, `InstructionSet`, `MessageParam`, `ConversationSummary`, `ConversationDetail`, `ApiErrorCode`
- [X] T009 Write Prisma schema in `prisma/schema.prisma` with models: `User` (id, sitecoreId unique, email, createdAt), `UserSession` (id, userId unique, accessToken, refreshToken, expiresAt, updatedAt), `Conversation` (id, userId, siteId, title?, deletedAt?, createdAt, updatedAt, indexes: [userId,siteId,deletedAt] and [updatedAt]), `Message` (id, conversationId, role enum, content, createdAt, index: [conversationId,createdAt])
- [X] T010 Create initial Prisma migration and `npm run db:setup` script that runs `prisma migrate deploy`
- [X] T011 Create Prisma singleton in `lib/resources/prisma.ts` using `globalThis` pattern for serverless-safe connection reuse
- [X] T012 [P] Create stub instruction files: `instructions/system/base.md` (placeholder base prompt text), `instructions/guardrails/core.md` (placeholder guardrail rules), and all five task overlays in `instructions/tasks/` (`content-audit.md`, `campaign-design.md`, `seo-optimization.md`, `component-population.md`, `site-management.md`) with placeholder content

**Checkpoint**: Foundation ready — database schema migrated, types defined, instruction stubs in place. User story work can begin.

---

## Phase 3: User Story 1 — Streaming Chat Loop (Priority: P1) 🎯 MVP

**Goal**: A user can type a message in the chat sidebar and receive a streamed assistant response. Guardrails active. Conversation persisted.

**Independent Test**: Open `http://localhost:3000`, type "What can you help me with?", verify streamed response appears within 2 seconds and conversation is saved to the database.

### Implementation for User Story 1

- [X] T013 [P] [US1] Create `lib/resources/prisma.ts` conversation query helpers: `createConversation`, `appendMessage`, `getConversationWithMessages`, `updateConversationTitle` — all scoped by userId + conversationId ownership check
- [X] T014 [P] [US1] Create `lib/clients/anthropic.ts`: Anthropic SDK wrapper exposing `stream(messages: MessageParam[], systemPrompt: string): AsyncIterable<StreamEvent>` where `StreamEvent` is `{ type: 'delta', text: string } | { type: 'done' } | { type: 'error', code: string }`
- [X] T015 [P] [US1] Create `lib/services/instruction-loader.ts`: reads `instructions/system/base.md` + `instructions/guardrails/core.md` on every call; appends `instructions/tasks/{taskName}.md` if taskName is in the allowed set (`content-audit`, `campaign-design`, `seo-optimization`, `component-population`, `site-management`); module-level `Map` cache; graceful fallback if task file missing; path traversal guard via allowlist
- [X] T016 [US1] Create `lib/services/chat.ts`: `ChatService.stream()` orchestrates — load instructions → create/validate conversation → save user message → call `AnthropicClient.stream()` → pipe SSE events → save complete assistant message on `done` → async update conversation title if first message
- [X] T017 [US1] Create `app/api/chat/route.ts` (POST, Node.js runtime): validate request body (`conversationId | null`, `message`, `context`); call `ChatService.stream()`; return `ReadableStream` response with `Content-Type: text/event-stream`; emit `conversationId` event first; handle errors with `{ type: 'error', code }` event before close
- [X] T018 [P] [US1] Create `lib/hooks/useChat.ts`: manages `messages: MessageParam[]` state and `streaming: string` partial-text state; `send(text)` posts to `/api/chat`, reads SSE via `ReadableStream.getReader()`; appends assistant message to `messages` only on `done`; preserves `messages` on error; exposes `loading`, `error`, `retry()`, `conversationId`
- [X] T019 [P] [US1] Create `components/MessageBubble.tsx`: renders a single message with role-based styling (user right-aligned, assistant left-aligned); renders `streaming` prop as in-progress bubble with cursor indicator
- [X] T020 [P] [US1] Create `components/MessageList.tsx`: scrollable container; auto-scrolls to bottom on new content; renders `MessageBubble` for each message plus one streaming bubble when `streaming` is non-empty
- [X] T021 [P] [US1] Create `components/ChatInput.tsx`: textarea input; Enter-to-submit (Shift+Enter for newline); disabled while `loading`; empty-message guard; shows character count if near limit
- [X] T022 [US1] Create `components/ChatPanel.tsx`: composes `MessageList` + `ChatInput`; wires `useChat` hook; shows error banner with retry button on stream error; full-height flex layout suitable for sidebar embedding
- [X] T023 [US1] Create `app/page.tsx` and `app/layout.tsx`: minimal sidebar shell rendering `ChatPanel`; sets `<html>` lang, viewport meta for iframe embedding
- [X] T024 [US1] Write `instructions/system/base.md` with real base system prompt: assistant identity (Sitecore marketing assistant), communication style (plain, encouraging, proactive), and reference to guardrails
- [X] T025 [US1] Write `instructions/guardrails/core.md` with real guardrail rules: prohibited topic list (politics, personal advice, medical, legal, gaming, gambling), required redirect behavior (one sentence, no preachiness), permitted topic list (marketing, Sitecore, competing products in marketing context)

**Checkpoint**: US1 fully functional — send a message, receive a streaming response, conversation saved to DB. Guardrails active.

---

## Phase 4: User Story 2 — Sitecore OAuth Authentication (Priority: P2)

**Goal**: Users are prompted to log in via Sitecore Auth0 on first load. Post-login, their in-progress conversation is restored. Token refresh is transparent.

**Independent Test**: Load sidebar without a session, complete the OAuth flow at `auth.sitecorecloud.io`, verify return to sidebar with session active and any pre-login conversation visible.

### Implementation for User Story 2

- [X] T026 [P] [US2] Create `lib/clients/auth.ts`: Auth0 client helpers — `getSession(req)`, `encryptToken(token)`, `decryptToken(token)`, `isTokenExpiringSoon(expiresAt, thresholdMinutes = 5)`
- [X] T027 [P] [US2] Create `lib/services/conversation.ts`: `ConversationService` — `upsertUser(sitecoreId, email)`, `upsertSession(userId, tokens)`, `clearSession(userId)`, `getSessionForUser(userId)`
- [X] T028 [US2] Create `app/api/auth/status/route.ts` (GET): reads session cookie; returns `{ authenticated, user: { id, email } | null, expiresAt | null }`
- [X] T029 [US2] Create `app/api/auth/login/route.ts` (GET): builds Auth0 authorize URL with PKCE, `state` param encoding `returnTo` + `conversationId`; redirects; sets `SameSite=None; Secure` on session cookie
- [X] T030 [US2] Create `app/api/auth/callback/route.ts` (GET): exchanges code for tokens via Auth0 token endpoint; upserts `User` and `UserSession` (encrypted tokens); redirects to `returnTo` with `conversationId` query param preserved
- [X] T031 [US2] Create `app/api/auth/refresh/route.ts` (POST): uses stored refresh token to obtain new access token; upserts `UserSession`; returns `{ expiresAt }`; clears session and returns 401 if refresh fails
- [X] T032 [US2] Create `components/AuthGate.tsx`: on mount calls `/api/auth/status`; if unauthenticated, renders login prompt with single CTA button (links to `/api/auth/login?returnTo=...&conversationId=...`); if authenticated, renders `children`; stores in-progress `conversationId` in `sessionStorage` before redirect
- [X] T033 [US2] Update `app/layout.tsx` to wrap content in `AuthGate` (iframe mode only — skip in local mode based on `NEXT_PUBLIC_RUNTIME_CONTEXT` env var)
- [X] T034 [US2] Update `app/api/chat/route.ts` to validate auth session from cookie on each request; pass `userId` from session into `ChatService.stream()` for conversation ownership scoping
- [X] T035 [US2] Update `useChat.ts` to read `conversationId` from URL query param on init (restores post-login conversation); clear query param from URL after pickup via `history.replaceState`

**Checkpoint**: US1 + US2 both functional — authenticated chat with persistent conversations, transparent token refresh.

---

## Phase 5: User Story 3 — Local Development Mode (Priority: P3)

**Goal**: Developers can run the full chat loop locally with no Sitecore Cloud Portal connection, using env-var stubs for all iframe-injected context.

**Independent Test**: Set `RUNTIME_CONTEXT=local` in `.env.local`, run `npm run dev`, send a message, verify streaming response using stub context — no Sitecore connection required.

### Implementation for User Story 3

- [X] T036 [P] [US3] Create `lib/clients/sitecore-context.ts`: exports `getSitecoreContext(): Promise<RuntimeContext>`; in `iframe` mode initialises `@sitecore-marketplace-sdk/client` and resolves `pages.context` subscription; in `local` mode returns `{ pageId: LOCAL_PAGE_ID, siteId: LOCAL_SITE_ID, language: LOCAL_LANGUAGE }` from env vars immediately
- [X] T037 [P] [US3] Create `lib/hooks/useSitecoreContext.ts`: React hook wrapping `getSitecoreContext()`; exposes `context: RuntimeContext | null` and `loading: boolean`; subscribes to context updates in iframe mode (page navigation within Sitecore updates context)
- [X] T038 [US3] Update `components/ChatPanel.tsx` to consume `useSitecoreContext` and pass `context` into `useChat.send()` calls; show loading state while context resolves
- [X] T039 [US3] Update `app/api/chat/route.ts` to accept `context` from request body (already in contract); validate that `RUNTIME_CONTEXT` is not `local` in production builds (warn, not block — enforcement is via deployment config)
- [X] T040 [US3] Update `app/api/auth/status/route.ts` and `components/AuthGate.tsx` to skip auth check when `NEXT_PUBLIC_RUNTIME_CONTEXT=local`; always return authenticated stub user in local mode
- [X] T041 [US3] Update `README.md` (or create if absent) with local development quickstart: prerequisites, env setup, Docker DB start, `npm run db:setup`, `npm run dev`; reference `specs/001-core-chat-app/quickstart.md` for full validation scenarios

**Checkpoint**: All three user stories functional. Full chat loop works in both local and iframe modes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge case handling, error states, and quality improvements that span all user stories.

- [X] T042 Add empty-message guard to `app/api/chat/route.ts` — return 400 if `message` is empty or whitespace-only
- [X] T043 Add rate-limit and upstream-error handling to `app/api/chat/route.ts` — catch Anthropic `RateLimitError` and emit `{ type: 'error', code: 'rate_limit' }` SSE event before closing stream
- [X] T044 Add large-conversation guard to `lib/services/chat.ts` — if message history exceeds 100 messages, truncate oldest messages (keep system prompt + last 50 turns) before sending to Anthropic
- [X] T045 [P] Handle Sitecore iframe context change in `useSitecoreContext.ts` — when `pages.context` subscription emits a new `itemId`, update `context` and emit a UI hint ("Page context updated")
- [X] T046 [P] Add `lib/services/guardrails.ts` topic classifier: lightweight keyword/pattern match on user message; logs detected category (`politics`, `medical`, `legal`, etc.) to console/future analytics; does NOT block request — model enforces guardrails via system prompt
- [X] T047 [P] Write `instructions/tasks/content-audit.md` with real content audit task overlay instructions
- [X] T048 [P] Write `instructions/tasks/campaign-design.md` with real campaign design task overlay instructions
- [X] T049 [P] Write `instructions/tasks/seo-optimization.md` with real SEO optimization task overlay instructions
- [X] T050 [P] Write `instructions/tasks/component-population.md` with real component population task overlay instructions
- [X] T051 [P] Write `instructions/tasks/site-management.md` with real site management task overlay instructions
- [ ] T052 Run quickstart validation from `specs/001-core-chat-app/quickstart.md` and confirm all 5 success criteria pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — core MVP, no dependency on US2/US3
- **Phase 4 (US2)**: Depends on Phase 3 being complete (auth wraps the chat loop)
- **Phase 5 (US3)**: Depends on Phase 3 (local mode wraps the same chat loop); can run in parallel with Phase 4
- **Phase 6 (Polish)**: Depends on all story phases being complete

### Within Each Phase

- Tasks marked `[P]` have no dependencies on incomplete tasks in the same phase — run in parallel
- Tasks without `[P]` must run after their preceding task in the same story
- `T016` depends on `T014` + `T015` (chat service needs both Anthropic client and instruction loader)
- `T017` depends on `T016` (route handler needs the service)
- `T022` depends on `T019` + `T020` + `T021` (panel composes all three sub-components)
- `T034` depends on `T028`–`T031` (chat route needs auth session reading)

### Parallel Opportunities

```
# Phase 3 — launch these together after T012:
T013 [P] conversation query helpers
T014 [P] Anthropic client
T015 [P] instruction loader
T018 [P] useChat hook (depends only on T017 being specified, not implemented)
T019 [P] MessageBubble component
T020 [P] MessageList component
T021 [P] ChatInput component

# Phase 5 — launch these together after T035:
T036 [P] sitecore-context client
T037 [P] useSitecoreContext hook

# Phase 6 — launch all task overlay instructions together:
T047–T051 [P] all five task overlay .md files
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `npm run dev`, open `http://localhost:3000`, confirm streaming chat, guardrails, and DB persistence all work
5. This is a shippable demo — chat works, auth is not yet required

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → MVP: streaming chat works ✅
3. Phase 4 → Auth: personalized conversations ✅
4. Phase 5 → Local dev mode: developer experience ✅
5. Phase 6 → Polish: edge cases + real instruction content ✅

---

## Notes

- `[P]` = parallelizable — no dependency on incomplete sibling tasks
- `[US1/2/3]` = maps task to its user story for traceability
- All file paths are relative to the repository root
- Token encryption in `UserSession` is required — do not store plain-text tokens
- `RUNTIME_CONTEXT=local` must never appear in `.env.production` or any deployed environment config
- Task overlays in Phase 6 (T047–T051) should be written by the product team / content designer, not auto-generated — placeholder content from T012 is sufficient to complete earlier phases
