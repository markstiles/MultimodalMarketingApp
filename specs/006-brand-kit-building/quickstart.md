# Quickstart Validation Guide: Brand Kit Building

**Feature**: 006-brand-kit-building | **Date**: 2026-06-18

## Prerequisites

- Local dev environment running (`docker compose up` from project root)
- At least one Published brand kit in the Sitecore organization (brand kit ID known)
- `BRAND_SERVICE_ORG_ID` set in `.env`
- `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION` set in `.env`
- Sample PDF available for upload (any small PDF ≤ 50 MB)
- Alembic migration applied: `cd backend && alembic upgrade head`

## Running the App

```bash
docker compose up
```

Frontend: `https://localhost:3000` | Backend: `http://localhost:8000`

---

## Scenario 1 — Upload a Document to a Brand Kit (US1 / P1)

**Goal**: Verify FR-001, FR-002, FR-003, FR-004, FR-015 and SC-001, SC-002

**Steps**:

1. Open the assistant and say: *"I'd like to add a document to our brand kit `[brand_kit_id]`"*
2. **Expected**: Assistant lists the brand kit's current document library (up to 5 names + remaining count if more than 5 exist) and asks for confirmation before proceeding.
3. Attach or reference a PDF file and confirm the upload.
4. **Expected**: Assistant confirms the document was uploaded successfully, names the file, and explicitly states it is in **Draft status** and will not affect brand guidelines until the processing pipeline is run.
5. **Timing check**: Confirmation should appear within 30 seconds of confirming the upload (SC-001).
6. Verify in the Sitecore brand management UI that the document appears in the brand kit's library with Draft status.

**Negative check** — attempt upload without confirmation:
- Reference the document but say "never mind" when asked to confirm.
- **Expected**: No document is uploaded; no record created in `brand_document_uploads`.

**Negative check** — unsupported format:
- Try to upload a `.xlsx` file.
- **Expected**: Assistant identifies the unsupported format and lists accepted formats; no upload attempted.

---

## Scenario 2 — Trigger Brand Ingestion Pipeline (US2 / P2)

**Goal**: Verify FR-007, FR-009, FR-010, FR-011, FR-015, FR-016 and SC-002, SC-003, SC-004

**Prerequisite**: At least one Draft document in the brand kit library (upload one via Scenario 1 or directly via Sitecore UI).

**Steps**:

1. Say: *"Run the brand ingestion pipeline for brand kit `[brand_kit_id]`"*
2. **Expected**: Assistant warns that processing will overwrite existing AI-Editable sections, explains the Non-AI Editable option for protecting manual edits, and asks for explicit confirmation.
3. Optionally, ask the assistant to show brand kit subsections to review editability before confirming.
4. Confirm the pipeline trigger.
5. **Expected**: Assistant confirms the pipeline is running and states the expected duration (~10–20 minutes).
6. Continue using the assistant normally during this time (SC-04 check — conversation should not be blocked).
7. When the pipeline completes (check Sitecore UI for status), send any message to the assistant.
8. **Expected**: Before the model responds, a pipeline completion notification appears in the conversation indicating success or failure (SC-003).

**Duplicate guard check**:
- Immediately after triggering, try to trigger the same pipeline again.
- **Expected**: Assistant reports the pipeline is already running rather than triggering a duplicate.

**Cross-type simultaneous check**:
- While ingestion is running, trigger enrichment.
- **Expected**: Both pipelines are tracked independently; assistant confirms enrichment is also running.

---

## Scenario 3 — Generate Brand Kit Content from a Website (US3 / P3)

**Goal**: Verify FR-012, FR-013 and SC-005

**Steps**:

1. Say: *"Generate brand kit content for `[brand_kit_id]` from our website at `https://example.com`"*
2. **Expected**: Assistant describes what will happen (enrichment pipeline will analyze the site and update brand kit content) and asks for confirmation — within three conversational steps (SC-005).
3. Confirm the action.
4. **Expected**: Enrichment pipeline is triggered with the site URL; assistant confirms it is running.
5. Check `brand_pipeline_runs` table: a row should exist with `pipeline_type=enrichment`, `site_url=https://example.com`, `status=running`.

**Unreachable URL check**:
- Repeat with a URL that does not resolve (e.g., `https://thisdomaindoesnotexist-abc123.com`).
- **Expected**: Assistant informs the marketer the site could not be reached; no pipeline is triggered; no row in `brand_pipeline_runs`.

---

## Scenario 4 — Non-AI Editable Toggle (FR-017)

**Goal**: Verify a marketer can protect a manually customized subsection before triggering processing.

**Steps**:

1. Say: *"Show me the sections in brand kit `[brand_kit_id]`"*
2. **Expected**: Assistant lists sections and subsections with their AI-editability status.
3. Say: *"Protect the 'Brand Voice' subsection from being overwritten"*
4. **Expected**: Assistant confirms with a description of what will happen and asks for confirmation.
5. Confirm.
6. **Expected**: Subsection is marked Non-AI Editable; assistant confirms the change.
7. Verify in Sitecore UI that the subsection shows as Non-AI Editable.

---

## DB Verification Queries

```sql
-- Check pending pipeline runs
SELECT brand_kit_id, pipeline_type, status, triggered_at, notification_sent
FROM brand_pipeline_runs
ORDER BY triggered_at DESC;

-- Check document uploads
SELECT brand_kit_id, filename, status, created_at
FROM brand_document_uploads
ORDER BY created_at DESC;
```

## References

- [Tool contracts](contracts/tool-contracts.md)
- [Data model](data-model.md)
- [Spec](spec.md) — FR-001 through FR-017, SC-001 through SC-006
