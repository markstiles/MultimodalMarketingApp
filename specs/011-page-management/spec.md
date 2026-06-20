# Feature Specification: Guided Page Creation & Management

**Feature Branch**: `011-page-management`

**Created**: 2026-06-19

**Status**: Draft

**Input**: Marketers need to create and manage pages in Sitecore from the chat assistant. Page creation is a guided, multi-step conversation — the assistant helps the marketer choose the page type, parent location, name, and understand the content structure before creating anything. The assistant can also manage existing pages: rename, duplicate, update field values, create new versions, and manage page state. This feature augments MCP-based page operations for cases where direct Pages API access is required.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Marketer Creates a New Page with Guided Scaffolding (Priority: P1)

A marketer needs to add a new page to their site. From the chat, they describe the page they want (e.g., "I need a new blog post page about our summer campaign"). The assistant asks about the page type, where it should sit in the site hierarchy, and what the page should be named. It presents the full plan for approval before creating anything. Nothing is written to Sitecore until the marketer confirms.

**Why this priority**: Page creation with the wrong template or at the wrong location requires rework. A guided flow catches structural decisions before they are committed.

**Independent Test**: Ask the assistant to create a new page called "Summer Campaign" under the blog section. Verify the assistant asks about page type and location before creating anything, and that the page is created only after confirmation.

**Acceptance Scenarios**:

1. **Given** a marketer says "create a new page called Summer Campaign," **When** the assistant responds, **Then** it asks for the parent page location and page type before proposing any action.
2. **Given** the assistant presents the available page types for a parent location, **When** the marketer selects one, **Then** the assistant incorporates it into the creation plan and asks for any remaining details.
3. **Given** all required details are gathered, **When** the assistant presents the creation plan, **Then** it includes the page name, parent path, and page type — and creation does not proceed until the marketer explicitly approves.
4. **Given** the marketer approves, **When** the page is created, **Then** the assistant confirms the new page name, its location in the site hierarchy, and its page identifier.
5. **Given** the marketer describes the purpose or content of the page, **When** gathering scaffolding details, **Then** the assistant uses this context to suggest an appropriate page type and name rather than asking the marketer to specify every detail independently.

---

### User Story 2 — Marketer Manages an Existing Page (Priority: P1)

A marketer wants to make changes to an existing page — rename it, duplicate it for a variant, update specific field values, or create a new version to work on. The assistant identifies the page from context or asks the marketer to specify it, confirms the operation, and executes it.

**Why this priority**: Day-to-day content operations (renaming, updating fields, creating versions) are high-frequency tasks that benefit from chat-driven automation.

**Independent Test**: Ask the assistant to rename a page from "About" to "About Us." Verify the assistant confirms the target page and new name before making any change.

**Acceptance Scenarios**:

1. **Given** a marketer says "rename the About page to About Us," **When** the assistant identifies the page and confirms the change, **Then** the page is renamed only after explicit marketer approval.
2. **Given** a marketer says "duplicate the homepage," **When** confirmed, **Then** a copy of the page is created as a sibling with a clear name indicating it is a duplicate, and the assistant returns the new page's identifier.
3. **Given** a marketer says "update the title field on the Summer Campaign page to read 'Summer 2026 Campaign'," **When** confirmed, **Then** the specific field is updated and the assistant confirms the change.
4. **Given** a marketer wants to create a new draft version of a published page, **When** they ask to "create a new version of the homepage," **Then** a new page version is created and the assistant confirms the new version number.
5. **Given** a marketer asks for the current state of a page (status, version, workflow), **When** the assistant retrieves it, **Then** it presents the page's publishing status, version number, and whether it is live.

---

### User Story 3 — Marketer Searches for Pages (Priority: P2)

A marketer wants to find pages by name before managing them. They can describe the page they are looking for and the assistant returns matching pages with their location in the site hierarchy.

**Why this priority**: Page management operations require knowing the correct page before acting on it. Search reduces the chance of acting on the wrong page.

**Independent Test**: Ask the assistant to "find pages with 'campaign' in the name." Verify it returns a list of matching pages with their paths.

**Acceptance Scenarios**:

1. **Given** the marketer describes a page to find, **When** the assistant searches, **Then** it returns matching pages with their display name, parent path, and whether they are pages or folders.
2. **Given** multiple pages match the search, **When** the assistant returns results, **Then** it asks the marketer to confirm which page they want to act on before proceeding.
3. **Given** no pages match the search, **When** the assistant reports this, **Then** it suggests the marketer refine their search or create a new page.

---

### Edge Cases

- What if the marketer specifies a parent path that does not exist? The assistant reports the location cannot be found and asks for an alternative.
- What if the marketer tries to delete a page? Page deletion is supported as a confirmed, guarded operation with a clear warning that it is irreversible.
- What if two pages have the same name under different parents? The assistant presents both matches and asks the marketer to confirm which page they mean.
- What if a page has no compatible insert options (no allowed child templates) for the requested page type? The assistant reports this constraint and does not attempt creation.
- What if the marketer abandons the creation or edit flow mid-conversation? No changes are made to Sitecore; the assistant confirms nothing was written.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST guide the marketer through a structured conversation before creating a page — parent location and page type must be established before presenting a creation plan.
- **FR-002**: System MUST retrieve available page types (insert options) for a given parent location and present them to the marketer when creating a page.
- **FR-003**: System MUST present a complete creation plan (name, parent path, page type) and require explicit marketer approval before creating a page.
- **FR-004**: System MUST create the page after approval and confirm with the new page's name, path, and identifier.
- **FR-005**: System MUST support renaming a page with explicit marketer confirmation of the target page and new name before executing.
- **FR-006**: System MUST support duplicating a page with explicit marketer confirmation before executing.
- **FR-007**: System MUST support updating specific field values on a page with explicit marketer confirmation of the target page, field name, and new value before executing.
- **FR-008**: System MUST support creating a new version of a page and confirming the new version number after creation.
- **FR-009**: System MUST support retrieving the current state of a page (display name, version, workflow status, publishing state).
- **FR-010**: System MUST support searching for pages by name or display name and returning results with their location in the site hierarchy.
- **FR-011**: System MUST support deleting a page with an explicit warning that the action is irreversible, followed by explicit marketer confirmation, before executing.
- **FR-012**: System MUST scope all page operations to the marketer's active site and environment.
- **FR-013**: System MUST NOT proceed with any page write operation (create, rename, duplicate, update, delete) without at least one explicit marketer confirmation.

### Key Entities

- **Page**: Page ID, site, language, version, display name, parent path, template, workflow status, publishing status (live/not live).
- **PageVersion**: Version number, language, page ID, created date.
- **InsertOption**: Template ID, template name (available page types for a given parent).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Marketers can complete guided page creation in no more than 5 conversational turns (description → parent → type → name → confirm).
- **SC-002**: No page write operation (create, rename, duplicate, update, delete) is executed without at least one explicit marketer confirmation.
- **SC-003**: The assistant correctly surfaces available page types for the selected parent location before any creation decision is made.
- **SC-004**: Marketers can retrieve the current state of any page in their active site within 2 seconds of asking.
- **SC-005**: Search returns matching pages within 2 seconds and disambiguates when multiple pages share the same name.

---

## Assumptions

- The marketer's active session context provides the site identifier, language, and environment required for page operations.
- Page operations default to the primary language of the active site; multi-language operations are out of scope for v1.
- Layout updates (adding/removing/reordering components on a page) are out of scope for v1 — only field value updates are supported.
- Page translation is out of scope for v1.
- The assistant does not bulk-create pages; each page is created individually with its own confirmation gate.
- Retrieving insert options (available page types for a parent) requires the parent page ID — the assistant resolves this via search if the marketer provides a name rather than an ID.
- The Pages API is accessed using the same automation client credentials used elsewhere in the application.
