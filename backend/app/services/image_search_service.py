"""Image search service — Cohere multimodal embeddings + pgvector similarity search.

Prerequisites:
    - PostgreSQL with pgvector extension: CREATE EXTENSION IF NOT EXISTS vector;
    - COHERE_API_KEY env var
    - SITECORE_CM_HOST env var (for media library crawl)

Embedding model: embed-english-v3.0 (1024-dimensional)
Distance metric: cosine (pgvector <=> operator; lower = more similar)
Score reported as 1 - cosine_distance (higher = more relevant, range 0–1)
"""
import base64
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_COHERE_EMBED_URL = "https://api.cohere.ai/v2/embed"
_COHERE_MODEL = "embed-english-v3.0"
_DEFAULT_LIMIT = 5

# Sitecore CM GraphQL — used for media library crawl
_CM_GRAPHQL_PATH = "/sitecore/api/graph/edge"
# Image template GUID in Sitecore (standard Sitecore image template)
_IMAGE_TEMPLATE_ID = "{EAF50F47-D3AC-4364-A0A4-F812D3C5E2E7}"


def _cohere_headers() -> dict[str, str]:
    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is not set")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def embed_text_query(query: str) -> list[float]:
    """Embed a natural-language search query using Cohere text embeddings.

    Returns a 1024-dimensional float vector suitable for cosine similarity
    against image embeddings stored in pgvector.
    """
    payload = {
        "model": _COHERE_MODEL,
        "input_type": "search_query",
        "embedding_types": ["float"],
        "texts": [query],
    }
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.post(_COHERE_EMBED_URL, json=payload, headers=_cohere_headers())
        resp.raise_for_status()
        data = resp.json()

    embed_data = data.get("embeddings", {})
    embeddings = embed_data.get("float") if isinstance(embed_data, dict) else embed_data
    if not embeddings:
        raise ValueError("Cohere embed API returned no embeddings")
    return embeddings[0] if isinstance(embeddings[0], list) else embeddings


async def embed_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[float]:
    """Embed an image using Cohere multimodal embeddings.

    Returns a 1024-dimensional float vector in the same space as text embeddings,
    enabling cross-modal similarity search.
    """
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:{mime_type};base64,{b64}"
    payload = {
        "model": _COHERE_MODEL,
        "input_type": "image",
        "embedding_types": ["float"],
        "images": [data_uri],
    }
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(_COHERE_EMBED_URL, json=payload, headers=_cohere_headers())
        resp.raise_for_status()
        data = resp.json()

    embed_data = data.get("embeddings", {})
    embeddings = embed_data.get("float") if isinstance(embed_data, dict) else embed_data
    if not embeddings:
        raise ValueError("Cohere embed API returned no image embeddings")
    return embeddings[0] if isinstance(embeddings[0], list) else embeddings


async def search_images(
    query: str,
    site_id: str,
    collection: str,
    environment: str,
    db: AsyncSession,
    limit: int = _DEFAULT_LIMIT,
) -> dict:
    """Search indexed images by natural-language description.

    Embeds the query with Cohere and performs cosine similarity search against
    the pgvector image_embeddings table scoped to the given site and environment.

    Returns {success, query, results: [{item_id, item_name, media_path, alt_text, score}], count}.
    Returns empty results (not an error) if no images are indexed yet.
    """
    try:
        query_embedding = await embed_text_query(query)
    except Exception as exc:
        logger.warning("Failed to embed query %r: %s", query, exc)
        return {"success": False, "error": str(exc), "query": query}

    embedding_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT item_id, item_name, media_path, alt_text,
               ROUND((1 - (embedding <=> :embedding::vector))::numeric, 4) AS score
        FROM image_embeddings
        WHERE site_id   = :site_id
          AND collection = :collection
          AND environment = :environment
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """)

    try:
        result = await db.execute(sql, {
            "embedding": embedding_literal,
            "site_id": site_id,
            "collection": collection,
            "environment": environment,
            "limit": limit,
        })
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("pgvector search failed: %s", exc)
        return {"success": False, "error": str(exc), "query": query}

    results = [
        {
            "item_id": row[0],
            "item_name": row[1],
            "media_path": row[2],
            "alt_text": row[3],
            "score": float(row[4]),
        }
        for row in rows
    ]
    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results),
    }


async def upsert_image_embedding(
    item_id: str,
    site_id: str,
    collection: str,
    environment: str,
    media_path: str,
    item_name: str,
    alt_text: str | None,
    embedding: list[float],
    db: AsyncSession,
) -> None:
    """Insert or update an image embedding row (upsert on item_id+environment+site_id)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    sql = text("""
        INSERT INTO image_embeddings
            (item_id, environment, site_id, collection, media_path, item_name, alt_text,
             embedding, indexed_at, updated_at)
        VALUES
            (:item_id, :environment, :site_id, :collection, :media_path, :item_name, :alt_text,
             :embedding::vector, :now, :now)
        ON CONFLICT (item_id, environment, site_id)
        DO UPDATE SET
            media_path  = EXCLUDED.media_path,
            item_name   = EXCLUDED.item_name,
            alt_text    = EXCLUDED.alt_text,
            embedding   = EXCLUDED.embedding,
            updated_at  = EXCLUDED.updated_at
    """)
    await db.execute(sql, {
        "item_id": item_id,
        "environment": environment,
        "site_id": site_id,
        "collection": collection,
        "media_path": media_path,
        "item_name": item_name,
        "alt_text": alt_text,
        "embedding": embedding_literal,
        "now": now,
    })
    await db.commit()


async def index_image_from_url(
    item_id: str,
    site_id: str,
    collection: str,
    environment: str,
    media_path: str,
    item_name: str,
    alt_text: str | None,
    image_url: str,
    auth_token: str,
    db: AsyncSession,
) -> dict:
    """Download one image from Sitecore, embed it, and upsert into the index.

    Returns {success, item_id, item_name} or {success=False, error}.
    """
    try:
        cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
        full_url = image_url if image_url.startswith("http") else f"{cm_host}{image_url}"
        async with httpx.AsyncClient(timeout=30) as http:
            img_resp = await http.get(
                full_url,
                headers={"Authorization": f"Bearer {auth_token}"},
                follow_redirects=True,
            )
            img_resp.raise_for_status()
        image_bytes = img_resp.content
        mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", image_url, exc)
        return {"success": False, "item_id": item_id, "error": f"Download failed: {exc}"}

    try:
        embedding = await embed_image(image_bytes, mime_type=mime)
    except Exception as exc:
        logger.warning("Failed to embed image %s: %s", item_id, exc)
        return {"success": False, "item_id": item_id, "error": f"Embedding failed: {exc}"}

    await upsert_image_embedding(
        item_id=item_id,
        site_id=site_id,
        collection=collection,
        environment=environment,
        media_path=media_path,
        item_name=item_name,
        alt_text=alt_text,
        embedding=embedding,
        db=db,
    )
    return {"success": True, "item_id": item_id, "item_name": item_name}


async def crawl_and_index_media_library(
    site_id: str,
    collection: str,
    environment: str,
    folder_path: str | None,
    auth_token: str,
    db: AsyncSession,
    batch_limit: int = 100,
) -> dict:
    """Crawl the Sitecore media library via GraphQL and index all images.

    Queries the CM Edge GraphQL API for image items under `folder_path`
    (or the full media library if None). Embeds each image with Cohere and
    stores the vectors in pgvector.

    Returns {success, indexed_count, failed_count, skipped_count, total_found}.
    """
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        return {"success": False, "error": "SITECORE_CM_HOST is not set"}

    graphql_url = f"{cm_host}{_CM_GRAPHQL_PATH}"
    root_path = folder_path or "/sitecore/media library"

    # GraphQL query for image items under a path
    gql_query = """
    query GetMediaImages($rootPath: String!, $after: String) {
      search(
        fieldsEqual: [
          { name: "_templates", value: "{EAF50F47-D3AC-4364-A0A4-F812D3C5E2E7}" }
        ]
        rootItem: $rootPath
        first: 50
        after: $after
      ) {
        total
        pageInfo { hasNextPage endCursor }
        results {
          id
          name
          url { path }
          field(name: "Alt") { value }
        }
      }
    }
    """

    indexed = 0
    failed = 0
    cursor: str | None = None
    total_found = 0

    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            variables = {"rootPath": root_path, "after": cursor or ""}
            try:
                resp = await http.post(
                    graphql_url,
                    json={"query": gql_query, "variables": variables},
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                gql_data = resp.json()
            except Exception as exc:
                logger.error("GraphQL media crawl failed: %s", exc)
                return {
                    "success": False,
                    "error": str(exc),
                    "indexed_count": indexed,
                    "failed_count": failed,
                }

            search_result = gql_data.get("data", {}).get("search", {})
            total_found = search_result.get("total", 0)
            items = search_result.get("results", [])
            page_info = search_result.get("pageInfo", {})

            for item in items:
                item_id = item.get("id", "")
                item_name = item.get("name", "")
                media_url_path = (item.get("url") or {}).get("path", "")
                alt_text = (item.get("field") or {}).get("value")

                if not item_id or not media_url_path:
                    failed += 1
                    continue

                result = await index_image_from_url(
                    item_id=item_id,
                    site_id=site_id,
                    collection=collection,
                    environment=environment,
                    media_path=media_url_path,
                    item_name=item_name,
                    alt_text=alt_text,
                    image_url=media_url_path,
                    auth_token=auth_token,
                    db=db,
                )
                if result["success"]:
                    indexed += 1
                else:
                    failed += 1
                    logger.debug("Failed to index %s: %s", item_id, result.get("error"))

                if indexed + failed >= batch_limit:
                    logger.info("Reached batch_limit=%d, stopping crawl", batch_limit)
                    return {
                        "success": True,
                        "indexed_count": indexed,
                        "failed_count": failed,
                        "skipped_count": 0,
                        "total_found": total_found,
                        "batch_limited": True,
                    }

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

    return {
        "success": True,
        "indexed_count": indexed,
        "failed_count": failed,
        "skipped_count": 0,
        "total_found": total_found,
        "batch_limited": False,
    }
