import logging

from langchain_core.tools import tool

from app.services.components_service import (
    create_component_datasource_api,
    get_component_api,
    list_components_api,
    search_component_datasources_api,
)

logger = logging.getLogger(__name__)


@tool
async def list_components(site_name: str) -> dict:
    """List all components available for a Sitecore site.

    Returns the full component catalog including built-in and custom components.
    Use this to find component IDs before calling create_component_ds or
    get_allowed_components_by_placeholder.

    Args:
        site_name: The site name (e.g. "skate-park").
    """
    try:
        result = await list_components_api(site_name=site_name)
        components = result.get("components", result)
        return {"success": True, "components": components}
    except Exception as exc:
        logger.error("list_components error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_component(component_id: str) -> dict:
    """Get details of a specific Sitecore component including its datasource options.

    Args:
        component_id: UUID of the component.
    """
    try:
        result = await get_component_api(component_id=component_id)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("get_component error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def create_component_ds(
    component_id: str,
    site_name: str,
    data_fields: dict,
    language: str = "en",
) -> dict:
    """Create a new datasource item for a Sitecore component.

    ALWAYS confirm with the user before calling this tool. Show them the
    component ID, site name, and field values and wait for explicit approval.

    Use search_component_datasources first to check if a suitable datasource
    already exists before creating a new one.

    Args:
        component_id: UUID of the component for which to create the datasource.
        site_name: Name of the site where the datasource will be created.
        data_fields: Dict of field name → value pairs for the datasource item.
        language: Language code (default "en").
    """
    try:
        result = await create_component_datasource_api(
            component_id=component_id,
            site_name=site_name,
            data_fields=data_fields,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("create_component_ds error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def search_component_datasources(component_id: str, term: str) -> dict:
    """Search for existing datasources that can be used with a Sitecore component.

    Use this before create_component_ds to avoid creating duplicate datasources.

    Args:
        component_id: UUID of the component.
        term: Search term to filter datasources by name or content.
    """
    try:
        result = await search_component_datasources_api(component_id=component_id, term=term)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("search_component_datasources error: %s", exc)
        return {"success": False, "error": str(exc)}
