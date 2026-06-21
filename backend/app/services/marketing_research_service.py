import logging
import os

logger = logging.getLogger(__name__)


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web via Tavily. Returns a list of {url, title, content} dicts.

    Raises RuntimeError if TAVILY_API_KEY is not set or the API call fails.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not set — add it to your .env to enable web research"
        )

    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError(
            "tavily-python is not installed — run `pip install tavily-python`"
        ) from exc

    client = TavilyClient(api_key=api_key)
    try:
        response = client.search(query, max_results=max_results)
    except Exception as exc:
        logger.error("Tavily search failed for query %r: %s", query, exc)
        raise RuntimeError(f"Web search failed: {exc}") from exc

    results = []
    for item in response.get("results", []):
        results.append(
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "score": item.get("score"),
            }
        )
    return results
