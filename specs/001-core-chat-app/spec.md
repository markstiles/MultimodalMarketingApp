# Feature Specification: Core Chat Application

**Feature Branch**: `001-core-chat-app`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Core chat application — Next.js sidebar chat UI embedded in Sitecore XM Cloud Pages Editor via iframe. Includes streaming AI responses via Anthropic Claude, Sitecore OAuth authentication, layered service architecture (route handlers / services / API clients / resources), conversation persistence in PostgreSQL, local vs iframe runtime context switching, and the instruction loader for markdown-based task overlays. The chat must be usable both inside the Sitecore iframe and standalone locally for development."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marketer Sends a Chat Message and Receives a Streaming Response (Priority: P1)

A non-technical marketer opens the Sitecore Pages Editor, sees the chat sidebar, types a question about their site or content, and receives a response that streams in word-by-word — giving immediate visual feedback rather than a blank wait. The assistant's reply is coherent, on-topic, and relevant to their marketing task.

**Why this priority**: This is the core value of the entire product. Nothing else matters if the basic send-message / receive-answer loop does not work reliably. Every other story builds on top of this.

**Independent Test**: Open the chat sidebar, type "What can you help me with?", and verify a streamed response appears within 2 seconds.

**Acceptance Scenarios**:

1. **Given** the chat sidebar is open, **When** the user types a message and submits, **Then** the assistant response begins streaming within 2 seconds and completes without error.
2. **Given** a streaming response is in progress, **When** the user scrolls the conversation, **Then** the stream continues uninterrupted and auto-scrolls to the latest content.
3. **Given** the assistant receives an off-topic question (e.g., politics, medical advice), **When** it responds, **Then** it politely declines and redirects to marketing-relevant topics in one sentence.
4. **Given** a network error interrupts the stream, **When** the error occurs, **Then** the user sees a clear error message and a retry option — the conversation is not lost.

---

### User Story 2 - Marketer Authenticates via Sitecore OAuth (Priority: P2)

Before the assistant can act on the user's Sitecore environment, the user must be identified. The user is prompted to log in with their Sitecore credentials when the sidebar first loads (or when the session expires). After login they are returned to their in-progress conversation without losing any context.

**Why this priority**: Authentication gates all write operations and personalizes conversation history. The chat is still partially useful without auth (read-only answers) but personalization and Sitecore actions require it.

**Independent Test**: Load the sidebar without an active session, complete the Sitecore OAuth flow, and verify the conversation the user started before login is still visible and active.

**Acceptance Scenarios**:

1. **Given** no active session, **When** the sidebar loads, **Then** the user is prompted to log in with a single clear call-to-action.
2. **Given** the user completes the OAuth flow, **When** they are redirected back, **Then** their pre-login conversation is restored and the session is active.
3. **Given** an active session token is nearing expiry, **When** the user sends a message, **Then** the token is refreshed transparently — the user sees no interruption.
4. **Given** a token refresh fails, **When** the user attempts to send a message, **Then** they are prompted to re-authenticate and their current conversation is preserved.

---

### User Story 3 - Developer Runs the App Locally Without Sitecore (Priority: P3)

A developer working on the assistant can start the app on their local machine without access to a live Sitecore environment. A local-mode flag provides stub values for the iframe context (page ID, site, auth token) so the full chat loop can be exercised and debugged without spinning up Sitecore.

**Why this priority**: Developer experience is not user-facing value, but without it the team cannot build or test the application. It is ordered last because it is a prerequisite for development, not for end-user delivery.

**Independent Test**: Set the local runtime flag, start the app, send a message, and verify a response is received using stub Sitecore context — with no live Sitecore connection required.

**Acceptance Scenarios**:

1. **Given** the local runtime flag is set, **When** the app starts, **Then** stub values are used for all iframe-injected context (page ID, site ID, auth token).
2. **Given** local mode is active, **When** a developer sends a chat message, **Then** the full chat loop executes including instruction loading, response streaming, and conversation persistence.
3. **Given** the app is running in iframe mode (no local flag), **When** it starts, **Then** it reads context values from the Sitecore iframe and the local stubs are not used.

---

### Edge Cases

- What happens when the user submits an empty message?
- What happens when the AI provider is unavailable or rate-limited?
- What happens if the instruction file for a detected task type is missing?
- What happens when the conversation history grows very large (hundreds of messages)?
- What happens if two browser tabs open the same conversation simultaneously?
- What happens when the Sitecore iframe context changes (user navigates to a different page inside the editor)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render a chat sidebar within the Sitecore XM Cloud Pages Editor via iframe embed.
- **FR-002**: The system MUST stream assistant responses to the user in real time — text MUST appear progressively, not all at once.
- **FR-003**: The system MUST enforce topic guardrails — requests about politics, personal advice, medical diagnoses, legal advice, gaming, or gambling MUST be declined with a one-sentence redirect.
- **FR-004**: The system MUST authenticate users via Sitecore OAuth 2.0 before enabling write operations or personalized conversation history.
- **FR-005**: The system MUST transparently refresh OAuth tokens without interrupting the user's conversation.
- **FR-006**: The system MUST restore a user's in-progress conversation after they complete the OAuth login flow.
- **FR-007**: The system MUST persist all conversation messages per authenticated user and per Sitecore site.
- **FR-008**: The system MUST load assistant instructions from Markdown files at runtime, resolving them by file-path convention — no instruction text may be hardcoded in application logic.
- **FR-009**: The system MUST support additive task instruction overlays — when a user's intent matches a task type, the corresponding instruction file is loaded on top of the base instructions without replacing the conversational context.
- **FR-010**: The system MUST operate in a local development mode using stub values for all Sitecore iframe context, controlled by an environment variable.
- **FR-011**: The system MUST operate in an iframe production mode where all context values are read from the Sitecore Pages Editor iframe.
- **FR-012**: Any action that writes to Sitecore MUST present an explicit confirmation step to the user before execution.
- **FR-013**: The system MUST be organized into four code layers: route handlers, services, API clients, and resources — with no cross-layer skipping.

### Key Entities

- **Conversation**: Belongs to one user and one Sitecore site. Contains an ordered list of messages and a title.
- **Message**: A single turn in a conversation — either a user message or an assistant response. Records timestamp, role, and full content.
- **User Session**: Tracks the authenticated user's identity, OAuth access token, refresh token, and expiry. Linked to a Sitecore user account.
- **Instruction File**: A Markdown file on disk at a known convention path. Loaded at runtime. Can be a base instruction (always loaded) or a task overlay (loaded conditionally on intent).
- **Runtime Context**: The set of values injected by the Sitecore iframe at startup — page ID, site ID, language, and auth token. In local mode, replaced by environment-variable stubs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can send a message and see the first words of the assistant's response within 2 seconds under normal network conditions.
- **SC-002**: The full chat loop — message sent, response streamed, conversation saved — completes without error in 95% of interactions.
- **SC-003**: A developer can start the application locally and complete a full chat interaction in under 5 minutes from a clean checkout, with no Sitecore environment required.
- **SC-004**: Guardrail deflections occur for 100% of messages that match the prohibited topic list, with no false positives on legitimate marketing questions in a standard smoke test.
- **SC-005**: After an OAuth token refresh, the user's conversation continues without any visible interruption or data loss.

## Assumptions

- Users access the chat exclusively through the Sitecore XM Cloud Pages Editor sidebar (desktop browser); mobile and standalone page access are out of scope for v1.
- A single Anthropic API key is shared across all users; per-user API key management is out of scope.
- The Sitecore OAuth flow follows the standard authorization code flow; PKCE and custom grant types are out of scope unless discovered during planning.
- The `instructions/` directory and its subdirectory conventions (`system/`, `tasks/`, `guardrails/`) are established by this feature and serve as the contract for all future instruction files.
- Local development mode is intended for developers only — it MUST NOT be enabled in any deployed environment.
- Concurrent multi-tab usage of the same conversation is not supported in v1; last-write-wins behavior is acceptable.
