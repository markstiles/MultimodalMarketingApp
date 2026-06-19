import asyncio
import logging

from langchain_core.tools import tool

from app.services.content_workflow_service import (
    PHASE_ARTIFACT_MAP,
    PHASES_ORDERED,
    STALENESS_DAYS,
    build_artifact_media_path,
    check_media_artifact_exists,
    download_and_extract_artifact,
    generate_phase_docx,
    get_sitecore_media_auth_token,
    upload_artifact_to_media_library,
)

logger = logging.getLogger(__name__)


@tool
async def scan_content_project_status(tenant: str, site: str) -> dict:
    """
    Scan all six phase folders in the Sitecore media library and return the current
    content project state for the given site. Call this at the start of any content
    development session to detect existing artifacts and determine the next recommended phase.

    Args:
        tenant: Tenant name from active session context (e.g. "acme-corp")
        site: Site name from active session context (e.g. "us-site")

    Returns ContentProjectSummary including phase statuses, staleness flags, and
    the recommended next phase.
    """
    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "phases": []}

    checks = await asyncio.gather(
        *[
            check_media_artifact_exists(tenant, site, phase, auth_token)
            for phase in PHASES_ORDERED
        ],
        return_exceptions=True,
    )

    phases = []
    last_completed_phase: str | None = None
    next_recommended_phase: str | None = None
    stale_phase_names: list[str] = []

    for phase, result in zip(PHASES_ORDERED, checks):
        info = PHASE_ARTIFACT_MAP[phase]
        media_path = build_artifact_media_path(tenant, site, phase)

        if isinstance(result, Exception):
            logger.warning("Phase %s check failed: %s", phase, result)
            result = {"exists": False, "modified_at": None, "age_days": None}

        exists: bool = result["exists"]
        modified_at: str | None = result["modified_at"]
        age_days: int | None = result["age_days"]

        if not exists:
            status = "not_started"
        elif age_days is not None and age_days > STALENESS_DAYS:
            status = "stale"
            stale_phase_names.append(phase)
            last_completed_phase = phase
        else:
            status = "complete"
            last_completed_phase = phase

        if next_recommended_phase is None and not exists:
            next_recommended_phase = phase

        phases.append(
            {
                "phase": phase,
                "folder_name": info["folder"],
                "canonical_filename": info["filename"],
                "media_path": media_path,
                "status": status,
                "modified_at": modified_at,
                "age_days": age_days,
            }
        )

    return {
        "tenant": tenant,
        "site": site,
        "phases": phases,
        "last_completed_phase": last_completed_phase,
        "next_recommended_phase": next_recommended_phase,
        "has_stale_phases": bool(stale_phase_names),
        "stale_phase_names": stale_phase_names,
    }


@tool
async def save_phase_artifact(
    tenant: str,
    site: str,
    phase: str,
    title: str,
    sections: list[dict],
) -> dict:
    """
    Generate a Word document (.docx) from the provided structured content and save it
    to the canonical Sitecore media library path for the specified phase. ONLY call this
    tool after the marketer has explicitly approved the artifact.

    Args:
        tenant: Tenant name from active session context
        site: Site name from active session context
        phase: One of: Research, Strategy, Structure, Content, Variation, Execution
        title: Document title (e.g. "Research Brief — Acme Corp / US Site")
        sections: List of dicts with keys: heading (str), content (str),
                  subsections (list of {heading, content})

    Returns ArtifactSaveResult with success status and media library path.
    """
    if phase not in PHASE_ARTIFACT_MAP:
        valid = ", ".join(PHASES_ORDERED)
        return {
            "success": False,
            "error": f"Unknown phase: {phase!r}. Must be one of: {valid}.",
            "phase": phase,
            "media_path": None,
            "filename": None,
            "overwrite": False,
        }

    info = PHASE_ARTIFACT_MAP[phase]
    media_path = build_artifact_media_path(tenant, site, phase)

    try:
        docx_bytes = generate_phase_docx(phase, title, tenant, site, sections)
    except Exception as exc:
        logger.error("Failed to generate .docx for phase %s: %s", phase, exc)
        return {
            "success": False,
            "error": f"Failed to generate document: {exc}",
            "phase": phase,
            "media_path": media_path,
            "filename": info["filename"],
            "overwrite": False,
        }

    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
            "phase": phase,
            "media_path": media_path,
            "filename": info["filename"],
            "overwrite": False,
        }

    result = await upload_artifact_to_media_library(
        tenant, site, phase, docx_bytes, auth_token
    )
    return {
        "success": result["success"],
        "phase": phase,
        "media_path": result.get("media_path", media_path),
        "filename": info["filename"],
        "overwrite": result.get("overwrite", False),
        "error": result.get("error"),
    }


@tool
async def get_phase_artifact_content(tenant: str, site: str, phase: str) -> dict:
    """
    Retrieve the text content of an existing phase artifact from the Sitecore media
    library. Use this to inject prior phase findings into context at the start of
    downstream phases so the marketer does not need to re-enter information already
    captured.

    Args:
        tenant: Tenant name from active session context
        site: Site name from active session context
        phase: One of: Research, Strategy, Structure, Content, Variation, Execution

    Returns ArtifactContentResult with extracted text content and modification date.
    """
    if phase not in PHASE_ARTIFACT_MAP:
        valid = ", ".join(PHASES_ORDERED)
        return {
            "success": False,
            "phase": phase,
            "media_path": None,
            "text_content": None,
            "modified_at": None,
            "error": f"Unknown phase: {phase!r}. Must be one of: {valid}.",
        }

    media_path = build_artifact_media_path(tenant, site, phase)

    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {
            "success": False,
            "phase": phase,
            "media_path": media_path,
            "text_content": None,
            "modified_at": None,
            "error": str(exc),
        }

    check = await check_media_artifact_exists(tenant, site, phase, auth_token)
    if not check["exists"]:
        return {
            "success": False,
            "phase": phase,
            "media_path": media_path,
            "text_content": None,
            "modified_at": None,
            "error": (
                f"No artifact found for phase '{phase}'. "
                "The phase may not be complete yet."
            ),
        }

    success, text_content, error = await download_and_extract_artifact(
        media_path, auth_token
    )
    return {
        "success": success,
        "phase": phase,
        "media_path": media_path,
        "text_content": text_content,
        "modified_at": check.get("modified_at"),
        "error": error,
    }
