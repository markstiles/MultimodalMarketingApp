import logging

from langchain_core.tools import tool

from app.services.marketing_research_service import web_search

logger = logging.getLogger(__name__)


@tool
async def search_market_research(queries: list[str]) -> dict:
    """
    Search the web for competitive intelligence and market data to support the
    Research phase of the marketing pipeline.

    Call this ONLY after the marketer has explicitly requested AI-assisted research.
    Pass 3-5 targeted queries covering competitor positioning, market trends, and
    audience pain points relevant to the marketer's product category.

    Args:
        queries: List of search query strings. Example:
            ["SaaS project management competitor positioning 2025",
             "remote team collaboration software market trends",
             "project manager pain points productivity tools"]

    Returns a dict with per-query results and a combined results list. Each result
    has: url, title, content, score. Use these findings to synthesize the Research
    Brief — do not present raw search results to the marketer.
    """
    if not queries:
        return {"success": False, "error": "No queries provided", "results": []}

    all_results: list[dict] = []
    errors: list[str] = []

    for query in queries:
        try:
            results = await web_search(query, max_results=5)
            for r in results:
                r["query"] = query
            all_results.extend(results)
        except RuntimeError as exc:
            logger.warning("Search failed for %r: %s", query, exc)
            errors.append(str(exc))

    return {
        "success": bool(all_results),
        "query_count": len(queries),
        "result_count": len(all_results),
        "results": all_results,
        "errors": errors if errors else None,
    }
