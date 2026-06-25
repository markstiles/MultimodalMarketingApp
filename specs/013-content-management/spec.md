# Feature Specification: Content Item CRUD

**Feature Branch**: `013-content-management`

**Created**: 2026-06-25

**Status**: Draft

**Input**: Marketers need to create, read, update, and delete Sitecore content items from the chat assistant. Content items are the reusable data records that back pages and components — they hold field values like titles, body text, dates, and references. This feature exposes the Sitecore Agent API content surface so the assistant can author and manage content items on behalf of the marketer.

---

## Overview

This feature gives marketers natural-language access to Sitecore content item CRUD operations. The assistant can create a content item with all field values in a single step, retrieve items by ID or path, update specific fields, and delete items — all with appropriate confirmation gates on write operations. The assistant can also list available child item types for a given parent location to guide creation.

---

## User Stories

### User Story 1 — Marketer Creates a Content Item with Field Values (Priority: P1)

A marketer wants to create a new content item — for example, a product detail record with a title, description, and image reference — without navigating to the Sitecore editor. They describe the item to the assistant, which gathers the required fields, presents the creation plan, and creates the item only after explicit confirmation.

**Acceptance Criteria**:

1. **Given** a marketer asks to create a content item, **When** the assistant gathers the item name, parent path, and template type, **Then** it presents the full creation plan (name, path, template, field values) before writing anything.
2. **Given** the marketer approves the creation plan, **When** the assistant creates the item, **Then** it returns the new item's ID and path.
3. **Given** the marketer asks what item types can be created at a given location, **When** the assistant calls `list_content_insert_options`, **Then** it presents the available templates so the marketer can choose one.
4. **Given** the marketer provides field values inline, **When** the item is created, **Then** all provided field values are persisted in a single API call without a separate update step.
5. **Given** the marketer does not confirm the creation plan, **When** they say "cancel" or give no explicit approval, **Then** no item is created in Sitecore.

---

### User Story 2 — Marketer Reads Content Items by ID or Path (Priority: P1)

A marketer wants to inspect a content item's current field values — to verify what is published, to audit a record, or to understand its structure before editing. They can ask the assistant to retrieve an item by its Sitecore item ID or by its content path.

**Acceptance Criteria**:

1. **Given** a marketer provides an item ID, **When** the assistant calls `get_content_item_by_id`, **Then** it returns the item's fields, path, and template information.
2. **Given** a marketer provides a content path, **When** the assistant calls `get_content_item_by_path`, **Then** it returns the same item details as retrieval by ID.
3. **Given** the requested item does not exist, **When** the assistant reports this, **Then** it suggests the marketer verify the path or ID.
4. **Given** the assistant retrieved an item, **When** it presents the response, **Then** field values are shown in a readable format — not raw JSON.

---

### User Story 3 — Marketer Updates or Deletes Content Items (Priority: P1)

A marketer wants to modify specific fields on an existing content item or remove an item that is no longer needed. Every write operation requires explicit marketer confirmation before it is executed.

**Acceptance Criteria**:

1. **Given** a marketer asks to update a field on a content item, **When** the assistant confirms the target item, field name, and new value, **Then** it calls `update_content` only after explicit approval.
2. **Given** the assistant completes an update, **When** it confirms, **Then** it states which fields were changed and their new values.
3. **Given** a marketer asks to delete a content item, **When** the assistant presents the deletion confirmation, **Then** it includes an explicit warning that deletion is irreversible.
4. **Given** the marketer confirms deletion, **When** the assistant calls `delete_content`, **Then** it confirms the item has been removed and states its former path.
5. **Given** the marketer does not explicitly confirm a write or delete action, **When** the conversation continues, **Then** no changes are made to Sitecore.

---

## Out of Scope

- Bulk content item creation or import from external sources
- Content item publishing and workflow state transitions (covered by spec 009)
- Moving or renaming content items (path restructuring)
- Content versioning and language fallback configuration
- Retrieving content item children or tree traversal beyond insert options
- Field-level validation rules (template-enforced constraints are the CMS's responsibility)
