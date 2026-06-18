# Feature Specification: Context Awareness & Session Management

**Feature Branch**: `003-context-session-management`

**Created**: 2026-06-18

**Status**: Draft

**Input**: User description: "Context Awareness & Session Management — a foundational capability that gives users visibility into how much of the assistant's active context window is being used, and manages that context intelligently across the full lifecycle of a conversation. As users upload documents, receive image results, and accumulate tool call history, the context fills up. When users switch between multiple conversations and return to a previous one, they should not silently lose the context they were working with. The system must store full conversation history persistently so no data is ever lost, but apply smart strategies when loading a conversation into the active context window — prioritizing recent messages, preserving pinned documents or key reference material, and summarizing older turns rather than truncating them. Users should be able to see their context usage, understand what is currently in context, and have the ability to manage it (clear tool history, pin a document, etc.). The system must handle graceful overflow: warn the user when context is nearly full rather than silently dropping content."

## Clarifications

### Session 2026-06-18

- Q: When a conversation requires summarisation on load, what is the expected UX while waiting, and what triggers summarisation? → A: Proactive background summarisation triggered when a conversation exceeds a size/length threshold after the user switches away. Resume is always instant. If the background job hasn't completed before the user returns, a brief "Restoring your conversation…" loading state is shown as a fallback.
- Q: What is the canonical user-facing term for the active context window? → A: "conversation" — specifically "active conversation" to distinguish the active conversation from the stored conversation record. UI copy uses "Your active conversation is X% full."
- Q: When the system automatically summarises older turns, should this event be visible to the user in the conversation transcript? → A: A subtle inline marker is shown in the transcript (e.g., "Earlier messages summarised — full history saved") in muted/secondary styling — visible and persistent, but unobtrusive. No modal or blocking UI.
- Q: Should users be able to "pin" documents to protect them from summarisation? → A: Pinning removed from scope. Brand guides and briefs are stored in the Sitecore content system and retrieved via API — they are not user uploads that need manual protection. Brand context retrieval from Sitecore (ask the user which brand guide to load, retrieve it via API, inject it into the conversation) is a separate capability to be specified independently.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Marketer Sees How Full Their Active Conversation Is (Priority: P1)

A marketer is working on a content authoring session. They have uploaded a brand guide, run several tool calls to inspect page components, and had an extended back-and-forth with the assistant. They want to know — at a glance — how much active conversation remains before the assistant starts struggling to hold everything in mind at once. A visible indicator in the chat shows the current usage level and updates as the session progresses.

**Why this priority**: Visibility is the prerequisite for everything else. A user cannot make an informed decision about pinning, clearing, or summarising unless they first know that a problem exists. This story also has the widest reach — it benefits every user in every session, regardless of whether they ever hit a limit.

**Independent Test**: Load a conversation with several messages and an uploaded document; verify a context usage indicator is visible, shows a non-zero level, and updates after sending a new message.

**Acceptance Scenarios**:

1. **Given** the chat sidebar is open, **When** the user is in any active conversation, **Then** a context usage indicator is visible that shows the current fill level expressed in plain language (e.g., "42% full") or as a visual bar.
2. **Given** the marketer uploads a document, **When** the upload completes, **Then** the context usage indicator increases to reflect the added content.
3. **Given** the marketer asks for context details, **When** they request a breakdown, **Then** the assistant describes what is occupying the most space (e.g., "Your uploaded brand guide is the largest item, followed by recent tool results").
4. **Given** the indicator is visible, **When** the usage is below 60%, **Then** no warning state is shown — the indicator is informational only at this level.

---

### User Story 2 - Marketer Resumes a Previous Conversation Without Losing Work (Priority: P2)

A marketer has been working across two conversations simultaneously — one about a homepage redesign and one about a product launch. They switch to the homepage conversation after spending time on the product launch. When they return, the conversation picks up where it left off: recent messages are intact, the brand guide they uploaded is still available, and the assistant can reference things they discussed earlier without the marketer having to repeat themselves.

**Why this priority**: Multi-conversation switching is a core workflow for marketers managing multiple projects. Silent context loss on resume would be a trust-breaking failure — the user would not know whether the assistant remembers their previous work or not.

**Independent Test**: Create a conversation, upload a document, exchange five messages, switch to a different conversation, then switch back — verify the original conversation's recent messages and uploaded document are still available to the assistant.

**Acceptance Scenarios**:

1. **Given** a marketer has worked on a conversation and switches away, **When** they return to that conversation, **Then** the most recent messages are immediately available to the assistant without repeating context.
2. **Given** a conversation has a long history that exceeds available active conversation, **When** it is resumed, **Then** the most recent messages are loaded in full and older turns are represented as summaries — the assistant can reference older topics at a high level.
3. **Given** the marketer resumes a conversation and references something from early in the session, **When** the assistant cannot find it in the active conversation, **Then** it says so explicitly ("I have a summary of our earlier discussion — you may need to re-share the specific detail") rather than fabricating an answer.

---

### User Story 3 - Marketer Takes Control of What Stays in the Active Conversation (Priority: P3)

After a long session running many tool checks and receiving verbose results, the marketer notices the context indicator is getting high. They want to free up space without starting over. They can clear the accumulated tool call history — which they no longer need — while keeping the conversation messages and any documents that were loaded during the session.

**Why this priority**: Control empowers the user to keep working efficiently in long sessions without being forced to start a new conversation. It also reduces frustration when the assistant starts behaving as if it has forgotten things.

**Independent Test**: In a conversation with tool call history present, clear the tool history using the context management controls and verify the usage indicator decreases and the assistant no longer references the cleared tool results as part of the active conversation.

**Acceptance Scenarios**:

1. **Given** the marketer opens the context management panel, **When** they view it, **Then** they see a list of what is in their current active conversation, grouped by type (messages, documents, tool results), with the ability to act on each group.
2. **Given** the marketer selects "clear tool history," **When** the action is confirmed, **Then** the tool call results are removed from the active conversation, the usage indicator decreases, and the assistant no longer treats those results as currently active — though the messages referencing them remain.

---

### User Story 4 - Context Fills Up — Marketer Is Warned and Given Options (Priority: P4)

Midway through a complex authoring session, the marketer notices the context indicator turning amber. They have a large document uploaded, significant tool history, and a long conversation. The assistant proactively warns them that active conversation is nearly full and explains what is consuming it. The marketer is presented with clear options — summarise old messages, clear tool history, or continue and let the system manage automatically — rather than being left to guess why the assistant suddenly seems less capable.

**Why this priority**: Graceful overflow handling protects the user experience at the moment it is most at risk. Without it, the assistant silently degrades and the marketer loses trust without understanding why.

**Independent Test**: Fill a conversation to near-capacity with messages, tool results, and a document, then verify the assistant proactively warns the marketer with a plain-language explanation and at least one actionable option before capacity is reached.

**Acceptance Scenarios**:

1. **Given** the context usage reaches 80%, **When** the marketer sends their next message, **Then** the assistant includes a visible notice that active conversation is nearly full and briefly explains the main contributors.
2. **Given** the near-full warning has been shown, **When** the marketer takes no action, **Then** the system automatically summarises the oldest conversation turns to free space — and informs the marketer it has done so.
3. **Given** the system has summarised old turns automatically, **When** the marketer asks about something covered in a summarised section, **Then** the assistant acknowledges it has a summary rather than the full text and offers to look it up from stored history.
4. **Given** the context is at capacity and automatic summarisation has already occurred, **When** the marketer tries to upload another document, **Then** the system warns that there is not enough space and suggests clearing tool history before uploading.

---

### Edge Cases

- What if a single uploaded document is larger than the entire available active conversation? The system should warn the user during upload before processing completes, not after.
- What if context fills up mid-stream while the assistant is actively responding? The current response completes; the overflow notice appears in the following turn.
- What if the marketer clears tool history but then asks the assistant to re-run the same tool? The tool is re-run as a new call; no previous result is assumed.
- What if a conversation has no history yet (first message)? The context indicator shows near-zero and no management controls are needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chat interface MUST display a context usage indicator that shows the current fill level as a percentage and updates after each message, upload, or tool call completes.
- **FR-002**: The assistant MUST be able to describe, on request, which items are occupying the most active conversation, grouped by type (messages, documents, tool results).
- **FR-003**: When a conversation is resumed after switching away, the system MUST load the most recent messages in full and represent older turns as compressed summaries rather than dropping them. If the background summarisation job completed before resume, the conversation opens instantly. If not, a brief loading indicator is shown until it completes.
- **FR-003a**: The system MUST proactively summarise conversations in the background when a user switches away, but only when the conversation has accumulated enough content to risk exceeding the available active conversation on next load. Short or light conversations MUST NOT trigger background summarisation.
- **FR-004**: Users MUST be able to clear accumulated tool call results from the active conversation without deleting the conversation messages that reference them.
- **FR-005**: When context usage reaches 80%, the system MUST display a near-full warning to the user before they send their next message, naming the main space contributors.
- **FR-006**: When the system automatically summarises old conversation turns to free space, it MUST insert a subtle inline marker in the conversation transcript (e.g., "Earlier messages summarised — full history saved") in secondary styling. This marker is persistent — it remains visible when the conversation is resumed — and confirms that full history is still available in permanent storage.
- **FR-007**: All conversation content — messages, uploaded document text, tool results — MUST be persisted in full to permanent storage. Context window management decisions MUST NOT cause permanent data loss.
- **FR-008**: When an upload would exceed available active conversation, the system MUST warn the user before completing the upload rather than failing silently or dropping other content without notice.

### Key Entities

- **ConversationContext**: the active working snapshot for a conversation — current fill percentage and breakdown of space used by type (messages, documents, tool results).
- **ContextSummary**: a compressed representation of older conversation turns generated when the full history exceeds available active conversation; references the original stored turns so nothing is lost.
- **ContextEvent**: a logged record of any context management action taken — automatic summarisation, user-initiated clear — so the marketer has an audit trail of what changed and when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of context reduction events (automatic summarisation, content removal) are preceded by a visible notice to the user — no silent drops.
- **SC-002**: When resuming a conversation where background summarisation has completed, the conversation is available instantly (under 1 second). When the fallback loading state is required, the 10 most recent turns are available within 5 seconds of switching back.
- **SC-003**: A marketer can identify the top contributor to their context usage within 2 conversational exchanges — no digging required.
- **SC-004**: No conversation content is ever permanently lost due to context management — 100% of history remains retrievable from stored conversation records.
- **SC-005**: After clearing tool history, the context usage indicator reflects the reduction within one message turn.

## Assumptions

- Context usage percentage is calculated by the backend and expressed to the user as a human-readable percentage — raw token counts are not exposed in the UI.
- The 80% threshold for the near-full warning is a system default; per-user customisation of this threshold is out of scope.
- Summarisation of old turns is performed by the assistant itself as part of context loading — no separate summarisation service is required.
- Clearing tool history removes tool results from the active conversation but the messages that triggered and referenced those tools remain intact.
- The context usage indicator reflects the current active conversation only — it does not aggregate across all open conversations.
- Automatic context summarisation triggers only when the system needs to load a conversation that exceeds available space, not proactively during an active session unless the user is near the warning threshold.
- This spec governs active conversation management; the permanent storage layer (conversation persistence) is governed by the core chat application spec.
