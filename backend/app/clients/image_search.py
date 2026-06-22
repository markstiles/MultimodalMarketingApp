"""Image search tools — semantic search over Sitecore media library images.

Requires the image_embeddings table (pgvector) to be populated before search
will return results. Use index_media_library_images first to seed the index,
or rely on the Sitecore webhook integration (spec 008) for ongoing updates.
"""
import logging

from langchain_core.tools import tool

from app.services.sitecore_auth import get_sitecore_automation_token
from app.services.sites_service import get_site_info

logger = logging.getLogger(__name__)


@tool
async def search_site_images(query: str, site_id: str, environment: str = "master") -> dict:
    """
    Search the Sitecore media library for images matching a natural-language description.

    Uses multimodal AI embeddings (Cohere) to find images by semantic similarity,
    not just filename keywords. Works best with descriptive queries like
    "construction workers on a job site using a mobile device" rather than
    generic terms like "photo".

    The search is scoped to the current site so results are relevant to the campaign.
    Returns up to 5 ranked results with Sitecore media paths that can be used
    directly in update_page_fields to set image component fields.

    If no results are returned, the image index may not yet be populated —
    use index_media_library_images to seed it first.

    Args:
        query:       Natural-language description of the image to find
                     (e.g. "modern office team collaboration", "outdoor signage on building")
        site_id:     Site identifier from session context
        environment: Sitecore environment ("master" for staging, "web" for live)

    Returns {success, query, results: [{item_id, item_name, media_path, alt_text, score}], count}.
    score is cosine similarity (0–1, higher = more relevant).
    media_path can be used as the value in update_page_fields for image fields.
    """
    from app.resources.database import _get_session_factory
    from app.services.image_search_service import search_images

    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "query": query}

    site_info = await get_site_info(site_id, auth_token)
    if not site_info.get("success"):
        return {
            "success": False,
            "error": site_info.get("error", "Could not resolve site"),
            "query": query,
        }

    collection = site_info["collection"]

    async with _get_session_factory()() as db:
        return await search_images(
            query=query,
            site_id=site_id,
            collection=collection,
            environment=environment,
            db=db,
        )


@tool
async def index_media_library_images(
    site_id: str,
    folder_path: str | None = None,
    environment: str = "master",
    batch_limit: int = 100,
) -> dict:
    """
    Crawl and index images from the Sitecore media library for semantic search.

    Queries the Sitecore CM GraphQL API for image items, embeds each one with
    Cohere multimodal embeddings, and stores the vectors in the pgvector database.
    Must be run before search_site_images will return results.

    This operation is safe to re-run — existing images are updated in place
    (upsert semantics). Limit batch processing with batch_limit to avoid
    long-running operations during chat sessions; run without limit for full
    initial indexing.

    Args:
        site_id:     Site identifier from session context
        folder_path: Optional Sitecore media library path to scope the crawl
                     (e.g. "/sitecore/media library/Project/acme-corp/acme-us").
                     Defaults to the full media library.
        environment: Sitecore environment to tag embeddings against ("master" or "web")
        batch_limit: Maximum number of images to process per call (default 100).
                     Use a lower value (10–20) for quick sampling.

    Returns {success, indexed_count, failed_count, total_found, batch_limited}.
    """
    from app.resources.database import _get_session_factory
    from app.services.image_search_service import crawl_and_index_media_library

    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    site_info = await get_site_info(site_id, auth_token)
    if not site_info.get("success"):
        return {"success": False, "error": site_info.get("error", "Could not resolve site")}

    collection = site_info["collection"]

    async with _get_session_factory()() as db:
        return await crawl_and_index_media_library(
            site_id=site_id,
            collection=collection,
            environment=environment,
            folder_path=folder_path,
            auth_token=auth_token,
            db=db,
            batch_limit=batch_limit,
        )
