import logging

from langchain_core.tools import tool

from app.services.publishing_service import (
    create_publishing_job as _create_publishing_job,
    get_publishing_job as _get_publishing_job,
    get_publishing_summary as _get_publishing_summary,
    list_publishing_jobs as _list_publishing_jobs,
)
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


@tool
async def publish_content(
    name: str,
    source: str,
    locales: list[str],
    items: list[dict] | None = None,
    mode: str = "Smart",
    description: str = "",
) -> dict:
    """Publish content to the Sitecore Edge delivery layer.

    ONLY call this tool after the marketer has explicitly approved the publishing plan.

    Args:
        name:        Display name for the job (e.g. "Publish Homepage update")
        source:      Publishing source identifier (usually the site name or environment key)
        locales:     Language codes to publish, e.g. ["en"] or ["en", "fr-CA"]
        items:       Specific items to publish — each: {"id": "<item-id>", "type": "Item"}.
                     Omit or pass [] to publish by site-wide mode only.
        mode:        "Smart" (default — only changed items), "Incremental", or "Republish"
        description: Optional description for the job

    Returns {success, id, name, source, status} on success or {success, error} on failure.
    """
    auth_token = await get_sitecore_automation_token()
    options: dict = {
        "xmc": {
            "locales": locales,
            "site": {"mode": mode},
            "items": {"mode": mode, "publishRelatedItems": False, "publishChildren": False},
        }
    }
    if items:
        options["items"] = items
    return await _create_publishing_job(
        name=name,
        source=source,
        options=options,
        auth_token=auth_token,
        description=description,
    )


@tool
async def get_publishing_job(job_id: str) -> dict:
    """Retrieve the status and statistics of a publishing job by its ID.

    Use this to check whether a publish has completed, failed, or is still running.
    Possible status values: Queued, Running, Completed, Failed, Canceled, Canceling.

    Returns {success, id, name, source, status, queued_time, start_time, finish_time, statistics}.
    """
    auth_token = await get_sitecore_automation_token()
    return await _get_publishing_job(job_id=job_id, auth_token=auth_token)


@tool
async def list_publishing_jobs(
    source: str = "",
    status: str = "",
    page_size: int = 20,
) -> dict:
    """List recent publishing jobs, optionally filtered by source or status.

    Args:
        source:    Filter by publishing source (optional — leave empty for all sources)
        status:    Filter by status: "Queued", "Running", "Completed", "Failed",
                   "Canceled", or "Canceling" (optional)
        page_size: Results to return (default 20, max 100)

    Returns {success, jobs, total_count} where each job has {id, name, source, status, queued_time}.
    """
    auth_token = await get_sitecore_automation_token()
    return await _list_publishing_jobs(
        auth_token=auth_token,
        source=source,
        status=status,
        page_size=page_size,
    )


@tool
async def get_publishing_summary() -> dict:
    """Get a count of publishing jobs grouped by status — a quick queue health snapshot.

    Call this before proposing a publish to show whether the queue is idle or backed up.

    Returns {success, queued, running, canceled, failed, completed, canceling}.
    """
    auth_token = await get_sitecore_automation_token()
    return await _get_publishing_summary(auth_token=auth_token)
