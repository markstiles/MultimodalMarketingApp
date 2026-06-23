import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def present_options(
    items: list[dict],
    prompt: str = "",
    option_type: str = "generic",
) -> dict:
    """
    Render a list of choices as interactive UI cards/buttons so the user can select one.

    Use this whenever you have retrieved a list of items (sites, briefs, templates,
    collections, pages, languages) and the user needs to pick one. This renders a
    visual selection panel instead of a plain text list — do NOT also write the same
    list out in prose.

    After calling this tool, stop and wait for the user's reply. Do not continue
    with follow-up actions until the user has made their selection.

    Args:
        items: List of objects, each with at least {"id": "...", "label": "..."}.
               Optional extra keys: "description", "thumbnail" (URL), "metadata" (short string).
               Example: [{"id": "abc", "label": "Acme Site", "description": "Marketing microsite"}]
        prompt: Question or instruction shown above the option cards.
                Example: "Which site would you like to work with?"
        option_type: Rendering hint — one of: "site", "brief", "template", "collection",
                     "page", "language", "image", "generic"

    Returns the options so the conversation context includes what was presented.
    """
    logger.info("present_options: type=%s count=%d", option_type, len(items))
    return {
        "success": True,
        "presented": True,
        "items": items,
        "prompt": prompt,
        "option_type": option_type,
        "count": len(items),
    }
