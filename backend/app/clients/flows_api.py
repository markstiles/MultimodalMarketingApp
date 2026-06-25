import logging

from langchain_core.tools import tool

from app.services.flows_service import (
    get_flow_definition_api,
    get_variant_api,
    list_flow_definitions_by_page_api,
    setup_variant_api,
)

logger = logging.getLogger(__name__)


@tool
async def list_page_flows(page_id: str, language: str = "en") -> dict:
    """List all flow definitions (A/B tests and personalizations) for a Sitecore page.

    Returns both experiment flows and personalization flows with their variants
    and configuration details.

    Args:
        page_id: UUID of the page.
        language: Language version (default "en").
    """
    try:
        flows = await list_flow_definitions_by_page_api(page_id=page_id, language=language)
        return {"success": True, "flows": flows, "count": len(flows)}
    except Exception as exc:
        logger.error("list_page_flows error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_flow_definition(flow_id: str) -> dict:
    """Get the full details of a specific flow definition (A/B test or personalization).

    Use list_page_flows first to discover flow IDs on a page.

    Args:
        flow_id: The flow definition identifier.
    """
    try:
        result = await get_flow_definition_api(flow_id=flow_id)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("get_flow_definition error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_flow_variant(flow_id: str, variant_id: str, language: str = "en") -> dict:
    """Get the datasource and component details for a specific flow variant.

    Args:
        flow_id: The flow definition identifier.
        variant_id: The variant identifier (from list_page_flows or get_flow_definition).
        language: Language version (default "en").
    """
    try:
        result = await get_variant_api(flow_id=flow_id, variant_id=variant_id, language=language)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("get_flow_variant error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def setup_flow_variant(
    flow_id: str,
    variant_id: str,
    page_id: str,
    component_id: str,
    variant_strategy: str,
    language: str = "en",
    page_version: int | None = None,
    swapped_component: dict | None = None,
) -> dict:
    """Set up a component variant for an A/B test or personalization flow.

    ALWAYS confirm with the user before calling this tool. Show them the flow ID,
    variant ID, component, and strategy before proceeding.

    variant_strategy must be one of:
    - HIDE: Hide the component in this variant.
    - SWAP: Replace the component with a different component (requires swapped_component).
    - COPY: Copy the component for independent editing in this variant.

    Use list_page_flows to find flow and variant IDs, and get_components_on_page
    to find component IDs.

    Args:
        flow_id: The flow definition identifier.
        variant_id: The variant identifier to configure.
        page_id: UUID of the page containing the component.
        component_id: UUID of the component to configure as a variant.
        variant_strategy: Strategy for this variant — HIDE, SWAP, or COPY.
        language: Language code (default "en").
        page_version: Specific page version to use (optional, defaults to latest).
        swapped_component: Replacement component details required when strategy is SWAP.
    """
    try:
        result = await setup_variant_api(
            flow_id=flow_id,
            variant_id=variant_id,
            page_id=page_id,
            component_id=component_id,
            variant_strategy=variant_strategy,
            language=language,
            page_version=page_version,
            swapped_component=swapped_component,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("setup_flow_variant error: %s", exc)
        return {"success": False, "error": str(exc)}
