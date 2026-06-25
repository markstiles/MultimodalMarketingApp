# Task Overlay: Publishing

This overlay is loaded when the marketer's intent relates to publishing Sitecore content, checking publish job status, or managing publishing jobs. It governs the guided conversation flow for all publishing operations.

Publishing jobs are asynchronous. Once started, they run in the background — do NOT poll or repeatedly call status tools unless the marketer explicitly asks for a status update.

## Intent Classification — Read This First

Before calling any tool, classify the marketer's intent:

| Intent | Signal words | Correct action | NEVER do |
|--------|-------------|----------------|----------|
| **Publish content** | "publish", "push to live", "push to edge", "go live", "deploy content" | Guided publish flow | Do NOT create a job without the marketer specifying what to publish |
| **Check status** | "status", "what's publishing", "is it done", "check publish", "any jobs running" | Call `list_publishing_jobs` or `get_publishing_job` immediately | No confirmation needed |
| **Publishing summary** | "how many jobs", "summary", "publishing overview" | Call `get_publishing_summary` immediately | No confirmation needed |

**If the intent is ambiguous**, ask: "Are you looking to publish content, or check the status of existing publish jobs?"

---

## Check Publish Status (Read-Only)

These are read-only operations — call immediately, no confirmation needed.

### Check recent jobs

Call `list_publishing_jobs`. To filter by status, pass `status` (e.g. `"Running"`, `"Queued"`, `"Failed"`, `"Completed"`).

Present the results:

> **Recent publishing jobs**
> | Job | Source | Status | Queued |
> |-----|--------|--------|--------|
> | [name] | [source] | [status] | [queued_time] |

If no jobs are found with the current filter, note that and offer to broaden the filter.

### Check a specific job

If the marketer provides a job ID, call `get_publishing_job` with that ID.

Present the result:

> **Publishing job: [name]**
> - **Status**: [status]
> - **Source**: [source]
> - **Queued**: [queued_time]
> - **Started**: [start_time]
> - **Finished**: [finish_time]
> - **Statistics**: [statistics summary if available]

### Publishing summary

Call `get_publishing_summary`. Present the counts:

> **Publishing job summary**
> - Queued: [queued]
> - Running: [running]
> - Completed: [completed]
> - Failed: [failed]
> - Canceled: [canceled]

---

## Publish Content Flow

Use this flow when the marketer wants to publish content to the live environment (Sitecore XM Cloud Edge).

### Step 1 — Clarify what to publish

If the marketer did not specify what to publish, ask:
> "What would you like to publish? For example: a specific page, a set of items, or the full site?"

Determine the scope:
- **Full site republish**: All content is republished from scratch.
- **Incremental / smart**: Only changed items since the last publish.
- **Specific items**: One or more item IDs provided explicitly.

### Step 2 — Determine publish options

Gather the following from context or conversation:

| Option | What to ask |
|--------|-------------|
| **Scope** | Full site, incremental, or smart? (default: smart if not specified) |
| **Locales** | Which languages to publish? (default: `["en"]` unless the marketer specifies others) |
| **Related items** | Should related items be published alongside? (default: no) |
| **Children** | Should child items be included? (default: no) |

For simple cases (e.g. "publish the site"), use smart site publish with the default locale. Do not over-ask — only prompt for options that are genuinely ambiguous.

### Step 3 — Present the publish plan and confirm

Present the plan before calling any tool:

> **Publish plan**
> - **Scope**: [full site / incremental / smart / specific items]
> - **Locales**: [en, fr-CA, ...]
> - **Include related items**: [yes / no]
> - **Include children**: [yes / no]
>
> Ready to publish? Reply "yes" or "publish it" to confirm.

Do not call `create_publishing_job` until the marketer explicitly approves.

### Step 4 — Create the publishing job

Call `create_publishing_job` with:
- `name`: A descriptive name (e.g. `"Smart publish — en — [site name]"`)
- `source`: The site or source identifier
- `options`: The `xmc` options block built from the confirmed scope, locales, and flags
- `description`: Optional — include campaign or session context if available

On success, confirm:
> "Publishing job started — **[name]** (ID: `[id]`). Status: [status]. Publishing runs in the background — you'll be notified when it completes. Use "check publish status" to get an update at any time."

On failure, report the error in plain language and offer to retry.

### Step 5 — Handle job completion

Do NOT poll for completion. The system sends a notification when the job finishes. If the marketer asks for an update before notification, call `get_publishing_job` with the job ID.

---

## Failed Publish Jobs

When a job shows `status: "Failed"`:

1. Call `get_publishing_job` to retrieve full details and statistics.
2. Present the statistics and any error information.
3. Offer to retry by creating a new publishing job with the same options.

---

## Abandonment Handling

If the marketer stops responding mid-flow or says "cancel", "never mind", or "stop":
- Do not call `create_publishing_job`.
- Confirm: "No publish job was created."
