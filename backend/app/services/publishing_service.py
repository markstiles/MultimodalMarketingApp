import logging
import os

import httpx

from app.services._api_endpoint import api_endpoint

logger = logging.getLogger(__name__)

_BASE_URL = "https://edge-platform.sitecorecloud.io/authoring/publishing/v1"


def _get_base_url() -> str:
    return os.environ.get("SITECORE_PUBLISHING_API_BASE_URL", _BASE_URL).rstrip("/")


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@api_endpoint(exposed=True, category="publishing")
async def create_publishing_job(
    name: str,
    source: str,
    options: dict,
    auth_token: str,
    description: str = "",
) -> dict:
    """Create a publishing job via POST /authoring/publishing/v1/jobs.

    Args:
        name:        Display name for the job (max 256 chars)
        source:      Publishing source identifier (max 256 chars)
        options:     PublishOptionsModel dict. Structure:
                     {
                       "items": [{"id": "<item-id>", "type": "<type>", "locale": "<optional>"}],
                       "xmc": {
                         "locales": ["en"],
                         "site": {"mode": "Republish|Incremental|Smart"},
                         "items": {
                           "mode": "Republish|Smart",
                           "publishRelatedItems": false,
                           "publishChildren": false
                         }
                       }
                     }
        description: Optional description (max 256 chars)

    Returns {success, id, name, source, status} on success or {success, error} on failure.
    """
    url = f"{_get_base_url()}/jobs"
    body: dict = {"name": name, "source": source, "options": options}
    if description:
        body["description"] = description
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(url, json=body, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "create_publishing_job HTTP %d (body=%s): %s",
            exc.response.status_code, body, exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("create_publishing_job error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "id": data.get("id", ""),
        "name": data.get("name", name),
        "source": data.get("source", source),
        "status": data.get("system", {}).get("status", ""),
    }


@api_endpoint(exposed=True, category="publishing")
async def get_publishing_job(job_id: str, auth_token: str) -> dict:
    """Retrieve a publishing job by ID via GET /authoring/publishing/v1/jobs/{id}.

    Returns {success, id, name, source, status, statistics} on success.
    """
    url = f"{_get_base_url()}/jobs/{job_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, headers=_auth_headers(auth_token))
        if resp.status_code == 404:
            return {"success": False, "error": f"Publishing job not found: {job_id!r}"}
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_publishing_job HTTP %d (id=%s): %s", exc.response.status_code, job_id, exc.response.text)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("get_publishing_job error: %s", exc)
        return {"success": False, "error": str(exc)}

    system = data.get("system", {})
    return {
        "success": True,
        "id": data.get("id", job_id),
        "name": data.get("name", ""),
        "source": data.get("source", ""),
        "status": system.get("status", ""),
        "queued_time": system.get("queuedTime", ""),
        "start_time": system.get("startTime", ""),
        "finish_time": system.get("finishTime", ""),
        "statistics": data.get("statistics", {}),
    }


@api_endpoint(exposed=True, category="publishing")
async def list_publishing_jobs(
    auth_token: str,
    source: str = "",
    status: str = "",
    page_size: int = 20,
    page_number: int = 1,
) -> dict:
    """List publishing jobs via GET /authoring/publishing/v1/jobs.

    Args:
        source:      Filter by publishing source (optional)
        status:      Filter by status — e.g. "Queued", "Running", "Completed",
                     "Failed", "Canceled", "Canceling" (optional)
        page_size:   Number of results per page (max 100, default 20)
        page_number: 1-based page number for offset pagination (default 1)

    Returns {success, jobs, total_count} on success.
    """
    url = f"{_get_base_url()}/jobs"
    params: dict = {"pageSize": page_size, "pageNumber": page_number}
    if source:
        params["source"] = source
    if status:
        params["system.status"] = status
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, params=params, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("list_publishing_jobs HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "jobs": [], "error": str(exc)}
    except Exception as exc:
        logger.error("list_publishing_jobs error: %s", exc)
        return {"success": False, "jobs": [], "error": str(exc)}

    raw = data if isinstance(data, list) else data.get("data") or data.get("items") or []
    jobs = [
        {
            "id": j.get("id", ""),
            "name": j.get("name", ""),
            "source": j.get("source", ""),
            "status": j.get("system", {}).get("status", ""),
            "queued_time": j.get("system", {}).get("queuedTime", ""),
        }
        for j in (raw if isinstance(raw, list) else [])
    ]
    total = data.get("totalCount", len(jobs)) if isinstance(data, dict) else len(jobs)
    return {"success": True, "jobs": jobs, "total_count": total}


@api_endpoint(exposed=False, category="publishing")
async def cancel_publishing_job(job_id: str, auth_token: str) -> dict:
    """Cancel a running publishing job via POST /authoring/publishing/v1/jobs/{jobId}/cancel.

    Returns {success, job_id} on success or {success, error} on failure.
    """
    url = f"{_get_base_url()}/jobs/{job_id}/cancel"
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(url, headers=_auth_headers(auth_token))
        if resp.status_code == 404:
            return {"success": False, "error": f"Publishing job not found: {job_id!r}"}
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "cancel_publishing_job HTTP %d (id=%s): %s",
            exc.response.status_code, job_id, exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("cancel_publishing_job error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {"success": True, "job_id": job_id}


@api_endpoint(exposed=True, category="publishing")
async def get_publishing_summary(auth_token: str) -> dict:
    """Retrieve a summary of publishing job counts by status.

    Returns {success, queued, running, canceled, failed, completed, canceling}.
    """
    url = f"{_get_base_url()}/jobs/summary"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_publishing_summary HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("get_publishing_summary error: %s", exc)
        return {"success": False, "error": str(exc)}

    counts = data.get("counts", data)
    return {
        "success": True,
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "canceled": counts.get("canceled", 0),
        "failed": counts.get("failed", 0),
        "completed": counts.get("completed", 0),
        "canceling": counts.get("canceling", 0),
    }


@api_endpoint(exposed=False, category="publishing")
async def get_publishing_permissions(auth_token: str) -> dict:
    """Retrieve the current user's publishing permissions.

    Returns {success, can_read_all, can_create, ...} on success.
    """
    url = f"{_get_base_url()}/jobs/permissions"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_publishing_permissions HTTP %d: %s", exc.response.status_code, exc.response.text)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("get_publishing_permissions error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "can_read_all": data.get("canReadAll", False),
        "can_read_own": data.get("canReadOwn", False),
        "can_view_details_of_all": data.get("canViewDetailsOfAll", False),
        "can_view_details_of_own": data.get("canViewDetailsOfOwn", False),
        "can_create": data.get("canCreate", False),
    }
