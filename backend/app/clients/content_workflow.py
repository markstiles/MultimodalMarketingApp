import asyncio
import logging
import re

from langchain_core.tools import tool

from app.services.content_workflow_service import (
    CONTENT_STRATEGY_FOLDER,
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
from app.services.sites_service import get_site_info

logger = logging.getLogger(__name__)


def _parse_markdown_sections(text: str) -> list[dict]:
    """Convert a markdown string into the sections list expected by generate_phase_docx.

    ## headings become section headings; ### become subsections.
    # headings (document title level) are ignored — the title is passed separately.
    Text before the first heading is collected as an intro section.
    """
    sections: list[dict] = []
    current_section: dict | None = None
    current_sub: dict | None = None
    buf: list[str] = []

    def _flush() -> str:
        content = "\n".join(buf).strip()
        buf.clear()
        return content

    for line in text.splitlines():
        if re.match(r"^#\s", line):          # h1 — title level, skip
            _flush()
        elif re.match(r"^##\s", line):        # h2 — section
            if current_sub is not None:
                current_sub["content"] = _flush()
                current_sub = None
            elif current_section is not None:
                current_section["content"] = _flush()
            else:
                orphan = _flush()
                if orphan:
                    sections.append({"heading": "", "content": orphan, "subsections": []})
            heading = re.sub(r"^##\s+", "", line).strip()
            current_section = {"heading": heading, "content": "", "subsections": []}
            sections.append(current_section)
        elif re.match(r"^###\s", line):       # h3 — subsection
            if current_sub is not None:
                current_sub["content"] = _flush()
            elif current_section is not None:
                current_section["content"] = _flush()
            else:
                orphan = _flush()
                if orphan:
                    sections.append({"heading": "", "content": orphan, "subsections": []})
            heading = re.sub(r"^###\s+", "", line).strip()
            current_sub = {"heading": heading, "content": ""}
            if current_section is None:
                current_section = {"heading": "", "content": "", "subsections": []}
                sections.append(current_section)
            current_section["subsections"].append(current_sub)
        else:
            buf.append(line)

    tail = _flush()
    if current_sub is not None:
        current_sub["content"] = tail
    elif current_section is not None:
        current_section["content"] = tail
    elif tail:
        sections.append({"heading": "", "content": tail, "subsections": []})

    return sections


@tool
async def scan_content_project_status(site_id: str) -> dict:
    """
    Scan all five marketing pipeline phase folders in the Sitecore media library and
    return the current project state for the given site. Call this at the start of
    every marketing pipeline session to detect existing artifacts and determine the
    next recommended phase.

    The site's collection (organization grouping) is resolved automatically from the
    Sites API — you only need to pass the site_id from session context.

    Args:
        site_id: Site identifier from active session context

    Returns MarketingProjectSummary including phase statuses, staleness flags, and
    the recommended next phase. Phases: Research, Strategy, BrandVoice, Brief, Campaign.
    """
    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "phases": []}

    site_info = await get_site_info(site_id, auth_token)
    if not site_info.get("success"):
        return {
            "success": False,
            "error": site_info.get("error", "Failed to resolve site context"),
            "phases": [],
        }

    collection = site_info["collection"]
    site_name = site_info["name"]

    checks = await asyncio.gather(
        *[
            check_media_artifact_exists(collection, site_name, phase, auth_token)
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
        media_path = build_artifact_media_path(collection, site_name, phase)

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
                "folder_name": CONTENT_STRATEGY_FOLDER,
                "canonical_filename": info["filename"],
                "media_path": media_path,
                "status": status,
                "modified_at": modified_at,
                "age_days": age_days,
            }
        )

    return {
        "site_id": site_id,
        "collection": collection,
        "site_name": site_name,
        "phases": phases,
        "last_completed_phase": last_completed_phase,
        "next_recommended_phase": next_recommended_phase,
        "has_stale_phases": bool(stale_phase_names),
        "stale_phase_names": stale_phase_names,
    }


@tool
async def save_phase_artifact(
    site_id: str,
    phase: str,
    title: str,
    content: str,
) -> dict:
    """
    Save the approved phase document to the Sitecore media library.

    Call this once the marketer has approved the content for the current phase.
    Pass the full document body as markdown — sections (##), subsections (###),
    and body text are converted to a Word document automatically.

    The site's collection is resolved automatically — you only need site_id.

    Args:
        site_id: Site identifier from active session context
        phase: One of: Research, Strategy, BrandVoice, Brief, Campaign
        title: Document title (e.g. "Research Brief — Acme Corp / US Site")
        content: Full document body as markdown

    Returns success status and media library path. On failure the error field
    describes what went wrong.
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

    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
            "phase": phase,
            "media_path": None,
            "filename": PHASE_ARTIFACT_MAP[phase]["filename"],
            "overwrite": False,
        }

    site_info = await get_site_info(site_id, auth_token)
    if not site_info.get("success"):
        return {
            "success": False,
            "error": site_info.get("error", "Failed to resolve site context"),
            "phase": phase,
            "media_path": None,
            "filename": PHASE_ARTIFACT_MAP[phase]["filename"],
            "overwrite": False,
        }

    collection = site_info["collection"]
    site_name = site_info["name"]
    info = PHASE_ARTIFACT_MAP[phase]
    media_path = build_artifact_media_path(collection, site_name, phase)

    sections = _parse_markdown_sections(content)
    try:
        docx_bytes = generate_phase_docx(phase, title, collection, site_name, sections)
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

    result = await upload_artifact_to_media_library(
        collection, site_name, phase, docx_bytes, auth_token
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
async def get_phase_artifact_content(site_id: str, phase: str) -> dict:
    """
    Retrieve the text content of an existing phase artifact from the Sitecore media
    library. Use this to inject prior phase findings into context at the start of
    downstream phases so the marketer does not need to re-enter information already
    captured.

    The site's collection is resolved automatically — you only need site_id.

    Args:
        site_id: Site identifier from active session context
        phase: One of: Research, Strategy, BrandVoice, Brief, Campaign

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

    try:
        auth_token = await get_sitecore_media_auth_token()
    except RuntimeError as exc:
        return {
            "success": False,
            "phase": phase,
            "media_path": None,
            "text_content": None,
            "modified_at": None,
            "error": str(exc),
        }

    site_info = await get_site_info(site_id, auth_token)
    if not site_info.get("success"):
        return {
            "success": False,
            "phase": phase,
            "media_path": None,
            "text_content": None,
            "modified_at": None,
            "error": site_info.get("error", "Failed to resolve site context"),
        }

    collection = site_info["collection"]
    site_name = site_info["name"]
    media_path = build_artifact_media_path(collection, site_name, phase)

    check = await check_media_artifact_exists(collection, site_name, phase, auth_token)
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
