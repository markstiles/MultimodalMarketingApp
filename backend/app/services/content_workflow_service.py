import io
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from docx import Document

from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)

# ── Phase artifact registry ──────────────────────────────────────────────────

PHASE_ARTIFACT_MAP: dict[str, dict[str, str]] = {
    "Research":  {"folder": "Research",  "filename": "research-brief.docx"},
    "Strategy":  {"folder": "Strategy",  "filename": "content-strategy.docx"},
    "Structure": {"folder": "Structure", "filename": "content-structure.docx"},
    "Content":   {"folder": "Content",   "filename": "content-plan.docx"},
    "Variation": {"folder": "Variation", "filename": "variation-plan.docx"},
    "Execution": {"folder": "Execution", "filename": "execution-checklist.docx"},
}

PHASES_ORDERED: list[str] = list(PHASE_ARTIFACT_MAP.keys())
STALENESS_DAYS = 365

# Sitecore template ID for media library folders
FOLDER_TEMPLATE_ID = "{FE5DD826-48C6-436D-B87A-7C4210C7413B}"


def build_artifact_media_path(tenant: str, site: str, phase: str) -> str:
    info = PHASE_ARTIFACT_MAP.get(phase)
    if not info:
        raise ValueError(f"Unknown phase: {phase!r}")
    return (
        f"/sitecore/Media Library/Project/{tenant}/{site}"
        f"/Content Strategy/{info['folder']}/{info['filename']}"
    )


# ── Auth ─────────────────────────────────────────────────────────────────────

# Alias for backward compatibility — callers in this module use the old name.
get_sitecore_media_auth_token = get_sitecore_automation_token


# ── Media library existence check ────────────────────────────────────────────

async def check_media_artifact_exists(
    tenant: str, site: str, phase: str, auth_token: str
) -> dict:
    media_path = build_artifact_media_path(tenant, site, phase)
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        logger.warning("SITECORE_CM_HOST not set — treating all phases as not_started")
        return {"exists": False, "modified_at": None, "age_days": None}

    url = f"{cm_host}/sitecore/api/ssc/item"
    params = {"database": "master", "path": media_path}

    try:
        async with httpx.AsyncClient(timeout=8) as http:
            resp = await http.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Media artifact check timed out for phase %s: %s", phase, exc)
        return {"exists": False, "modified_at": None, "age_days": None}

    if resp.status_code == 404:
        return {"exists": False, "modified_at": None, "age_days": None}

    if not resp.is_success:
        logger.warning("Media check returned %d for phase %s", resp.status_code, phase)
        return {"exists": False, "modified_at": None, "age_days": None}

    data = resp.json()
    raw = data.get("__Updated") or data.get("Updated") or data.get("updated")

    modified_at: str | None = None
    age_days: int | None = None
    if raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            modified_at = dt.isoformat()
            age_days = (datetime.now(timezone.utc) - dt).days
        except ValueError:
            pass

    return {"exists": True, "modified_at": modified_at, "age_days": age_days}


# ── Word document generation ──────────────────────────────────────────────────

def generate_phase_docx(
    phase: str,
    title: str,
    tenant: str,
    site: str,
    sections: list[dict],
) -> bytes:
    doc = Document()
    doc.add_heading(title, level=1)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = doc.add_paragraph()
    meta.add_run(
        f"Phase: {phase}  |  Site: {tenant} / {site}  |  Generated: {now_str}"
    ).italic = True
    doc.add_paragraph()

    for section in sections:
        heading = section.get("heading", "")
        content = section.get("content", "")
        subsections = section.get("subsections", [])

        if heading:
            doc.add_heading(heading, level=2)
        for line in (content or "").split("\n"):
            if line.strip():
                doc.add_paragraph(line.strip())
        for sub in subsections:
            if sub.get("heading"):
                doc.add_heading(sub["heading"], level=3)
            for line in (sub.get("content") or "").split("\n"):
                if line.strip():
                    doc.add_paragraph(line.strip())

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Media folder management ───────────────────────────────────────────────────

async def _ssc_item_exists(cm_host: str, path: str, auth_token: str) -> bool:
    """Return True if a Sitecore item exists at *path* (SSC API HEAD/GET)."""
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            resp = await http.get(
                f"{cm_host}/sitecore/api/ssc/item",
                params={"database": "master", "path": path},
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        return resp.status_code == 200
    except Exception:
        return False


async def _create_media_folder(
    cm_host: str, parent_path: str, folder_name: str, auth_token: str
) -> bool:
    """Create a media-library folder via the GraphQL authoring API."""
    mutation = """
mutation CreateMediaFolder($input: CreateItemInput!) {
  createItem(input: $input) {
    item { itemId path }
  }
}
"""
    variables = {
        "input": {
            "name": folder_name,
            "templateId": FOLDER_TEMPLATE_ID,
            "parent": parent_path,
            "language": "en",
        }
    }
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{cm_host}/sitecore/api/authoring/graphql/v1",
                json={"query": mutation, "variables": variables},
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json",
                },
            )
        if resp.is_success:
            data = resp.json()
            if not data.get("errors"):
                item = (data.get("data") or {}).get("createItem", {}).get("item")
                logger.info("Created media folder: %s", (item or {}).get("path", folder_name))
                return True
            logger.warning("GraphQL createItem errors for %s/%s: %s", parent_path, folder_name, data["errors"])
        else:
            logger.warning(
                "GraphQL createItem HTTP %d for %s/%s: %s",
                resp.status_code, parent_path, folder_name, resp.text[:300],
            )
    except Exception as exc:
        logger.warning("GraphQL createItem exception for %s/%s: %s", parent_path, folder_name, exc)
    return False


async def ensure_phase_upload_folders(
    tenant: str, site: str, phase: str, auth_token: str
) -> None:
    """Ensure the Content Strategy folder and per-phase subfolder exist in the media library.

    The site folder (/sitecore/Media Library/Project/{tenant}/{site}) is assumed to exist.
    Creates any missing ancestors using the media-folder template via GraphQL authoring API.
    Failures are logged but never raise — callers should still attempt the upload.
    """
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        return

    info = PHASE_ARTIFACT_MAP.get(phase)
    if not info:
        return

    site_path = f"/sitecore/Media Library/Project/{tenant}/{site}"
    cs_path = f"{site_path}/Content Strategy"
    phase_path = f"{cs_path}/{info['folder']}"

    if not await _ssc_item_exists(cm_host, cs_path, auth_token):
        logger.info("Creating 'Content Strategy' folder under %s", site_path)
        await _create_media_folder(cm_host, site_path, "Content Strategy", auth_token)

    if not await _ssc_item_exists(cm_host, phase_path, auth_token):
        logger.info("Creating '%s' folder under Content Strategy", info["folder"])
        await _create_media_folder(cm_host, cs_path, info["folder"], auth_token)


# ── Media library upload ──────────────────────────────────────────────────────

async def upload_artifact_to_media_library(
    tenant: str,
    site: str,
    phase: str,
    docx_bytes: bytes,
    auth_token: str,
) -> dict:
    info = PHASE_ARTIFACT_MAP.get(phase)
    if not info:
        return {
            "success": False,
            "error": f"Unknown phase: {phase!r}",
            "media_path": None,
            "overwrite": False,
        }

    media_path = build_artifact_media_path(tenant, site, phase)
    agents_base = os.environ.get(
        "SITECORE_AGENTS_API_BASE_URL",
        "https://edge-platform.sitecorecloud.io/stream/ai-agent-api",
    ).rstrip("/")
    upload_url = f"{agents_base}/api/v1/assets/upload"

    overwrite = False
    try:
        check = await check_media_artifact_exists(tenant, site, phase, auth_token)
        overwrite = check["exists"]
    except Exception:
        pass

    # Create Content Strategy and phase folders if they don't exist yet.
    try:
        await ensure_phase_upload_folders(tenant, site, phase, auth_token)
    except Exception as exc:
        logger.warning("Folder pre-creation failed (upload may still succeed): %s", exc)

    folder_path = (
        f"/sitecore/Media Library/Project/{tenant}/{site}"
        f"/Content Strategy/{info['folder']}"
    )

    # Sitecore item names don't include the extension — the extension field covers that.
    asset_name = info["filename"].rsplit(".", 1)[0]  # "research-brief.docx" → "research-brief"

    # Agent API validates siteName against registered Sitecore sites. Use the
    # configured default site name (SITECORE_PUBLIC_DEFAULT_SITE_NAME) when available;
    # the tool's `site` context value is a page-context ID that may not match the
    # Sitecore site name/handle required by the API.
    site_name_for_api = os.environ.get("SITECORE_PUBLIC_DEFAULT_SITE_NAME") or site

    upload_request = json.dumps({
        "name": asset_name,
        "itemPath": folder_path,
        "language": "en",
        "extension": "docx",
        "siteName": site_name_for_api,
    })

    logger.info(
        "Media upload → url=%s filename=%s upload_request=%s",
        upload_url, info["filename"], upload_request,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                upload_url,
                headers={"Authorization": f"Bearer {auth_token}"},
                files={
                    "file": (
                        info["filename"],
                        docx_bytes,
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document",
                    ),
                    "upload_request": (None, upload_request),
                },
            )
        if not resp.is_success:
            full_body = resp.text
            logger.error(
                "Media upload failed: %d | url=%s | body=%s",
                resp.status_code, upload_url, full_body,
            )
            # The Agent API upload endpoint has a confirmed server-side bug where
            # upload_request is never parsed from multipart bodies (HTTP 400 "Field
            # required"). Surface a clean message for this known case so the LLM
            # can handle it gracefully without alarming the user.
            known_api_bug = (
                resp.status_code == 400
                and "upload_request" in full_body
                and "Field required" in full_body
            )
            if known_api_bug:
                user_msg = (
                    "The document was generated successfully but could not be saved to "
                    "the Sitecore media library (upload API unavailable). "
                    "The artifact content is available in this conversation."
                )
                return {
                    "success": False,
                    "docx_generated": True,
                    "upload_unavailable": True,
                    "error": user_msg,
                    "media_path": media_path,
                    "overwrite": overwrite,
                }
            return {
                "success": False,
                "error": f"Media library upload failed: HTTP {resp.status_code} — {full_body[:2000]}",
                "media_path": media_path,
                "overwrite": overwrite,
            }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Media library upload timed out after 30 seconds",
            "media_path": media_path,
            "overwrite": overwrite,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Media library upload failed: {exc}",
            "media_path": media_path,
            "overwrite": overwrite,
        }

    logger.info("Uploaded %s to %s (overwrite=%s)", info["filename"], media_path, overwrite)
    return {"success": True, "media_path": media_path, "overwrite": overwrite, "error": None}


# ── Artifact text extraction ──────────────────────────────────────────────────

async def download_and_extract_artifact(
    media_path: str, auth_token: str
) -> tuple[bool, str | None, str | None]:
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        return False, None, "SITECORE_CM_HOST not configured"

    # Convert media library path to HTTP download URL
    # e.g. /sitecore/media library/Project/... → /-/media/Project/...
    relative = media_path.replace("/sitecore/media library", "").lstrip("/")
    url = f"{cm_host}/-/media/{relative}"

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(url, headers={"Authorization": f"Bearer {auth_token}"})
        if resp.status_code == 404:
            return False, None, "Artifact not found at media library path"
        if not resp.is_success:
            return False, None, f"Failed to download artifact: HTTP {resp.status_code}"
        docx_bytes = resp.content
    except httpx.TimeoutException:
        return False, None, "Download timed out"
    except Exception as exc:
        return False, None, f"Download failed: {exc}"

    try:
        doc = Document(io.BytesIO(docx_bytes))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return True, text, None
    except Exception as exc:
        return False, None, f"Failed to extract text from document: {exc}"
