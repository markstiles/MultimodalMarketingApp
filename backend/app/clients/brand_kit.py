import logging

from langchain_core.tools import tool

from app.services.brand_kit_service import (
    create_brand_kit,
    get_brand_kit_voice_sections,
    list_brand_kits,
    run_brand_review,
    upload_brand_document,
)
from app.services.sitecore_auth import get_sitecore_automation_token

logger = logging.getLogger(__name__)


@tool
async def list_org_brand_kits() -> dict:
    """
    List all brand kits in the Sitecore Stream organization.

    Call this at the start of the Brand Voice phase to check whether an existing
    brand kit is available for the marketer's brand. Returns a list of kits with
    their id, name, status, and industry.

    If the list is empty, offer the marketer the option to create a new brand kit
    and import their brand documents.
    If the marketer is choosing a brand kit, you MUST immediately call `present_options`
    after this tool returns — do NOT write a prose list.
    Format each kit as: {"id": kit_id, "label": kit_name, "metadata": status}
    """
    try:
        token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "brand_kits": []}

    try:
        kits = await list_brand_kits(token)
        return {"success": True, "brand_kits": kits, "count": len(kits)}
    except RuntimeError as exc:
        return {"success": False, "error": str(exc), "brand_kits": []}


@tool
async def get_brand_voice_summary(kit_id: str) -> dict:
    """
    Read the Brand Context, Tone of Voice, and Do's & Don'ts from a Sitecore Stream
    brand kit.

    Call this after the marketer has selected a brand kit from list_org_brand_kits.
    The returned sections provide the brand voice context needed to produce the
    Brand Voice Summary artifact and to inform downstream Brief and Campaign phases.

    Args:
        kit_id: The brand kit UUID (from list_org_brand_kits)

    Returns brand_context, tone_of_voice, and dos_and_donts as text strings.
    """
    try:
        token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    try:
        sections = await get_brand_kit_voice_sections(kit_id, token)
        return {"success": True, "kit_id": kit_id, **sections}
    except RuntimeError as exc:
        return {"success": False, "kit_id": kit_id, "error": str(exc)}


@tool
async def create_org_brand_kit(name: str, brand_name: str | None = None) -> dict:
    """
    Create a new brand kit in the Sitecore Stream organization.

    Call this when the marketer wants to set up a new brand kit because none
    exists for their brand. After creating the kit, use import_brand_document
    to upload brand guidelines PDFs.

    Args:
        name: Display name for the brand kit (e.g. "Acme Corp Brand Kit")
        brand_name: The brand name if different from the kit name
    """
    try:
        token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    try:
        result = await create_brand_kit(name, token, brand_name=brand_name)
        return {"success": True, **result}
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}


@tool
async def import_brand_document(kit_id: str, file_url: str, filename: str) -> dict:
    """
    Upload a PDF brand document to a Sitecore Stream brand kit.

    Call this when the marketer wants to import brand guidelines, tone of voice
    documents, or brand identity guides into the brand kit. After upload, Sitecore
    can ingest the document to populate the brand kit sections.

    The document must be accessible via URL. Use a Sitecore media library URL if
    the marketer has already uploaded the file through the chat interface (starts
    with /-/media/...). Use an external https URL for publicly accessible documents.

    Args:
        kit_id: The brand kit UUID to attach the document to
        file_url: URL of the PDF document (https URL or Sitecore media path)
        filename: Display name for the document (e.g. "Brand Guidelines 2025.pdf")
    """
    try:
        token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    try:
        result = await upload_brand_document(kit_id, file_url, filename, token)
        return {"success": True, **result}
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}


@tool
async def review_content_against_brand(kit_id: str, content: str) -> dict:
    """
    Score content against brand kit guidelines using the Sitecore Brand Review API.

    Use this optionally before saving a Brief or Campaign artifact to check brand
    compliance. A score of 5 indicates highest alignment; 1 indicates poor alignment.
    The response includes per-section scores, explanations, and improvement suggestions.

    Args:
        kit_id: The brand kit UUID to evaluate against
        content: The text content to review (markdown or plain text; max ~2000 words)
    """
    try:
        token = await get_sitecore_automation_token()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    try:
        result = await run_brand_review(kit_id, content, token)
        return {"success": True, "kit_id": kit_id, **result}
    except RuntimeError as exc:
        return {"success": False, "kit_id": kit_id, "error": str(exc)}
