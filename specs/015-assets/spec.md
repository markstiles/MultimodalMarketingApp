# Feature Specification: Media Asset Management

**Feature Branch**: `015-assets`

**Created**: 2026-06-25

**Status**: Draft

**Input**: Marketers need to manage media assets in Sitecore's media library from the chat assistant — uploading new images and files, searching for existing assets, and updating asset metadata such as alt text. This feature uses the Sitecore Agent API REST asset surface, which is distinct from the semantic image search capability in spec 008 (PostgreSQL vector search for discovery). This spec covers operational asset management: uploading, retrieving metadata, and updating records.

---

## Overview

This feature gives marketers REST-based access to the Sitecore media library through the chat assistant. They can search for assets by name or metadata, view asset details, upload new files, and update asset metadata — all without leaving the chat interface. This complements semantic image search (spec 008), which is used for AI-driven discovery; this spec handles direct asset operations.

---

## User Stories

### User Story 1 — Marketer Searches and Views Asset Information (Priority: P1)

A marketer wants to locate a specific asset in the media library — for example, to confirm an image exists before referencing it from a content item, or to review its alt text for accessibility compliance. The assistant can search assets by name or metadata and retrieve full details for any individual asset.

**Acceptance Criteria**:

1. **Given** a marketer asks to search for an asset by name, **When** the assistant calls `search_assets`, **Then** it returns a list of matching assets with their IDs, names, and media paths.
2. **Given** a marketer asks for details on a specific asset by ID, **When** the assistant calls `get_asset_info`, **Then** it returns the asset's metadata including name, file type, dimensions (if applicable), alt text, and media library path.
3. **Given** no assets match the search query, **When** the assistant reports this, **Then** it offers to help the marketer upload a new asset.
4. **Given** multiple assets match, **When** the assistant presents results, **Then** it lists them in a readable format and asks the marketer to confirm which one they want to act on before proceeding.

---

### User Story 2 — Marketer Uploads New Assets and Updates Asset Metadata (Priority: P1)

A marketer wants to add a new image or document to the Sitecore media library from the chat assistant, or update the alt text and other metadata on an existing asset. Every write operation requires explicit confirmation before it is executed.

**Acceptance Criteria**:

1. **Given** a marketer wants to upload a new asset, **When** they provide the file and target media library path, **Then** the assistant confirms the upload details (filename, path) before calling `upload_asset`.
2. **Given** the assistant completes an upload, **When** it confirms, **Then** it returns the new asset's ID and media library path.
3. **Given** a marketer wants to update an asset's alt text or other metadata, **When** the assistant confirms the target asset and the new metadata values, **Then** it calls `update_asset` only after explicit marketer approval.
4. **Given** the assistant completes a metadata update, **When** it confirms, **Then** it states which metadata fields were changed and their new values.
5. **Given** the marketer does not explicitly confirm a write operation, **When** the conversation continues, **Then** no changes are made to the media library.

---

## Out of Scope

- Semantic/AI-powered image discovery by visual similarity or concept (covered by spec 008)
- Asset deletion from the media library
- Folder creation or media library tree restructuring
- Bulk asset uploads
- Asset publishing and workflow state transitions
- CDN cache invalidation after asset updates
