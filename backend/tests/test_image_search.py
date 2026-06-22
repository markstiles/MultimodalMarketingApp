"""Unit tests for image search service and LangChain tool wrappers.

These tests mock Cohere API, httpx downloads, and the DB session so the full
suite runs without any external dependencies.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_cohere_response(embedding: list[float]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "embeddings": {"float": [embedding]},
    }
    return resp


def _make_db():
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


# ---------------------------------------------------------------------------
# embed_text_query
# ---------------------------------------------------------------------------

class TestEmbedTextQuery:
    async def test_returns_vector_from_cohere(self, monkeypatch):
        from app.services.image_search_service import embed_text_query

        embedding = [0.1] * 1024
        mock_resp = _mock_cohere_response(embedding)

        async def fake_post(url, json, headers):
            return mock_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        with patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_client):
            result = await embed_text_query("construction workers on site")

        assert len(result) == 1024
        assert result[0] == pytest.approx(0.1)

    async def test_raises_on_empty_embeddings(self, monkeypatch):
        from app.services.image_search_service import embed_text_query

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"embeddings": {"float": []}}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        with patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="no embeddings"):
                await embed_text_query("test query")

    async def test_raises_when_api_key_missing(self, monkeypatch):
        from app.services.image_search_service import embed_text_query

        monkeypatch.delenv("COHERE_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="COHERE_API_KEY"):
            await embed_text_query("any query")


# ---------------------------------------------------------------------------
# embed_image
# ---------------------------------------------------------------------------

class TestEmbedImage:
    async def test_returns_vector_for_image_bytes(self, monkeypatch):
        from app.services.image_search_service import embed_image

        embedding = [0.2] * 1024
        mock_resp = _mock_cohere_response(embedding)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        with patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_client):
            result = await embed_image(b"\xff\xd8\xff")  # minimal JPEG header

        assert len(result) == 1024

    async def test_uses_data_uri_in_payload(self, monkeypatch):
        import base64
        from app.services.image_search_service import embed_image

        image_bytes = b"fake-image-data"
        expected_b64 = base64.b64encode(image_bytes).decode()

        captured = {}

        async def capture_post(url, json, headers):
            captured["payload"] = json
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"embeddings": {"float": [[0.1] * 1024]}}
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = capture_post

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        with patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_client):
            await embed_image(image_bytes, mime_type="image/png")

        assert "images" in captured["payload"]
        data_uri = captured["payload"]["images"][0]
        assert data_uri.startswith("data:image/png;base64,")
        assert expected_b64 in data_uri


# ---------------------------------------------------------------------------
# search_images
# ---------------------------------------------------------------------------

class TestSearchImages:
    async def test_returns_ranked_results(self, monkeypatch):
        from app.services.image_search_service import search_images

        embedding = [0.1] * 1024
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        db = _make_db()
        row1 = ("item-001", "hero-image", "/media/hero.jpg", "Construction team", 0.92)
        row2 = ("item-002", "banner",     "/media/banner.jpg", None,              0.78)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row1, row2]
        db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.image_search_service.embed_text_query",
            AsyncMock(return_value=embedding),
        ):
            result = await search_images(
                query="construction team",
                site_id="site-001",
                collection="acme",
                environment="master",
                db=db,
            )

        assert result["success"] is True
        assert result["count"] == 2
        assert result["results"][0]["item_id"] == "item-001"
        assert result["results"][0]["score"] == pytest.approx(0.92)
        assert result["results"][1]["alt_text"] is None

    async def test_returns_error_on_embed_failure(self, monkeypatch):
        from app.services.image_search_service import search_images

        db = _make_db()
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        with patch(
            "app.services.image_search_service.embed_text_query",
            AsyncMock(side_effect=RuntimeError("Cohere down")),
        ):
            result = await search_images(
                query="test",
                site_id="s",
                collection="c",
                environment="master",
                db=db,
            )

        assert result["success"] is False
        assert "Cohere down" in result["error"]

    async def test_returns_empty_results_gracefully(self, monkeypatch):
        from app.services.image_search_service import search_images

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        db = _make_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.image_search_service.embed_text_query",
            AsyncMock(return_value=[0.0] * 1024),
        ):
            result = await search_images(
                query="very obscure query",
                site_id="site-001",
                collection="acme",
                environment="master",
                db=db,
            )

        assert result["success"] is True
        assert result["count"] == 0
        assert result["results"] == []


# ---------------------------------------------------------------------------
# upsert_image_embedding
# ---------------------------------------------------------------------------

class TestUpsertImageEmbedding:
    async def test_executes_upsert_sql(self):
        from app.services.image_search_service import upsert_image_embedding

        db = _make_db()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        await upsert_image_embedding(
            item_id="item-001",
            site_id="site-001",
            collection="acme",
            environment="master",
            media_path="/media/hero.jpg",
            item_name="hero-image",
            alt_text="Team on job site",
            embedding=[0.5] * 1024,
            db=db,
        )

        db.execute.assert_called_once()
        db.commit.assert_called_once()
        sql_call = db.execute.call_args[0][0]
        assert "ON CONFLICT" in str(sql_call)


# ---------------------------------------------------------------------------
# index_image_from_url
# ---------------------------------------------------------------------------

class TestIndexImageFromUrl:
    async def test_downloads_embeds_and_upserts(self, monkeypatch):
        from app.services.image_search_service import index_image_from_url

        monkeypatch.setenv("COHERE_API_KEY", "test-key")
        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")

        fake_image_bytes = b"\xff\xd8\xff"  # JPEG header
        mock_img_resp = MagicMock()
        mock_img_resp.raise_for_status = MagicMock()
        mock_img_resp.content = fake_image_bytes
        mock_img_resp.headers = {"content-type": "image/jpeg"}

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_img_resp)

        db = _make_db()

        with (
            patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_http_client),
            patch(
                "app.services.image_search_service.embed_image",
                AsyncMock(return_value=[0.3] * 1024),
            ),
            patch("app.services.image_search_service.upsert_image_embedding", AsyncMock()),
        ):
            result = await index_image_from_url(
                item_id="item-001",
                site_id="site-001",
                collection="acme",
                environment="master",
                media_path="/media/hero.jpg",
                item_name="hero-image",
                alt_text=None,
                image_url="/media/hero.jpg",
                auth_token="tok",
                db=db,
            )

        assert result["success"] is True
        assert result["item_id"] == "item-001"

    async def test_returns_error_on_download_failure(self, monkeypatch):
        from app.services.image_search_service import index_image_from_url

        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(side_effect=Exception("network error"))

        db = _make_db()

        with patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_http_client):
            result = await index_image_from_url(
                item_id="item-999",
                site_id="site-001",
                collection="acme",
                environment="master",
                media_path="/media/broken.jpg",
                item_name="broken",
                alt_text=None,
                image_url="/media/broken.jpg",
                auth_token="tok",
                db=db,
            )

        assert result["success"] is False
        assert "Download failed" in result["error"]


# ---------------------------------------------------------------------------
# crawl_and_index_media_library
# ---------------------------------------------------------------------------

class TestCrawlAndIndexMediaLibrary:
    def _gql_page(self, items: list[dict], has_next: bool, cursor: str = "") -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": {
                "search": {
                    "total": len(items),
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                    "results": items,
                }
            }
        }
        return resp

    async def test_indexes_items_from_single_page(self, monkeypatch):
        from app.services.image_search_service import crawl_and_index_media_library

        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        items = [
            {"id": "item-001", "name": "hero", "url": {"path": "/media/hero.jpg"}, "field": {"value": "alt text"}},
            {"id": "item-002", "name": "banner", "url": {"path": "/media/banner.jpg"}, "field": None},
        ]
        gql_resp = self._gql_page(items, has_next=False)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=gql_resp)

        db = _make_db()

        with (
            patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.image_search_service.index_image_from_url",
                AsyncMock(return_value={"success": True, "item_id": "x", "item_name": "x"}),
            ),
        ):
            result = await crawl_and_index_media_library(
                site_id="site-001",
                collection="acme",
                environment="master",
                folder_path=None,
                auth_token="tok",
                db=db,
                batch_limit=100,
            )

        assert result["success"] is True
        assert result["indexed_count"] == 2
        assert result["failed_count"] == 0
        assert result["batch_limited"] is False

    async def test_stops_at_batch_limit(self, monkeypatch):
        from app.services.image_search_service import crawl_and_index_media_library

        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        items = [
            {"id": f"item-{i:03d}", "name": f"img{i}", "url": {"path": f"/media/{i}.jpg"}, "field": None}
            for i in range(10)
        ]
        gql_resp = self._gql_page(items, has_next=True, cursor="cursor-abc")

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=gql_resp)

        db = _make_db()

        with (
            patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.image_search_service.index_image_from_url",
                AsyncMock(return_value={"success": True, "item_id": "x", "item_name": "x"}),
            ),
        ):
            result = await crawl_and_index_media_library(
                site_id="site-001",
                collection="acme",
                environment="master",
                folder_path=None,
                auth_token="tok",
                db=db,
                batch_limit=3,
            )

        assert result["success"] is True
        assert result["indexed_count"] == 3
        assert result["batch_limited"] is True

    async def test_returns_error_when_cm_host_missing(self, monkeypatch):
        from app.services.image_search_service import crawl_and_index_media_library

        monkeypatch.delenv("SITECORE_CM_HOST", raising=False)
        db = _make_db()
        result = await crawl_and_index_media_library(
            site_id="s",
            collection="c",
            environment="master",
            folder_path=None,
            auth_token="tok",
            db=db,
        )
        assert result["success"] is False
        assert "SITECORE_CM_HOST" in result["error"]

    async def test_counts_failed_items(self, monkeypatch):
        from app.services.image_search_service import crawl_and_index_media_library

        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")
        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        items = [
            {"id": "item-001", "name": "hero", "url": {"path": "/media/hero.jpg"}, "field": None},
            # missing id — will be counted as failed
            {"id": "", "name": "bad", "url": {"path": ""}, "field": None},
        ]
        gql_resp = self._gql_page(items, has_next=False)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=gql_resp)

        db = _make_db()

        with (
            patch("app.services.image_search_service.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.image_search_service.index_image_from_url",
                AsyncMock(return_value={"success": True, "item_id": "item-001", "item_name": "hero"}),
            ),
        ):
            result = await crawl_and_index_media_library(
                site_id="site-001",
                collection="acme",
                environment="master",
                folder_path=None,
                auth_token="tok",
                db=db,
                batch_limit=100,
            )

        assert result["indexed_count"] == 1
        assert result["failed_count"] == 1


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

class TestSearchSiteImagesTool:
    async def test_returns_results_from_service(self, monkeypatch):
        """Tool resolves site info and calls search_images from the service."""
        from app.clients.image_search import search_site_images

        monkeypatch.setenv("COHERE_API_KEY", "test-key")

        mock_db = _make_db()
        mock_session_factory = MagicMock(return_value=mock_db)

        service_result = {
            "success": True,
            "query": "construction workers",
            "results": [{"item_id": "i1", "item_name": "img", "media_path": "/m/i.jpg", "alt_text": None, "score": 0.9}],
            "count": 1,
        }

        with (
            patch(
                "app.clients.image_search.get_sitecore_automation_token",
                AsyncMock(return_value="test-token"),
            ),
            patch(
                "app.clients.image_search.get_site_info",
                AsyncMock(return_value={"success": True, "collection": "acme"}),
            ),
            patch("app.resources.database._get_session_factory", return_value=mock_session_factory),
            patch(
                "app.services.image_search_service.search_images",
                AsyncMock(return_value=service_result),
            ),
        ):
            result = await search_site_images.ainvoke({
                "query": "construction workers",
                "site_id": "site-001",
            })

        assert result["success"] is True
        assert result["count"] == 1

    async def test_returns_error_on_auth_failure(self, monkeypatch):
        from app.clients.image_search import search_site_images

        with patch(
            "app.clients.image_search.get_sitecore_automation_token",
            AsyncMock(side_effect=RuntimeError("No credentials")),
        ):
            result = await search_site_images.ainvoke({
                "query": "test",
                "site_id": "site-001",
            })

        assert result["success"] is False
        assert "No credentials" in result["error"]

    async def test_returns_error_when_site_not_found(self, monkeypatch):
        from app.clients.image_search import search_site_images

        with (
            patch(
                "app.clients.image_search.get_sitecore_automation_token",
                AsyncMock(return_value="tok"),
            ),
            patch(
                "app.clients.image_search.get_site_info",
                AsyncMock(return_value={"success": False, "error": "Site not found"}),
            ),
        ):
            result = await search_site_images.ainvoke({
                "query": "test",
                "site_id": "unknown-site",
            })

        assert result["success"] is False
        assert "Site not found" in result["error"]


class TestIndexMediaLibraryImagesTool:
    async def test_delegates_to_crawl_service(self, monkeypatch):
        from app.clients.image_search import index_media_library_images

        mock_db = _make_db()
        mock_session_factory = MagicMock(return_value=mock_db)

        crawl_result = {
            "success": True,
            "indexed_count": 10,
            "failed_count": 0,
            "skipped_count": 0,
            "total_found": 10,
            "batch_limited": False,
        }

        with (
            patch(
                "app.clients.image_search.get_sitecore_automation_token",
                AsyncMock(return_value="tok"),
            ),
            patch(
                "app.clients.image_search.get_site_info",
                AsyncMock(return_value={"success": True, "collection": "acme"}),
            ),
            patch("app.resources.database._get_session_factory", return_value=mock_session_factory),
            patch(
                "app.services.image_search_service.crawl_and_index_media_library",
                AsyncMock(return_value=crawl_result),
            ),
        ):
            result = await index_media_library_images.ainvoke({
                "site_id": "site-001",
                "batch_limit": 10,
            })

        assert result["success"] is True
        assert result["indexed_count"] == 10
