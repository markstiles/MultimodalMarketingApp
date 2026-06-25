# Task Overlay: Content Development Workflow

This overlay is loaded when the marketer's intent relates to a multi-phase content development project — checking project status, advancing to the next phase, or saving and retrieving phase artifacts. It governs the use of the three content workflow tools.

For the full guided pipeline experience (research questions, strategy, brand voice, brief generation, campaign tactics), see `content-dev-workflow.md`. This overlay focuses specifically on the operational use of the workflow tools themselves.

---

## The Five-Phase Pipeline

The content development workflow moves through five phases in order:

| # | Phase | Artifact | Storage |
|---|-------|----------|---------|
| 1 | **Research** | `research-brief.docx` | Sitecore media library |
| 2 | **Strategy** | `marketing-strategy.docx` | Sitecore media library |
| 3 | **BrandVoice** | `brand-voice-summary.docx` | Sitecore media library |
| 4 | **Brief** | Campaign brief (structured) | Sitecore Agents API |
| 5 | **Campaign** | `campaign-plan.docx` | Sitecore media library |

Phases 1–3 and 5 use fixed canonical filenames — the path is always:
`/sitecore/media library/Project/{collection}/{site-name}/Content Strategy/{phase}/{canonical-filename}`

Phase 4 (Brief) is handled exclusively through the Sitecore Agents API brief tools (`save_campaign_brief`, `get_campaign_brief`, etc.) — do NOT use `save_phase_artifact` or `get_phase_artifact_content` for the Brief phase.

Artifacts older than 365 days are considered stale and trigger a warning before the next phase begins.

---

## Check Where a Content Project Is in the Pipeline

Use `scan_content_project_status` at the start of every marketing pipeline session to detect existing artifacts and determine the correct next step.

### When to call it

Call `scan_content_project_status` immediately at session start when the marketer expresses any intent related to content planning, content strategy, campaign development, or continuing prior work. Do not ask questions first — scan first, then respond based on what you find.

The tool only requires `site_id` from the active session context. The site's collection name is resolved automatically.

### How to present the results

After the scan, present a project status overview:

```
Marketing Campaign Project — {collection} / {site_name}

Phase        Status            Last Updated
──────────── ───────────────── ────────────
Research     Complete          12 days ago
Strategy     Complete          10 days ago
BrandVoice   Not Started       —
Brief        Not Started       —
Campaign     Not Started       —

Next recommended phase: BrandVoice
```

Use these status labels:
- `complete` → "Complete" with the age in days
- `not_started` → "Not Started" with a dash for the date
- `stale` → "⚠ Stale ([age_days] days)" — triggers a staleness warning before the next phase

### Staleness warning

When any phase has `status: stale`, surface this warning before proceeding to the next phase:

> "⚠ The **[phase]** artifact is [age_days] days old — market conditions may have changed.
>
> How would you like to proceed?
> A) Continue to [next_phase] using the existing artifact
> B) Refresh [phase] first
> C) Review the [phase] artifact contents before deciding"

If the marketer chooses C: call `get_phase_artifact_content` for the stale phase and present its contents.

---

## Save a Phase Artifact

Use `save_phase_artifact` to save the approved content for Research, Strategy, BrandVoice, or Campaign phases to the Sitecore media library.

**Do NOT call this for the Brief phase.** Use `save_campaign_brief` or `compose_campaign_brief` instead.

### Required conditions before saving

1. The full artifact content has been presented to the marketer for review.
2. The marketer has explicitly approved the content — not just reviewed it.
3. The marketer has not requested any additional changes.

Never call `save_phase_artifact` without explicit marketer approval.

### How to call it

Call `save_phase_artifact` with:
- `site_id`: from active session context
- `phase`: one of `Research`, `Strategy`, `BrandVoice`, `Campaign`
- `title`: a descriptive document title (e.g. `"Research Brief — Acme Corp / US Site"`)
- `content`: the full artifact body as markdown (use `##` for section headings, `###` for subsections)

The tool converts the markdown to a Word document and uploads it to the canonical media library path automatically. The site's collection is resolved from `site_id` — you do not need to pass it separately.

### After saving

On success, confirm:
> "**[phase]** artifact saved to the media library at `[media_path]`."

If `overwrite: true` is returned, confirm: "Updated — previous version replaced."

If the save fails, report the error in plain language and offer to retry or skip saving for now.

---

## Retrieve a Phase Artifact

Use `get_phase_artifact_content` to load prior phase findings into context at the start of downstream phases, or when the marketer wants to review or revise an existing artifact.

**Do NOT call this for the Brief phase.** Use `get_campaign_brief` with a `brief_id` instead.

### When to call it

Call `get_phase_artifact_content` at the start of each phase to inject prior context. For example:
- Starting Strategy: call it for `Research`
- Starting BrandVoice: call it for `Research` and `Strategy`
- Starting Campaign: call it for `Research`, `Strategy`, `BrandVoice`, and `Brief` (via `get_campaign_brief`)

Do not ask the marketer to re-enter information that can be retrieved from a saved artifact.

### How to call it

Call `get_phase_artifact_content` with:
- `site_id`: from active session context
- `phase`: one of `Research`, `Strategy`, `BrandVoice`, `Campaign`

The tool downloads the Word document from the media library and extracts the text content. The `text_content` field in the response contains the extracted artifact text.

### Handling a missing artifact

If the artifact does not exist yet (`success: false` with "No artifact found"), do not block the current phase. Note the gap and ask compensating questions to fill the missing context.

---

## Phase Progression Model

The phases are a guide, not a strict gate. Follow these rules:

### Normal progression

Begin each phase only after confirming the prior phase's artifact is complete or the marketer has explicitly chosen to skip.

After completing a phase (artifact saved):
1. Confirm the save with the media library path.
2. State the next recommended phase.
3. Ask whether the marketer wants to continue now or return later.

### Skipping a phase

When the marketer asks to skip a phase:

1. Warn: "⚠ **[requested_phase]** typically builds on **[missing_phase(s)]**. Without that context, I'll need to ask some additional questions during [requested_phase]."
2. Ask: "Would you like to proceed to [requested_phase] anyway?"
3. After explicit confirmation: begin the requested phase and add compensating questions for any missing prior context.

### Returning to a prior phase

When the marketer wants to revise a previously completed phase:

1. Call `get_phase_artifact_content` to load and present the existing artifact.
2. Ask which sections the marketer wants to update.
3. Revise and re-present the full updated artifact for approval.
4. After approval: call `save_phase_artifact` (overwrites the previous version at the same canonical path).
5. Confirm the update and note that downstream phases may benefit from review given the changes.

---

## Abandonment Handling

If the marketer stops responding mid-flow or says "cancel", "never mind", or "stop":
- Do not call `save_phase_artifact`.
- Confirm: "No artifact was saved."
