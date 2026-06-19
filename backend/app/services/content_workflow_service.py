import io
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from docx import Document

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


def build_artifact_media_path(tenant: str, site: str, phase: str) -> str:
    info = PHASE_ARTIFACT_MAP.get(phase)
    if not info:
        raise ValueError(f"Unknown phase: {phase!r}")
    return (
        f"/sitecore/media library/Project/{tenant}/{site}"
        f"/Content Strategy/{info['folder']}/{info['filename']}"
    )


# ── Auth ─────────────────────────────────────────────────────────────────────

_token_cache: dict[str, Any] = {}


async def get_sitecore_media_auth_token() -> str:
    now = time.monotonic()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    client_id = (
        os.environ.get("SITECORE_CLIENT_ID_AUTOMATION")
        or os.environ.get("AUTHOR_APP_ID", "")
    )
    client_secret = (
        os.environ.get("SITECORE_CLIENT_SECRET_AUTOMATION")
        or os.environ.get("AUTHOR_APP_CLIENT_CREDENTIALS", "")
    )
    if not client_id or not client_secret:
        raise RuntimeError(
            "Sitecore media credentials missing — set SITECORE_CLIENT_ID_AUTOMATION "
            "and SITECORE_CLIENT_SECRET_AUTOMATION in your .env"
        )

    token_url = os.environ.get(
        "SITECORE_AUTH_TOKEN_URL",
        "https://auth.sitecorecloud.io/oauth/token",
    )
    audience = os.environ.get(
        "SITECORE_AUTH_AUDIENCE",
        "https://api.sitecorecloud.io",
    )

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": audience,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


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
        "https://edge-platform.sitecorecloud.io/api/stream/agents",
    ).rstrip("/")
    upload_url = f"{agents_base}/media/upload"

    overwrite = False
    try:
        check = await check_media_artifact_exists(tenant, site, phase, auth_token)
        overwrite = check["exists"]
    except Exception:
        pass

    folder_path = (
        f"/sitecore/media library/Project/{tenant}/{site}"
        f"/Content Strategy/{info['folder']}"
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
                },
                data={
                    "mediaPath": folder_path,
                    "itemName": info["filename"].replace(".docx", ""),
                    "overwrite": "true" if overwrite else "false",
                },
            )
        if not resp.is_success:
            logger.error("Media upload failed: %d %s", resp.status_code, resp.text[:200])
            return {
                "success": False,
                "error": f"Media library upload failed: HTTP {resp.status_code}",
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
