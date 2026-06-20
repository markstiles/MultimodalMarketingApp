# Feature Specification: Guided Site & Collection Management

**Feature Branch**: `010-site-management`

**Created**: 2026-06-19

**Status**: Draft

**Input**: Marketers need to create and manage Sitecore sites and site collections from the chat assistant. Site creation is a structured, multi-step conversation — the assistant guides the marketer through choosing a site collection, naming the site, selecting languages, and understanding the template choices before executing. This feature augments MCP-based site operations for cases where direct Sites API access is required.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Marketer Creates a New Site (Priority: P1)

A marketer needs to set up a new website in Sitecore. From the chat, they describe the site they want to create. The assistant walks them through all required decisions — site collection, site name, language(s) — and presents a summary for confirmation before creating anything. Nothing is created until the marketer explicitly approves the full plan.

**Why this priority**: Site creation is a high-stakes operation. Getting the name, collection, or language wrong can require significant rework. A guided, confirmable flow prevents errors.

**Independent Test**: Ask the assistant to create a new site named "Acme Brand." Verify the assistant asks for collection and language before creating anything, and that the site is only created after explicit approval.

**Acceptance Scenarios**:

1. **Given** a marketer says "I need to create a new site," **When** the assistant responds, **Then** it asks for the site name, target site collection, and at least one language before proposing any action.
2. **Given** the assistant has gathered all required details, **When** it presents the creation plan, **Then** the plan includes site name, collection, and language(s), and creation does not proceed until the marketer approves.
3. **Given** the marketer approves the plan, **When** the site is created, **Then** the assistant confirms the new site name and its location within the site collection.
4. **Given** the marketer wants to create a site in a collection that does not yet exist, **When** this is discovered, **Then** the assistant offers to create the collection first as a prerequisite step (with its own confirmation).
5. **Given** a site name that is already in use, **When** the assistant attempts creation, **Then** it informs the marketer and asks for an alternative name.

---

### User Story 2 — Marketer Creates a Site Collection (Priority: P1)

A marketer needs to group a set of related sites under a new site collection. From the chat, they describe the collection and its purpose. The assistant gathers the collection name, confirms the details, and creates it.

**Why this priority**: Site collections are a prerequisite for site creation and are frequently needed when onboarding a new brand or region.

**Independent Test**: Ask the assistant to create a site collection named "EMEA." Verify it confirms the name and creates the collection.

**Acceptance Scenarios**:

1. **Given** a marketer asks to create a site collection, **When** the assistant responds, **Then** it asks for the collection name and an optional description before proposing any action.
2. **Given** the marketer approves the creation plan, **When** the collection is created, **Then** the assistant confirms the collection name and confirms it is ready for sites to be added.
3. **Given** a collection name that violates Sitecore naming rules (too long, invalid characters), **When** the assistant receives this feedback, **Then** it explains the constraint and asks the marketer to provide a valid name.

---

### User Story 3 — Marketer Lists and Reviews Sites (Priority: P2)

A marketer wants to know what sites exist in the environment. They can ask the assistant to list all sites, sites within a specific collection, or look up a particular site's details.

**Why this priority**: Visibility into existing sites is useful context before creating new ones or when selecting a site to work on.

**Independent Test**: Ask the assistant to list all sites. Verify it returns site names and their collections.

**Acceptance Scenarios**:

1. **Given** sites exist in the environment, **When** the marketer asks "what sites do we have?", **Then** the assistant returns a list of sites organized by collection, showing each site's name.
2. **Given** no sites exist in a collection, **When** the marketer asks about that collection, **Then** the assistant reports the collection exists but contains no sites.
3. **Given** the marketer asks about a specific site, **When** the assistant retrieves it, **Then** it shows the site name, collection, and available languages.

---

### Edge Cases

- What if the marketer provides a site name with invalid characters? The assistant explains the naming rules and asks for a corrected name before proceeding.
- What if the marketer abandons the creation flow mid-conversation? No site or collection is created; the assistant confirms nothing was written to Sitecore.
- What if the Sites API is temporarily unavailable? The assistant reports the error and suggests retrying. It does not fall back to MCP if the Sites API was already selected as the path.
- What if the marketer requests to delete a site? Site deletion is out of scope for v1 — the assistant explains this is not available and suggests contacting an administrator.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST guide the marketer through a structured conversation before creating a site or site collection — name, target collection (for sites), and language(s) must all be confirmed before any write operation.
- **FR-002**: System MUST present a full creation plan (name, collection, language list) and require explicit marketer approval before executing a site or collection creation.
- **FR-003**: System MUST create a site collection when requested, capturing the collection name and optional description.
- **FR-004**: System MUST create a site within a specified site collection, capturing site name and at least one language.
- **FR-005**: System MUST offer to create a missing site collection as a prerequisite when a marketer specifies a collection that does not exist during site creation.
- **FR-006**: System MUST list all sites in the active environment, organized by site collection, when asked.
- **FR-007**: System MUST validate site and collection names against Sitecore rules before attempting creation, and report specific constraint violations to the marketer.
- **FR-008**: System MUST confirm successful creation with the site or collection name and its location in the environment.
- **FR-009**: System MUST NOT delete sites or site collections — this operation is out of scope for v1.
- **FR-010**: System MUST scope all site operations to the marketer's active environment.

### Key Entities

- **SiteCollection**: ID, name, display name, description, environment.
- **Site**: ID, name, display name, site collection, language(s), environment.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Marketers can complete guided site creation in no more than 5 conversational turns (description → name → collection → language → confirm).
- **SC-002**: No site or collection is created without at least one explicit confirmation from the marketer.
- **SC-003**: The assistant correctly identifies and reports naming constraint violations before attempting any API call.
- **SC-004**: All created sites appear correctly scoped to the marketer's active environment and collection.
- **SC-005**: Marketers receive a list of all sites in the environment within 2 seconds of requesting it.

---

## Assumptions

- The marketer's active session context provides the environment identifier.
- Site template selection is out of scope for v1 — sites are created using the environment default. Template selection can be added in a future iteration.
- Language management (adding/removing languages from an existing site) is out of scope for v1.
- Renaming sites or collections is out of scope for v1.
- Site deletion requires administrator-level access and is explicitly excluded from the assistant's capabilities.
- Sitecore naming rules for sites and collections: max 50 characters, Latin alphanumeric characters, spaces and dashes only; cannot start with a dash or space.
- The Sites API is accessed using the same automation client credentials used elsewhere in the application.
