# Quickstart Validation Guide: Content Development Workflow

**Feature**: 007-content-dev-workflow | **Date**: 2026-06-19

## Prerequisites

- Local dev environment running (`docker compose up` from project root)
- Active Sitecore XM Cloud environment with media library access
- `SITECORE_CLIENT_ID_AUTOMATION` + `SITECORE_CLIENT_SECRET_AUTOMATION` set in `.env`
- A tenant name and site name accessible from session context (or set via local mock)
- No existing `Content Strategy` folder at the test site path (start clean) — or confirm path doesn't exist for a fresh run

## Running the App

```bash
docker compose up
```

Frontend: `https://localhost:3000` | Backend: `http://localhost:8000`

---

## Scenario 1 — Start a New Content Project (US1 / P1)

**Goal**: Verify FR-001, FR-002, FR-004, FR-006, FR-007, FR-008, FR-013 and SC-001, SC-002, SC-003

**Steps**:

1. Ensure no `Content Strategy` folder exists for the test site in the media library.
2. Open the assistant and say: *"I'd like to build a content strategy for our website."*
3. **Expected**: Assistant detects content development intent (FR-001), calls `scan_content_project_status`, and presents a project overview showing all 6 phases as Not Started — then explains the six-phase workflow and proposes starting with Research.
4. Confirm you want to begin Research.
5. **Expected**: Assistant runs any available analysis tools first (noting results or gaps), then asks targeted research questions about audience, competitors, and content goals.
6. Answer the research questions.
7. **Expected**: Assistant generates the Research Brief in full for review — does not save yet (FR-006).
8. Request a revision to one section (e.g., "make the competitive analysis more specific").
9. **Expected**: Assistant revises and re-presents — still does not save until you approve (FR-007, SC-003).
10. Approve the Research Brief.
11. **Expected**: Assistant saves to `/sitecore/media library/Project/{tenant}/{site}/Content Strategy/Research/research-brief.docx` and confirms the save with the full path (FR-008, FR-013). States that the next phase is Strategy (SC-001).

**Verify in Sitecore media library**: `research-brief.docx` present in the Research folder for the test site.

**Negative check** — decline save:
- After reviewing the Research Brief, say "I don't want to save this yet."
- **Expected**: No file is saved; session continues and the assistant asks what you'd like to change (SC-003).

---

## Scenario 2 — Resume an In-Progress Project (US2 / P2)

**Goal**: Verify FR-002, FR-003, FR-005, FR-009, FR-010 and SC-002, SC-004, SC-006

**Prerequisite**: `research-brief.docx` present in the media library from Scenario 1 (or uploaded manually).

**Steps**:

1. Start a **new assistant session** (new conversation).
2. Say: *"Let's continue working on our content strategy."*
3. **Expected**: Assistant calls `scan_content_project_status`, detects the Research Brief, and presents a project status overview — listing Research as Complete and Strategy through Execution as Not Started — without the marketer re-explaining history (SC-002, SC-006).
4. Confirm you want to proceed to Strategy.
5. **Expected**: Assistant calls `get_phase_artifact_content` for the Research phase, references its key findings, and begins Strategy questions without asking you to repeat research context (FR-005).

**Staleness check**:
- Manually change the modification date of `research-brief.docx` to be older than 365 days (or set a test flag).
- Start a new session and ask to continue the content strategy.
- **Expected**: Before beginning any phase work, assistant surfaces a staleness warning and offers three options: proceed anyway, return to Research, or review the Research Brief's contents (FR-009, FR-010, SC-004).

---

## Scenario 3 — Strategy Phase Cross-Phase Reference (US3 / P2)

**Goal**: Verify FR-004, FR-005, FR-006, FR-007, FR-008 and SC-005

**Prerequisite**: `research-brief.docx` present (from Scenario 1 or manual upload).

**Steps**:

1. In a session where Research is complete, say: *"I'm ready to develop the content strategy."*
2. **Expected**: Assistant summarizes the Research Brief's key findings (audience, competitive context, opportunities) before asking any Strategy questions.
3. Complete the Strategy questions.
4. **Expected**: The generated `content-strategy.docx` explicitly references audience segments and competitive findings from the Research Brief (SC-005).
5. Approve and save.
6. **Expected**: Saved to `/sitecore/media library/Project/{tenant}/{site}/Content Strategy/Strategy/content-strategy.docx`.

---

## Scenario 4 — Phase Skip Quality Warning (US4 / P3)

**Goal**: Verify FR-011 and SC-007

**Steps**:

1. With no existing artifacts (clean slate), say: *"Skip straight to building the content structure."*
2. **Expected**: Assistant warns that Structure typically builds on Research and Strategy and explicitly asks for confirmation before proceeding without them (FR-011). Warning is shown before any Structure work begins (SC-007).
3. Confirm you want to skip.
4. **Expected**: Assistant begins Structure phase and notes it will need additional context that would normally come from prior phases — proceeds without blocking.

**Negative check** — no silent skip:
- Ask to skip to Structure without ever saying yes or confirming.
- **Expected**: Assistant re-prompts for confirmation; does not advance silently.

---

## Scenario 5 — Research Phase Tool Degradation (FR-016)

**Goal**: Verify graceful fallback when analysis tools are unavailable

**Steps**:

1. Disable or mock the analysis tools (set MCP tools to return empty results or configure unavailability in test env).
2. Start a new content project.
3. **Expected**: Assistant notes that live analysis data was not available (specifying which tools were unavailable), then proceeds with marketer questions for the Research phase — session is not blocked (FR-016).
4. Complete the Research phase and save the artifact.
5. **Expected**: Research Brief notes the data gap (e.g., "Note: Site analytics were not available during this session — update this section when data is accessible.").

---

## DB Verification

No new database tables for this feature. Verify state in the Sitecore media library directly.

**Media library path to verify**:
```
/sitecore/media library/Project/{tenant}/{site}/Content Strategy/
```

Check the folder structure and modification dates on canonical artifact files after each scenario.

## References

- [Tool contracts](contracts/tool-contracts.md)
- [Data model](data-model.md)
- [Spec](spec.md) — FR-001 through FR-016, SC-001 through SC-007
