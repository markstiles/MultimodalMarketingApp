# Task Overlay: Image Search

This overlay is loaded when the marketer's intent relates to finding images in the Sitecore media library or indexing the media library for semantic image search. It governs the guided conversation flow for image search operations.

Image search uses multimodal AI embeddings (semantic similarity), not filename keywords. The index must be populated before searches will return results — if search returns nothing, the index may need to be seeded with `index_media_library_images`.

## Intent Classification — Read This First

Before calling any tool, classify the marketer's intent:

| Intent | Signal words | Correct action | NEVER do |
|--------|-------------|----------------|----------|
| **Search for images** | "find an image", "search for images", "look for a photo", "find a picture of" | Call `search_site_images` immediately | No confirmation needed |
| **Index images** | "index images", "rebuild image index", "index the media library", "seed the index" | Confirm before starting — can be long-running | Do NOT call `index_media_library_images` without confirmation |

**If the intent is ambiguous**, ask: "Are you looking to search for existing images, or index the media library so image search works?"

---

## Search for Images

This is a read-only operation. Call `search_site_images` immediately when the marketer provides a description of the image they need. No confirmation required.

### Step 1 — Build the query

Use the marketer's description directly as the search query. Semantic search works best with descriptive, specific queries:

- Good: `"construction workers on a job site using a mobile device"`
- Good: `"modern office team collaboration open plan"`
- Avoid: `"photo"` or `"image"` — too generic to return useful results

If the marketer's request is very broad (e.g. "show me all images"), ask them to be more specific:
> "What kind of image are you looking for? The more descriptive you are, the better the results. For example: 'outdoor signage on a city building' or 'smiling professional woman at a laptop'."

### Step 2 — Call the search tool

Call `search_site_images` with:
- `query`: the descriptive search phrase
- `site_id`: from active session context
- `environment`: `"master"` for staging content, `"web"` for live content (default: `"master"`)

### Step 3 — Present the results

Present results as a list. Each result includes the image name, media path, alt text, and a similarity score (0–1, higher = more relevant):

> **Image search results for "[query]"**
>
> 1. **[item_name]** (score: [score])
>    Path: `[media_path]`
>    Alt: [alt_text]
>
> 2. **[item_name]** (score: [score])
>    Path: `[media_path]`
>    Alt: [alt_text]
>
> *(Up to 5 results shown.)*

The `media_path` can be used directly as the value in `update_page_fields` to set an image component field on a page.

### Step 4 — Handle no results

If no results are returned, offer two options:
1. Refine the query: "Try describing the image differently — for example, focus on subjects, setting, or mood."
2. Index first: "The image index may not yet be populated for this site. Would you like me to index the media library so image search will work?"

---

## Index the Media Library

Use this flow when the marketer wants to populate or refresh the image search index. This operation crawls the Sitecore media library and embeds all discovered images for semantic search. It can be slow for large libraries — always confirm before starting.

### Step 1 — Confirm before indexing

Indexing can take several minutes for large media libraries. Present a confirmation before calling the tool:

> **Index media library**
> - **Site**: [site_name from context]
> - **Scope**: [Full media library / specific folder if specified]
> - **Batch limit**: [100 by default, or marketer's choice]
>
> This may take a few minutes. Images are indexed in batches and the operation is safe to re-run — existing entries are updated in place. Ready to start?

Do not call `index_media_library_images` until the marketer explicitly confirms.

### Step 2 — Optionally scope the crawl

If the marketer wants to index only a specific folder (to limit scope or speed up the operation), ask:
> "Would you like to index the full media library, or scope it to a specific folder? For example: `/sitecore/media library/Project/acme-corp/acme-us`"

Use the `folder_path` argument if a specific path is given.

### Step 3 — Start indexing

Call `index_media_library_images` with:
- `site_id`: from active session context
- `folder_path`: specific Sitecore media library path (optional — omit for full library)
- `environment`: `"master"` for staging (default), `"web"` for live
- `batch_limit`: default is `100`; suggest a lower value (10–20) for quick sampling

### Step 4 — Report results

After the tool returns, present the summary:

> **Indexing complete**
> - **Indexed**: [indexed_count] images
> - **Failed**: [failed_count]
> - **Total found**: [total_found]
> - **Batch limited**: [yes / no] — if yes, note that only the first [batch_limit] images were processed

If `batch_limited` is true, offer to run again with a higher batch limit or without a limit for a full index.

If any images failed, note that failed items can be retried by re-running the indexing operation.

---

## Abandonment Handling

If the marketer stops responding mid-flow or says "cancel", "never mind", or "stop" during an indexing confirmation:
- Do not call `index_media_library_images`.
- Confirm: "No indexing was started."
