import logging

from langchain_core.tools import tool

from app.services.assets_service import (
    get_asset_info_api,
    search_assets_api,
    update_asset_api,
    upload_asset_api,
)

logger = logging.getLogger(__name__)


@tool
async def search_assets(query: str = "", language: str = "en", asset_type: str = "") -> dict:
    """Search for assets in the Sitecore media library.

    Args:
        query: Search term to filter assets by name or metadata (optional).
        language: Language code to filter assets (default "en").
        asset_type: File type filter — "image", "video", or "document" (optional).
    """
    try:
        results = await search_assets_api(query=query, language=language, asset_type=asset_type)
        return {"success": True, "assets": results, "count": len(results)}
    except Exception as exc:
        logger.error("search_assets error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_asset_info(asset_id: str) -> dict:
    """Get full details of a specific Sitecore media asset including metadata.

    Args:
        asset_id: The unique identifier of the asset.
    """
    try:
        result = await get_asset_info_api(asset_id=asset_id)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("get_asset_info error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def upload_asset(
    file_content: bytes,
    filename: str,
    item_path: str,
    extension: str,
    site_name: str,
    language: str = "en",
) -> dict:
    """Upload a new file to the Sitecore media library.

    ALWAYS confirm with the user before calling this tool. Show them the
    filename, target path, and site name and wait for explicit approval.

    Args:
        file_content: Raw binary content of the file to upload.
        filename: Name for the uploaded asset (e.g. "hero-banner.jpg").
        item_path: Target media library path (e.g. "/sitecore/Media Library/Images/Campaigns").
        extension: File extension without dot (e.g. "jpg", "png", "pdf").
        site_name: Name of the site (e.g. "skate-park").
        language: Language code (default "en").
    """
    try:
        result = await upload_asset_api(
            file_content=file_content,
            filename=filename,
            item_path=item_path,
            extension=extension,
            site_name=site_name,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("upload_asset error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def update_asset(
    asset_id: str,
    fields: dict | None = None,
    language: str = "en",
    name: str = "",
) -> dict:
    """Update metadata and properties of an existing Sitecore media asset.

    ALWAYS confirm with the user before calling this tool. Show them the
    asset ID and the fields being changed and wait for explicit approval.

    Args:
        asset_id: The unique identifier of the asset to update.
        fields: Dict of metadata field name → new value (e.g. {"Alt": "New alt text"}).
        language: Language code (default "en").
        name: New name for the asset (optional — only provide to rename).
    """
    try:
        result = await update_asset_api(
            asset_id=asset_id,
            fields=fields,
            language=language,
            name=name or None,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("update_asset error: %s", exc)
        return {"success": False, "error": str(exc)}
