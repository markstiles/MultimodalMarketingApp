"""Image search service — Cohere multimodal embeddings + pgvector similarity search.

Prerequisites:
    - PostgreSQL with pgvector extension: CREATE EXTENSION IF NOT EXISTS vector;
    - COHERE_API_KEY env var
    - SITECORE_CM_HOST env var (for media library crawl)

Embedding model: embed-english-v3.0 (1024-dimensional)
Distance metric: cosine (pgvector <=> operator; lower = more similar)
Score reported as 1 - cosine_distance (higher = more relevant, range 0–1)
"""
import asyncio
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
_SCORE_THRESHOLD = 0.32  # minimum hybrid score — results below this are excluded

# Sitecore CM SSC REST API — used for media library crawl
_CM_SSC_ITEM_PATH = "/sitecore/api/ssc/item"
# XM Cloud image template GUIDs (bare, no braces — SSC returns IDs without braces).
# Three versioned and three unversioned variants covering image, jpeg, and webp.
_IMAGE_TEMPLATE_IDS: frozenset[str] = frozenset({
    # Versioned
    "F6F72B6B-F5D5-4ED0-8701-45266461F77B",  # webp
    "EB3FB96C-D56B-4AC9-97F8-F07B24BB9BF7",  # jpeg
    "C97BA923-8009-4858-BDD5-D8BE5FCCECF7",  # image
    # Unversioned
    "309EB383-99B6-4722-9FAB-58D8AE802D72",  # webp
    "DAF085E8-602E-43A6-8299-038FF171349F",  # jpeg
    "F1828A2C-7E5D-4BBD-98CA-320474871548",  # image
})


def _cohere_headers() -> dict[str, str]:
    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is not set")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _cohere_post(http: httpx.AsyncClient, payload: dict) -> dict:
    """POST to the Cohere embed endpoint with exponential-backoff retry on 429."""
    max_attempts = 5
    delay = 1.0
    for attempt in range(max_attempts):
        resp = await http.post(_COHERE_EMBED_URL, json=payload, headers=_cohere_headers())
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()
        if attempt == max_attempts - 1:
            resp.raise_for_status()
        retry_after = float(resp.headers.get("Retry-After", delay))
        wait = max(retry_after, delay)
        logger.warning("Cohere 429 — retrying in %.1fs (attempt %d/%d)", wait, attempt + 1, max_attempts)
        await asyncio.sleep(wait)
        delay *= 2
    raise RuntimeError("Cohere embed: exhausted retries")  # unreachable


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
        data = await _cohere_post(http, payload)

    embed_data = data.get("embeddings", {})
    embeddings = embed_data.get("float") if isinstance(embed_data, dict) else embed_data
    if not embeddings:
        raise ValueError("Cohere embed API returned no embeddings")
    return embeddings[0] if isinstance(embeddings[0], list) else embeddings


async def _describe_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str | None:
    """Generate a short text description of an image using OpenAI Vision.

    The description is stored alongside the vector embedding so keyword-based
    (FTS + trigram) search can find images that a pure semantic query might miss.
    Falls back gracefully to None when OPENAI_API_KEY is absent or the call fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("OPENAI_API_KEY not set — skipping image description generation")
        return None

    import openai
    b64 = base64.b64encode(image_bytes).decode()
    client = openai.AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image concisely for search indexing. "
                            "Include all visible objects, on-screen text, colors, people, "
                            "setting, and the overall concept or purpose. Keep it under 100 words."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                ],
            }],
            max_tokens=150,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("Image description via OpenAI Vision failed: %s", exc)
        return None


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
        data = await _cohere_post(http, payload)

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
    site_id = site_id.upper()
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    try:
        query_embedding = await embed_text_query(query)
    except Exception as exc:
        logger.warning("Failed to embed query %r: %s", query, exc)
        return {"success": False, "error": str(exc), "query": query}

    embedding_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Hybrid query: cosine similarity (70%) + FTS ts_rank (30%) with trigram fallback.
    # The inner query gathers candidates via any match method; the outer query enforces
    # the minimum hybrid score so low-quality FTS/trigram hits are still excluded.
    sql = text(f"""
        WITH fts AS (
            SELECT plainto_tsquery('english', :query) AS q
        )
        SELECT item_id, item_name, media_path, alt_text, score
        FROM (
            SELECT ie.item_id, ie.item_name, ie.media_path, ie.alt_text,
                   ROUND((
                       (1 - (ie.embedding <=> '{embedding_literal}'::vector)) * 0.7 +
                       COALESCE(ts_rank(ie.search_vector, fts.q), 0.0) * 0.3
                   )::numeric, 4) AS score
            FROM image_embeddings ie, fts
            WHERE ie.site_id    = :site_id
              AND ie.collection  = :collection
              AND ie.environment = :environment
              AND (
                (1 - (ie.embedding <=> '{embedding_literal}'::vector)) >= :threshold
                OR (ie.search_vector IS NOT NULL AND ie.search_vector @@ fts.q)
                OR (ie.description  IS NOT NULL AND ie.description % :query)
              )
        ) candidates
        WHERE score >= :threshold
        ORDER BY score DESC
        LIMIT :limit
    """)

    try:
        result = await db.execute(sql, {
            "site_id": site_id,
            "collection": collection,
            "environment": environment,
            "query": query,
            "threshold": _SCORE_THRESHOLD,
            "limit": limit,
        })
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("pgvector hybrid search failed: %s", exc)
        return {"success": False, "error": str(exc), "query": query}

    logger.info(
        "Hybrid search %r — %d results above score threshold %.2f",
        query, len(rows), _SCORE_THRESHOLD,
    )
    results = [
        {
            "item_id": row[0],
            "item_name": row[1],
            "media_path": row[2],
            "media_url": f"{cm_host}/-/media/{row[2].lstrip('/')}.ashx" if cm_host else None,
            "alt_text": row[3],
            "score": float(row[4]),  # hybrid score from outer query
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
    description: str | None = None,
) -> None:
    """Insert or update an image embedding row (upsert on item_id+environment+site_id).

    `description` is the image-to-text caption generated at index time; it is used
    to build a tsvector column for full-text + trigram keyword search.
    """
    site_id = site_id.upper()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Inline the vector literal — SQLAlchemy's text() cannot handle :param::vector
    # because the :: cast confuses the named-parameter parser.
    embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    # Build the FTS input in Python to avoid asyncpg AmbiguousParameterError.
    # Reusing the same named parameter in both a VALUES slot and to_tsvector() causes
    # asyncpg to infer conflicting types (varchar vs text) for the same positional $N.
    fts_input = " ".join(filter(None, [description or "", alt_text or "", item_name]))
    sql = text(f"""
        INSERT INTO image_embeddings
            (item_id, environment, site_id, collection, media_path, item_name, alt_text,
             description, search_vector, embedding, indexed_at, updated_at)
        VALUES
            (:item_id, :environment, :site_id, :collection, :media_path, :item_name, :alt_text,
             :description,
             to_tsvector('english', :fts_input),
             '{embedding_literal}'::vector, :now, :now)
        ON CONFLICT (item_id, environment, site_id)
        DO UPDATE SET
            media_path    = EXCLUDED.media_path,
            item_name     = EXCLUDED.item_name,
            alt_text      = EXCLUDED.alt_text,
            description   = EXCLUDED.description,
            search_vector = EXCLUDED.search_vector,
            embedding     = EXCLUDED.embedding,
            updated_at    = EXCLUDED.updated_at
    """)
    await db.execute(sql, {
        "item_id": item_id,
        "environment": environment,
        "site_id": site_id,
        "collection": collection,
        "media_path": media_path,
        "item_name": item_name,
        "alt_text": alt_text,
        "description": description,
        "fts_input": fts_input,
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

    # Generate text description in parallel with the upsert; failure is non-fatal.
    description = await _describe_image(image_bytes, mime_type=mime)
    if description:
        logger.debug("Generated description for %s: %s", item_id, description[:80])

    await upsert_image_embedding(
        item_id=item_id,
        site_id=site_id,
        collection=collection,
        environment=environment,
        media_path=media_path,
        item_name=item_name,
        alt_text=alt_text,
        embedding=embedding,
        description=description,
        db=db,
    )
    return {"success": True, "item_id": item_id, "item_name": item_name}


def _is_image_item(child: dict) -> bool:
    """Return True if a children-endpoint item looks like an image."""
    template_id = child.get("TemplateID", "").upper()
    if template_id in _IMAGE_TEMPLATE_IDS:
        return True
    # TemplateName is included in SSC children responses; fall back to it.
    template_name = child.get("TemplateName", "").lower()
    if template_name == "image":
        return True
    return False


async def _ssc_get_item_by_path(
    http: httpx.AsyncClient,
    ssc_base: str,
    path: str,
    headers: dict,
) -> dict | None:
    """Return the SSC item dict for a Sitecore path, or None if not found."""
    import urllib.parse
    url = f"{ssc_base}/?path={urllib.parse.quote(path)}&database=master"
    try:
        resp = await http.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("SSC get item by path %r failed: %s", path, exc)
        return None


async def _ssc_get_children_page(
    http: httpx.AsyncClient,
    ssc_base: str,
    item_id: str,
    headers: dict,
    skip: int = 0,
    take: int = 50,
) -> list[dict]:
    """Return one page of children for an SSC item ID."""
    url = f"{ssc_base}/{item_id}/children?database=master&skip={skip}&take={take}"
    try:
        resp = await http.get(url, headers=headers)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("SSC get children for %s failed: %s", item_id, exc)
        return []


def _media_url_from_item_path(cm_host: str, item_path: str) -> str:
    """Construct the Sitecore media download URL from an item path.

    SSC item paths look like:
      /sitecore/media library/Project/acme/acme-us/Images/hero.png
    Sitecore serves media at:
      {CM_HOST}/-/media/Project/acme/acme-us/Images/hero.png.ashx
    """
    rel = item_path.replace("/sitecore/media library/", "", 1).lstrip("/")
    return f"{cm_host}/-/media/{rel}.ashx"


async def crawl_and_index_media_library(
    site_id: str,
    collection: str,
    environment: str,
    folder_path: str | None,
    auth_token: str,
    db: AsyncSession,
    batch_limit: int = 100,
    site_name: str | None = None,
) -> dict:
    """Crawl the Sitecore media library via SSC REST API and index images.

    Uses BFS over the SSC item children endpoint to enumerate image items
    (template EAF50F47-D3AC-4364-A0A4-F812D3C5E2E7) under `folder_path`.
    When `folder_path` is None, defaults to the site-specific folder
    `/sitecore/media library/Project/{collection}/{site_name}`.

    Returns {success, indexed_count, failed_count, total_found, batch_limited}.
    """
    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        return {"success": False, "error": "SITECORE_CM_HOST is not set"}

    if folder_path:
        root_path = folder_path
    elif collection and site_name:
        root_path = f"/sitecore/media library/Project/{collection}/{site_name}"
    else:
        root_path = "/sitecore/media library"

    ssc_base = f"{cm_host}{_CM_SSC_ITEM_PATH}"
    ssc_headers = {"Authorization": f"Bearer {auth_token}"}

    indexed = 0
    failed = 0
    total_found = 0

    async with httpx.AsyncClient(timeout=30) as http:
        # Resolve root folder to its item ID
        root_item = await _ssc_get_item_by_path(http, ssc_base, root_path, ssc_headers)
        if not root_item:
            return {
                "success": False,
                "error": f"Media folder not found: {root_path!r}",
                "indexed_count": 0,
                "failed_count": 0,
            }

        logger.info("Crawling media under %r (id=%s)", root_path, root_item.get("ItemID"))

        # BFS over the folder tree
        queue: list[str] = [root_item["ItemID"]]
        while queue:
            folder_id = queue.pop(0)
            skip = 0
            while True:
                children = await _ssc_get_children_page(
                    http, ssc_base, folder_id, ssc_headers, skip=skip, take=50
                )
                if not children:
                    break
                for child in children:
                    if _is_image_item(child):
                        total_found += 1
                        item_id = child["ItemID"]
                        item_name = child.get("ItemName", "")
                        item_path = child.get("ItemPath", "")

                        # Fetch full item to get the real download URL and alt text
                        full_url = f"{ssc_base}/{item_id}?database=master"
                        try:
                            fr = await http.get(full_url, headers=ssc_headers)
                            fr.raise_for_status()
                            full = fr.json()
                        except Exception as exc:
                            logger.warning("Could not fetch full item %s: %s", item_id, exc)
                            full = {}

                        # SSC returns "ItemMedialUrl" (typo is intentional in the API)
                        medial_url = full.get("ItemMedialUrl", "")
                        alt_text = full.get("Alt") or None
                        if medial_url:
                            # Construct absolute URL from the relative medial URL
                            image_url = f"{cm_host}{medial_url}" if medial_url.startswith("/") else medial_url
                        else:
                            image_url = _media_url_from_item_path(cm_host, item_path)
                        media_path = item_path.replace("/sitecore/media library", "", 1)

                        result = await index_image_from_url(
                            item_id=item_id,
                            site_id=site_id,
                            collection=collection,
                            environment=environment,
                            media_path=media_path,
                            item_name=item_name,
                            alt_text=alt_text,
                            image_url=image_url,
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
                                "total_found": total_found,
                                "batch_limited": True,
                            }
                    else:
                        # Treat as potential sub-folder — add to BFS queue
                        queue.append(child["ItemID"])

                if len(children) < 50:
                    break  # last page
                skip += 50

    return {
        "success": True,
        "indexed_count": indexed,
        "failed_count": failed,
        "total_found": total_found,
        "batch_limited": False,
    }
