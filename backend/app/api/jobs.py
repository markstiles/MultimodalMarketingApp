import logging

from fastapi import APIRouter, Request

from app.clients.auth_verifier import get_user_id
from app.services.sites_service import check_job_status
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jobs")
async def get_job_status(handle: str, request: Request) -> dict:
    """Return the current status of a Sitecore background job by handle."""
    await get_user_id(request)
    try:
        auth_token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "status": "Error"}
    return await check_job_status(handle, auth_token)
