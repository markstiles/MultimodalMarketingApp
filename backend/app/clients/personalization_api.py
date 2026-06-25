import logging

from langchain_core.tools import tool

from app.services.personalization_service import (
    create_component_ab_test_api,
    create_personalization_version_api,
    get_condition_template_by_id_api,
    get_condition_templates_api,
    get_personalization_versions_api,
    update_ab_test_api,
    update_personalization_version_api,
)

logger = logging.getLogger(__name__)


@tool
async def get_personalization_versions(page_id: str, language: str = "en") -> dict:
    """List all personalization variants configured for a Sitecore page.

    Args:
        page_id: UUID of the page.
        language: Language version (default "en").
    """
    try:
        variants = await get_personalization_versions_api(page_id=page_id, language=language)
        return {"success": True, "variants": variants, "count": len(variants)}
    except Exception as exc:
        logger.error("get_personalization_versions error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_condition_templates() -> dict:
    """List all available condition templates for personalization targeting.

    Returns condition template IDs and their parameter requirements.
    Use this before creating a personalization variant to discover valid condition templates.
    """
    try:
        templates = await get_condition_templates_api()
        return {"success": True, "templates": templates, "count": len(templates)}
    except Exception as exc:
        logger.error("get_condition_templates error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def get_condition_template_by_id(template_id: str) -> dict:
    """Get detailed parameters for a specific personalization condition template.

    Args:
        template_id: The condition template identifier (e.g. "returning_visitor").
    """
    try:
        template = await get_condition_template_by_id_api(template_id=template_id)
        return {"success": True, **template}
    except Exception as exc:
        logger.error("get_condition_template_by_id error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def create_perso_version(
    page_id: str,
    name: str,
    variant_name: str,
    audience_name: str,
    condition_groups: list,
    language: str = "en",
) -> dict:
    """Create a personalization variant for a Sitecore page.

    ALWAYS confirm with the user before calling this tool. Show them the
    targeting rule, variant name, and audience before proceeding.

    Use get_condition_templates first to discover valid condition template IDs.
    Each condition group uses ConditionGroupInput with union_type (AND/OR) and
    a list of conditions with condition_template_id and condition_params.

    Args:
        page_id: UUID of the page to personalize.
        name: Name for the personalization rule.
        variant_name: Name for the content variant.
        audience_name: Name of the target audience.
        condition_groups: List of condition group objects defining targeting rules.
        language: Language code (default "en").
    """
    try:
        result = await create_personalization_version_api(
            page_id=page_id,
            name=name,
            variant_name=variant_name,
            audience_name=audience_name,
            condition_groups=condition_groups,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("create_perso_version error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def create_perso_version_multi(
    page_id: str,
    name: str,
    variant_name: str,
    audience_name: str,
    condition_groups: list,
    language: str = "en",
) -> dict:
    """Create a personalization variant with multiple condition groups for complex targeting.

    ALWAYS confirm with the user before calling this tool. Show them all the
    targeting conditions and audience definition before proceeding.

    Similar to create_perso_version but intended for cases with multiple condition
    groups combining AND/OR logic across different targeting dimensions.

    Args:
        page_id: UUID of the page to personalize.
        name: Name for the personalization rule.
        variant_name: Name for the content variant.
        audience_name: Name of the target audience.
        condition_groups: List of condition group objects. Each group has union_type
            (AND/OR) and a list of conditions. Groups themselves are combined with OR.
        language: Language code (default "en").
    """
    try:
        result = await create_personalization_version_api(
            page_id=page_id,
            name=name,
            variant_name=variant_name,
            audience_name=audience_name,
            condition_groups=condition_groups,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("create_perso_version_multi error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def update_perso_version(
    page_id: str,
    variant_id: str,
    variant_name: str,
    audience_name: str,
    condition_groups: list,
    language: str = "en",
) -> dict:
    """Update an existing personalization variant for a Sitecore page.

    ALWAYS confirm with the user before calling this tool. Show them the
    current vs. new targeting rules and wait for explicit approval.

    Args:
        page_id: UUID of the page.
        variant_id: ID of the variant to update (get from get_personalization_versions).
        variant_name: Updated variant name.
        audience_name: Updated audience name.
        condition_groups: Updated condition group objects.
        language: Language code (default "en").
    """
    try:
        result = await update_personalization_version_api(
            page_id=page_id,
            variant_id=variant_id,
            variant_name=variant_name,
            audience_name=audience_name,
            condition_groups=condition_groups,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("update_perso_version error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def create_component_ab_test(
    site_id: str,
    page_id: str,
    component_id: str,
    name: str,
    goal_type: str,
    variants: list,
    language: str = "en",
) -> dict:
    """Create an A/B/n test for a Sitecore component.

    ALWAYS confirm with the user before calling this tool. Show them the
    component, variant list, and traffic splits and wait for explicit approval.
    Traffic splits in variants must sum to 100; exactly one variant must be control.

    Args:
        site_id: Site identifier.
        page_id: UUID of the page containing the component.
        component_id: UUID of the component to A/B test.
        name: Name for the A/B test.
        goal_type: The conversion goal type (e.g. "click", "visit").
        variants: List of variant objects with traffic splits; splits must sum to 100.
        language: Language code (default "en").
    """
    try:
        result = await create_component_ab_test_api(
            site_id=site_id,
            page_id=page_id,
            component_id=component_id,
            name=name,
            goal_type=goal_type,
            variants=variants,
            language=language,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("create_component_ab_test error: %s", exc)
        return {"success": False, "error": str(exc)}


@tool
async def update_ab_test(
    flow_id: str,
    name: str = "",
    variants: list | None = None,
    archived: bool | None = None,
) -> dict:
    """Update an existing A/B/n test.

    ALWAYS confirm with the user before calling this tool. Show them the
    changes being made and wait for explicit approval.

    Args:
        flow_id: The flow ID of the A/B test (get from list_flow_definitions).
        name: New name for the test (optional).
        variants: Updated variant list with traffic splits (optional; must sum to 100).
        archived: Set to True to archive the test (optional).
    """
    try:
        result = await update_ab_test_api(
            flow_id=flow_id,
            name=name or None,
            variants=variants,
            archived=archived,
        )
        return {"success": True, **result}
    except Exception as exc:
        logger.error("update_ab_test error: %s", exc)
        return {"success": False, "error": str(exc)}
