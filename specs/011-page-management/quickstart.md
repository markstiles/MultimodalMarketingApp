# Quickstart Validation Guide: Guided Page Creation & Management

**Feature**: 011-page-management | **Date**: 2026-06-19

This guide documents the runnable end-to-end validation scenarios that prove the feature works correctly. Run these against a live Sitecore XM Cloud environment after implementing the tasks in `tasks.md`.

---

## Prerequisites

1. App running locally with `RUNTIME_CONTEXT=iframe` (or in Sitecore iframe context)
2. `SITECORE_CLIENT_ID_AUTOMATION` and `SITECORE_CLIENT_SECRET_AUTOMATION` set with valid automation credentials
3. `SITECORE_PAGES_API_BASE_URL` set (default: `https://xmapps-api.sitecorecloud.io/api/v1/pages`)
4. An active Sitecore XM Cloud tenant with at least one site and a known page in the site hierarchy
5. MLflow running at `MLFLOW_TRACKING_URI` for trace verification

---

## Scenario 1: Guided Page Creation (US1, FR-001–004)

**Goal**: Verify the assistant asks for parent location and page type before creating anything, and that the page is created only after explicit confirmation.

**Steps**:
1. Open the chat assistant.
2. Say: `"I need to create a new page called Summer Campaign"`
3. **Expected**: Assistant asks where in the site hierarchy the page should go (parent location) — it does NOT propose a creation plan yet.
4. Provide a parent location (e.g., `"under the Blog section"`).
5. **Expected**: Assistant searches for the Blog section, then presents available page types for that location (insert options from Pages API). If the Blog section is not found, the assistant asks for an alternative.
6. Select a page type.
7. **Expected**: Assistant presents a complete creation plan: page name ("Summer Campaign"), parent path, and page type. No page has been created yet.
8. Approve by saying `"yes"` or `"create it"`.
9. **Expected**: Assistant calls `create_page`, then confirms the new page's display name and page ID. No page is created before step 8.

**Verification**:
- Check in Sitecore Pages that the page exists under the correct parent with the selected template.
- Check MLflow trace: `get_insert_options` called before `create_page`; `create_page` called only after the user's approval message.

---

## Scenario 2: Page Search and Disambiguation (US3, FR-010)

**Goal**: Verify search returns results and handles duplicate names.

**Steps**:
1. Say: `"Find pages with 'campaign' in the name"`
2. **Expected**: Assistant returns matching pages with their display name and parent path.
3. If two pages with similar names are found: **Expected**: Assistant asks the marketer to confirm which page they want to work with before proceeding.
4. Say: `"Find pages named 'Home'"` (likely multiple matches).
5. **Expected**: All matches returned; assistant disambiguates before acting.

**Verification**:
- Returned pages are scoped to the active site — no results from other sites appear.

---

## Scenario 3: Page State Retrieval (US2, FR-009)

**Goal**: Verify state retrieval within 2 seconds.

**Steps**:
1. Say: `"What's the status of the Summer Campaign page?"`
2. **Expected**: Assistant searches for the page, then returns: display name, version number, workflow state, and whether it is live on Sitecore Edge. Response arrives in under 2 seconds.

---

## Scenario 4: Rename Page (US2, FR-005)

**Goal**: Verify rename confirmation gate.

**Steps**:
1. Say: `"Rename the About page to About Us"`
2. **Expected**: Assistant searches for "About", presents the target page and new name for confirmation. Rename does NOT execute yet.
3. Confirm.
4. **Expected**: Assistant renames the page and confirms the new name.
5. **Negative test**: Abandon mid-flow (stop responding). Verify the page name was NOT changed.

---

## Scenario 5: Page Deletion Warning (US2, FR-011)

**Goal**: Verify the assistant warns about irreversibility before deleting.

**Steps**:
1. Say: `"Delete the Summer Campaign page"`
2. **Expected**: Assistant presents the target page and warns explicitly that deletion is permanent and cannot be undone. Does NOT delete yet.
3. Confirm deletion.
4. **Expected**: Page is deleted. Assistant confirms.
5. **Negative test**: At step 3, say `"actually don't"`. Verify the page still exists in Sitecore.

---

## Scenario 6: Create Page Version (US2, FR-008)

**Goal**: Verify version creation and version number reporting.

**Steps**:
1. Say: `"Create a new version of the Homepage"`
2. **Expected**: Assistant identifies the Homepage, confirms version creation, then calls `create_page_version` and reports the new version number.

---

## Scenario 7: No Insert Options Available (Edge Case)

**Goal**: Verify the assistant handles locations that do not allow child pages.

**Steps**:
1. Ask to create a page under a location that has no insert options configured.
2. **Expected**: Assistant reports that no page types are available for that location and does NOT attempt to create a page.

---

## Scenario 8: Auth Token Shared Between Pages API and Agents API (Regression)

**Goal**: Verify the `sitecore_auth.py` refactor did not break `content_workflow_service.py`.

**Steps**:
1. Trigger a content workflow action that calls `scan_content_project_status` (e.g., say `"what's my content project status?"`).
2. **Expected**: The scan succeeds — auth token is acquired via `sitecore_auth.py` correctly.

---

## Environment Variable Checklist

| Variable | Required | Notes |
|----------|----------|-------|
| `SITECORE_CLIENT_ID_AUTOMATION` | Yes | Shared with spec 007 |
| `SITECORE_CLIENT_SECRET_AUTOMATION` | Yes | Shared with spec 007 |
| `SITECORE_PAGES_API_BASE_URL` | Yes (new) | Default: `https://xmapps-api.sitecorecloud.io/api/v1/pages` |
