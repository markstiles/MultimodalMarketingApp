import logging

from langchain_core.tools import tool

from app.services.content_service import (
    create_content_item_api,
    delete_content_api,
    get_content_item_by_id_api,
    get_content_item_by_path_api,
    list_content_insert_options_api,
    update_content_api,
)

logger = logging.getLogger(__name__)


@tool
async def create_content_item(
    template_id: str,
    name: str,
    parent_id: str,
    language: str = "en",
    fields: dict | None = None,
) -> dict:
    """Create a new content item in Sitecore.

    ALWAYS confirm with the user before calling this tool. Show them the
    template ID, name, and parent location and wait for explicit approval.

    Args:
        template_id: UUID of the template to use (get from list_content_insert_options).
        name: Name for the new content item.
        parent_id: UUID of the parent item under which to create this item.
        language: Language code (default "en").
        fields: Optional dict of field name → value pairs to set on creation.
    """
    try:
        result = await create_content_item_api(
            template_id=template_id,
            name=name,
            parent_id=parent_id,
            language=language,
            fields=fields,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("create_content_item error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_content_item(
    item_id: str = "",
    item_path: str = "",
    language: str = "en",
) -> dict:
    """Retrieve a Sitecore content item by ID or path.

    Provide either item_id (UUID) or item_path (Sitecore path). If both are
    given, item_id takes precedence.

    Args:
        item_id: UUID of the content item.
        item_path: Full Sitecore path (e.g. "/sitecore/content/MySite/Home/Promo").
        language: Language code (default "en").
    """
    try:
        if item_id:
            result = await get_content_item_by_id_api(item_id=item_id, language=language)
        elif item_path:
            result = await get_content_item_by_path_api(
                item_path=item_path, language=language, fail_on_not_found=True
            )
        else:
            return {"success": False, "error": "Provide either item_id or item_path."}
        return {"success": True, **result}
    except Exception as exc:
        logger.error("get_content_item error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def update_content(
    item_id: str,
    fields: dict,
    language: str = "en",
    create_new_version: bool = False,
    site_name: str = "",
) -> dict:
    """Update fields on an existing Sitecore content item.

    ALWAYS confirm with the user before calling this tool. Show the item ID,
    the fields being changed, and wait for explicit approval.

    Args:
        item_id: UUID of the content item to update.
        fields: Dict of field name → new value pairs to update.
        language: Language version to update (default "en").
        create_new_version: Whether to create a new version (default False).
        site_name: Site name where the item resides (optional).
    """
    try:
        result = await update_content_api(
            item_id=item_id,
            fields=fields,
            language=language,
            create_new_version=create_new_version,
            site_name=site_name or None,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("update_content error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def update_fields_on_item(
    item_id: str,
    fields: dict,
    language: str = "en",
) -> dict:
    """Update one or more fields on a Sitecore content item (simplified wrapper).

    ALWAYS confirm with the user before calling this tool. Show the item ID,
    the fields being changed, and wait for explicit approval.

    Args:
        item_id: UUID of the content item to update.
        fields: Dict of field name → new value pairs.
        language: Language version to update (default "en").
    """
    try:
        result = await update_content_api(
            item_id=item_id,
            fields=fields,
            language=language,
            create_new_version=False,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("update_fields_on_item error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def delete_content(item_id: str, language: str = "en") -> dict:
    """Delete a Sitecore content item. THIS IS IRREVERSIBLE.

    ALWAYS confirm with the user before calling this tool. Warn them that this
    deletes ALL language versions of the item, not just the specified language.
    Wait for explicit approval before proceeding.

    Args:
        item_id: UUID of the content item to delete.
        language: Accepted but does not scope deletion — ALL language versions are deleted.
    """
    return await delete_content_api(item_id=item_id, language=language)


@tool
async def list_content_insert_options(item_id: str, language: str = "en") -> dict:
    """List the allowed child content templates for a Sitecore content item.

    Use this to discover which template IDs are valid for creating child items
    under a given parent before calling create_content_item.

    Args:
        item_id: UUID of the parent content item.
        language: Language context (default "en").
    """
    try:
        options = await list_content_insert_options_api(item_id=item_id, language=language)
        return {"success": True, "options": options, "count": len(options)}
    except Exception as exc:
        logger.error("list_content_insert_options error: %s", exc)
        return {"success": False, "error": str(exc)}
