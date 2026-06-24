import logging

from langchain_core.tools import tool

from app.services.brief_service import (
    STANDARD_BRIEF_FIELDS,
    brief_fields_to_text,
    build_brief_fields,
    create_brief,
    delete_brief,
    generate_brief,
    get_brief,
    list_brief_types,
    list_briefs,
    update_brief,
)

logger = logging.getLogger(__name__)


@tool
async def get_brief_types() -> dict:
    """
    List the available campaign brief types from the Sitecore Agents API.

    Call this at the start of the Brief phase to show the marketer which
    brief types are available (e.g. product launch, event, seasonal campaign).
    The returned IDs are required for generate_campaign_brief and save_campaign_brief.

    Returns a list of brief types. After this tool returns, you MUST immediately
    call `present_options` to display them as clickable buttons — do NOT list
    them in prose. Format each as:
      {"id": brief_type_id, "label": name_or_label, "description": "..."}
    """
    try:
        items = await list_brief_types()
        return {"success": True, "brief_types": items, "count": len(items)}
    except Exception as exc:
        logger.error("list_brief_types failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_types": []}


@tool
async def generate_campaign_brief(
    brief_type_id: str,
    brand_id: str,
    prompt: str,
) -> dict:
    """
    Use the Sitecore Agents API to AI-generate campaign brief field content.

    This does NOT save the brief — it returns a preview of the generated fields
    so the marketer can review before committing. Call save_campaign_brief once
    the marketer approves.

    Args:
        brief_type_id: Brief type ID from get_brief_types()
        brand_id: Brand kit ID from list_org_brand_kits()
        prompt: Natural language description of the campaign (e.g. "Summer product launch for B2B SaaS")

    Returns generated_fields dict with AI-populated content for each brief field.
    """
    try:
        fields = await generate_brief(brief_type_id, brand_id, prompt)
        text_summary = brief_fields_to_text(fields)
        return {
            "success": True,
            "generated_fields": fields,
            "text_summary": text_summary,
        }
    except Exception as exc:
        logger.error("generate_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "generated_fields": {}}


@tool
async def save_campaign_brief(
    name: str,
    brief_type_id: str,
    fields: dict | None = None,
    locale: str = "en-us",
) -> dict:
    """
    Save the approved campaign brief as a draft in the Sitecore Agents API.

    Call this ONLY after the marketer has reviewed and approved the brief content.
    The brief is created with Draft status and can be viewed in the Sitecore
    Brief management tool.

    Use compose_campaign_brief instead when building a brief from conversation or
    an uploaded document — it accepts plain text and handles field formatting for you.

    Standard campaign brief fields (pass only the ones you have):
      Objectives, TargetAudience, Message  (required — RichText)
      CreativeRequirements, MarketResearch, AdditionalNotes  (optional — RichText)
      Timeline  (optional — {startDate, endDate, events: [{title, dueDate}]})
      DueDate   (optional — ISO 8601 datetime string)
      Budget    (optional — {type: "Budget", currency: "USD", amount: 0.0})

    RichText values must be ProseMirror doc objects:
      {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "..."}]}]}
    Plain strings are also accepted — they are wrapped automatically.

    Args:
        name: Display name for the brief (e.g. "Summer 2026 Campaign Brief")
        brief_type_id: Brief type ID from get_brief_types()
        fields: Dict of field values — {fieldName: {"type": "...", "value": ...}}
                Plain string values are auto-normalized for RichText fields.
        locale: Locale code in xx-XX format (default "en-us")

    Returns the created brief id, name, status, and locale.
    """
    try:
        brief = await create_brief(name, brief_type_id, fields=fields, locale=locale)
        return {
            "success": True,
            "brief_id": brief.get("id"),
            "name": brief.get("name"),
            "status": brief.get("status", "Draft"),
            "locale": brief.get("locale"),
        }
    except Exception as exc:
        logger.error("create_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_id": None}


@tool
async def get_campaign_brief(brief_id: str) -> dict:
    """
    Retrieve a saved campaign brief from the Sitecore Agents API.

    Use this to load brief context for the Campaign phase — inject the brief
    content so the marketer does not need to re-enter it.

    Args:
        brief_id: Brief ID from save_campaign_brief or find_campaign_brief

    Returns the brief name, status, locale, and all field content as text.
    """
    try:
        brief = await get_brief(brief_id)
        fields = brief.get("fields") or {}
        text_content = brief_fields_to_text(fields)
        return {
            "success": True,
            "brief_id": brief.get("id"),
            "name": brief.get("name"),
            "status": brief.get("status"),
            "locale": brief.get("locale"),
            "fields": fields,
            "text_content": text_content,
            "updated_on": brief.get("updatedOn"),
        }
    except Exception as exc:
        logger.error("get_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_id": brief_id}


@tool
async def update_campaign_brief(
    brief_id: str,
    name: str | None = None,
    fields: dict | None = None,
) -> dict:
    """
    Update an existing campaign brief in the Sitecore Agents API.

    Use this when the marketer wants to revise a previously saved brief.
    Only the provided fields are updated; all others are preserved.

    Args:
        brief_id: Brief ID to update
        name: New name for the brief (optional)
        fields: Updated field values dict (optional)

    Returns the updated brief id and name.
    """
    try:
        result = await update_brief(brief_id, name=name, fields=fields)
        return {
            "success": True,
            "brief_id": result.get("id"),
            "name": result.get("name"),
            "status": result.get("status"),
        }
    except Exception as exc:
        logger.error("update_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_id": brief_id}


@tool
async def delete_campaign_brief(brief_id: str) -> dict:
    """
    Permanently delete a campaign brief from the Sitecore Agents API.

    This action is IRREVERSIBLE. ONLY call this after the marketer has confirmed
    they want to delete the brief. Use find_campaign_brief to resolve a brief name
    to its ID before calling — NEVER invent a brief_id.

    Args:
        brief_id: Brief ID from save_campaign_brief or find_campaign_brief

    Returns success status and the deleted brief_id, or success=False with an error.
    """
    try:
        return await delete_brief(brief_id)
    except Exception as exc:
        logger.error("delete_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_id": brief_id}


@tool
async def describe_brief_schema() -> dict:
    """
    Return the standard campaign brief field schema.

    Call this when:
    - The marketer asks what information is needed to create a brief
    - You are about to create a brief from conversation and need to know what to collect
    - You are extracting brief content from an uploaded document and need field names

    Returns a list of fields with name, type, description, and whether they are required.
    For structured fields (Timeline, Budget) also returns the expected shape.
    """
    return {
        "success": True,
        "brief_type": "Standard Campaign Brief",
        "fields": STANDARD_BRIEF_FIELDS,
        "notes": (
            "RichText fields accept plain text — it is wrapped in the required format automatically. "
            "Timeline and Budget fields require structured values (see 'shape' on each field). "
            "DueDate accepts a date string in YYYY-MM-DD format; time defaults to 23:59:59 UTC."
        ),
    }


@tool
async def compose_campaign_brief(
    brief_name: str,
    brief_type_id: str,
    objectives: str,
    target_audience: str,
    message: str,
    creative_requirements: str = "",
    market_research: str = "",
    additional_notes: str = "",
    due_date: str | None = None,
    budget_amount: float | None = None,
    budget_currency: str = "USD",
    timeline_start: str | None = None,
    timeline_end: str | None = None,
    locale: str = "en-us",
) -> dict:
    """
    Build and save a campaign brief from plain-text field values.

    Use this tool when creating a brief from conversation, research, or an
    uploaded document. Pass plain text for each field — all formatting and
    field-type wrapping is handled automatically.

    The three required text fields are Objectives, TargetAudience, and Message.
    All other fields are optional — include them when the information is available.

    Args:
        brief_name:            Display name (e.g. "Q3 Product Launch Brief")
        brief_type_id:         Brief type ID from get_brief_types()
        objectives:            What the campaign aims to achieve (plain text)
        target_audience:       Who the campaign is for (plain text)
        message:               Core message / value proposition (plain text)
        creative_requirements: Brand guidelines, mandatory inclusions (plain text)
        market_research:       Competitor and market context (plain text)
        additional_notes:      Any other context or constraints (plain text)
        due_date:              Campaign deadline — YYYY-MM-DD or ISO 8601 datetime
        budget_amount:         Total budget as a number (e.g. 50000)
        budget_currency:       Currency code (default "USD")
        timeline_start:        Campaign start date — YYYY-MM-DD
        timeline_end:          Campaign end date — YYYY-MM-DD
        locale:                Locale code in xx-XX format (default "en-us")

    Returns the created brief id, name, status, and locale.
    """
    try:
        fields = build_brief_fields(
            objectives=objectives,
            target_audience=target_audience,
            message=message,
            creative_requirements=creative_requirements,
            market_research=market_research,
            additional_notes=additional_notes,
            due_date=due_date,
            budget_amount=budget_amount,
            budget_currency=budget_currency,
            timeline_start=timeline_start,
            timeline_end=timeline_end,
        )
        brief = await create_brief(brief_name, brief_type_id, fields=fields, locale=locale)
        return {
            "success": True,
            "brief_id": brief.get("id"),
            "name": brief.get("name"),
            "status": brief.get("status", "Draft"),
            "locale": brief.get("locale"),
        }
    except Exception as exc:
        logger.error("compose_campaign_brief failed: %s", exc)
        return {"success": False, "error": str(exc), "brief_id": None}


@tool
async def find_campaign_brief(name: str | None = None, status: str | None = None) -> dict:
    """
    Search for existing campaign briefs in the Sitecore Agents API.

    Call this at session start to detect whether a brief already exists for
    this campaign, or when the marketer says they have an existing brief.

    Args:
        name: Partial name match — e.g. "Summer" matches "Summer Campaign Brief"
        status: Filter by status — e.g. "Draft" or "Active" (optional)

    Returns a list of matching briefs with their id, name, status, and locale.
    If the user is selecting a brief to work with, you MUST immediately call
    `present_options` after this tool returns — do NOT write a prose list.
    Format each as: {"id": brief_id, "label": name, "metadata": status}
    """
    try:
        items = await list_briefs(name=name, status=status)
        # Normalize items so each has a top-level "id" field regardless of API naming
        normalized: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if "id" not in item:
                # Try common alternative field names for the primary ID
                for alt in ("briefId", "brief_id", "Id", "ID"):
                    if alt in item:
                        item = {**item, "id": item[alt]}
                        logger.warning(
                            "find_campaign_brief: item uses '%s' instead of 'id' — normalized", alt
                        )
                        break
                else:
                    logger.warning(
                        "find_campaign_brief: item has no recognisable ID field — keys: %s",
                        list(item.keys()),
                    )
            normalized.append(item)
        return {"success": True, "briefs": normalized, "count": len(normalized)}
    except Exception as exc:
        logger.error("list_briefs failed: %s", exc)
        return {"success": False, "error": str(exc), "briefs": []}
