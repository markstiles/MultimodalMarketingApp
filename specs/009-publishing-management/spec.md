# Feature Specification: Publishing Management

**Feature Branch**: `009-publishing-management`

**Created**: 2026-06-19

**Status**: Draft

**Input**: Marketers need to trigger and monitor Sitecore content publishing from the chat interface. Publishing should be triggerable for individual pages, entire sites, or all content. The assistant reports progress and completion status. This feature augments MCP-based publishing operations for cases where direct publishing API access is required.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Marketer Publishes Content from Chat (Priority: P1)

A marketer has made content changes and wants to publish them to the live site without leaving the chat assistant. They describe what to publish — a specific page, a site, or all content — and the assistant creates the publishing job, confirms the request before executing, reports progress, and notifies when publishing is complete or if it fails.

**Why this priority**: Publishing is a frequent end-of-workflow action. Marketers need to confirm their changes are live without switching tools.

**Independent Test**: From the chat, ask to publish a specific page. Verify the assistant confirms the request, creates the job, and reports when it completes successfully.

**Acceptance Scenarios**:

1. **Given** a marketer says "publish the homepage," **When** the assistant confirms the request and the marketer approves, **Then** a publishing job is created for that item and the assistant reports the job ID and status.
2. **Given** a publishing job is running, **When** the marketer asks for a status update, **Then** the assistant reports the current status (queued, running, failed, or completed) and any statistics (items processed, items failed).
3. **Given** a publishing job completes successfully, **When** the status is checked, **Then** the assistant confirms the content is now live and provides a summary (total items published).
4. **Given** a publishing job fails, **When** the failure is detected, **Then** the assistant reports the failure and what was and was not published.
5. **Given** the marketer asks to "republish all content," **When** they confirm the request, **Then** a full site republish job is created.

---

### User Story 2 — Marketer Monitors and Manages Active Jobs (Priority: P1)

A marketer wants to see what publishing jobs are currently running or recently completed. They can ask for a summary, view the status of a specific job, or cancel a job that is no longer needed.

**Why this priority**: Marketers need visibility into publishing activity and the ability to stop jobs that were triggered in error.

**Independent Test**: Trigger a publishing job, then query its status. Verify the assistant returns the correct status and job details.

**Acceptance Scenarios**:

1. **Given** one or more publishing jobs exist, **When** the marketer asks "what's currently publishing?", **Then** the assistant lists active and recent jobs with their status, source, and start time.
2. **Given** no jobs are active or recent, **When** the marketer asks for a job list, **Then** the assistant says no publishing jobs are currently running or recently completed.
3. **Given** a running or queued publishing job, **When** the marketer says "cancel that job" and confirms, **Then** the job is cancelled and the assistant confirms cancellation.
4. **Given** a job that is already completed, **When** the marketer tries to cancel it, **Then** the assistant explains the job is already finished and cannot be cancelled.

---

### Edge Cases

- What if the marketer specifies a page that does not exist in Sitecore? The assistant reports that the item could not be found and no job is created.
- What if a publish job is created but Sitecore fails to start it? The assistant reports the error returned and suggests retrying.
- What if the marketer does not confirm the publish request? The job is not created; the assistant waits for explicit confirmation before any Sitecore write operation.
- What if the marketer asks to cancel a job that is in "Canceling" state? The assistant informs them that cancellation is already in progress.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST require explicit marketer confirmation before creating any publishing job.
- **FR-002**: System MUST support publishing a specific item (by page name or path) by creating an item-scoped publishing job.
- **FR-003**: System MUST support publishing an entire site by creating a site-scoped publishing job.
- **FR-004**: System MUST support triggering a full content republish (all items, all languages) by creating a republish job.
- **FR-005**: System MUST report the publishing job ID and initial status after a job is successfully created.
- **FR-006**: System MUST allow marketers to query the current status of a publishing job by referencing the job or asking for active jobs.
- **FR-007**: System MUST list active and recently completed publishing jobs when asked, including job status, source, and timing information.
- **FR-008**: System MUST support cancelling a queued or running publishing job with explicit marketer confirmation before executing the cancellation.
- **FR-009**: System MUST report job statistics when available: total items sent, items processed, and items failed.
- **FR-010**: System MUST handle publishing API errors gracefully — if a job cannot be created or status cannot be retrieved, the assistant reports the specific error to the marketer.

### Key Entities

- **PublishingJob**: Job ID, name, source, status (Queued / Running / Completed / Failed / Canceled / Canceling), queued time, start time, finish time, created by, statistics (items sent, processed, failed), publish scope (item or site), publish mode (Smart / Republish / Incremental).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Marketers can initiate a publishing job from chat within 2 interactions (description + confirmation).
- **SC-002**: Publishing job status is retrievable within 3 seconds of the marketer asking.
- **SC-003**: All publishing write operations (create, cancel) require at least one explicit marketer confirmation before executing.
- **SC-004**: The assistant correctly reports job completion or failure for 100% of jobs it created within the same session.
- **SC-005**: Marketers can cancel an active job from chat without navigating to any other tool.

---

## Assumptions

- The marketer's active session context provides the tenant identifier required for publishing API authentication.
- Publishing jobs are tenant-scoped; the assistant only creates and monitors jobs for the active tenant.
- Smart publishing mode is the default for item and site publishes; Republish is only used when explicitly requested.
- The assistant cannot resolve page names to item IDs autonomously — it relies on other tools (MCP, GraphQL) or asks the marketer to confirm the item path. Confirming the correct item is the marketer's responsibility.
- Job status polling (to track running jobs) is on-demand — the assistant does not poll in the background between conversation turns.
- The publishing API is accessed using the same automation client credentials (`SITECORE_CLIENT_ID_AUTOMATION` / `SITECORE_CLIENT_SECRET_AUTOMATION`) used elsewhere in the application.
