"""Unit tests for pages_api @tool functions and pages_service helpers."""
from unittest.mock import AsyncMock, patch

import pytest
import httpx

# LangChain's ainvoke uses asyncio.gather internally — trio backend is incompatible.
pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ── search_pages ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_search_pages_returns_results():
    mock_result = {
        "success": True,
        "pages": [
            {"page_id": "abc", "display_name": "Summer Campaign", "parent_path": "/Blog",
             "template_name": "Blog Post", "is_folder": False, "site_id": "site1"},
        ],
        "total_count": 1,
        "has_more": False,
        "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.search_pages_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import search_pages
        result = await search_pages.ainvoke(
            {"site_id": "site1", "environment": "env1", "query": "campaign", "language": "en"}
        )
    assert result["success"] is True
    assert len(result["pages"]) == 1
    assert result["pages"][0]["display_name"] == "Summer Campaign"


@pytest.mark.anyio
async def test_search_pages_auth_failure():
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock,
               side_effect=RuntimeError("creds missing")):
        from app.clients.pages_api import search_pages
        result = await search_pages.ainvoke(
            {"site_id": "site1", "environment": "env1", "query": "test", "language": "en"}
        )
    assert result["success"] is False
    assert "creds missing" in result["error"]


# ── get_insert_options ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_insert_options_returns_templates():
    mock_result = {
        "success": True,
        "insert_options": [{"template_id": "t1", "template_name": "Blog Post"}],
        "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.get_insert_options_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import get_insert_options
        result = await get_insert_options.ainvoke(
            {"site_id": "s1", "environment": "e1", "parent_page_id": "parent1"}
        )
    assert result["success"] is True
    assert result["insert_options"][0]["template_name"] == "Blog Post"


@pytest.mark.anyio
async def test_get_insert_options_empty_list():
    mock_result = {"success": True, "insert_options": [], "error": None}
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.get_insert_options_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import get_insert_options
        result = await get_insert_options.ainvoke(
            {"site_id": "s1", "environment": "e1", "parent_page_id": "leaf-page"}
        )
    assert result["success"] is True
    assert result["insert_options"] == []


# ── create_page ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_page_success():
    mock_result = {
        "success": True, "page_id": "new-page-1", "display_name": "Summer Campaign",
        "version": None, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.create_page_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import create_page
        result = await create_page.ainvoke({
            "site_id": "s1", "environment": "e1", "parent_page_id": "parent1",
            "template_id": "t1", "display_name": "Summer Campaign", "language": "en",
        })
    assert result["success"] is True
    assert result["page_id"] == "new-page-1"


@pytest.mark.anyio
async def test_create_page_api_error():
    mock_result = {
        "success": False, "page_id": None, "display_name": None, "version": None,
        "error": "403 Forbidden",
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.create_page_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import create_page
        result = await create_page.ainvoke({
            "site_id": "s1", "environment": "e1", "parent_page_id": "p1",
            "template_id": "t1", "display_name": "Bad Page", "language": "en",
        })
    assert result["success"] is False
    assert result["error"] == "403 Forbidden"


# ── get_page_state ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_page_state_success():
    mock_result = {
        "success": True, "page_id": "pg1", "display_name": "Homepage",
        "parent_path": "/", "template_name": "Site Root", "language": "en",
        "version": 2, "workflow_state": "Approved", "is_live": True,
        "last_modified": "2026-06-19T10:00:00Z", "site_id": "s1", "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.get_page_state_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import get_page_state
        result = await get_page_state.ainvoke({"site_id": "s1", "environment": "e1", "page_id": "pg1"})
    assert result["success"] is True
    assert result["workflow_state"] == "Approved"
    assert result["is_live"] is True


# ── rename_page ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_rename_page_success():
    mock_result = {
        "success": True, "page_id": "pg1", "display_name": "About Us",
        "version": None, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.rename_page_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import rename_page
        result = await rename_page.ainvoke(
            {"site_id": "s1", "environment": "e1", "page_id": "pg1", "new_display_name": "About Us"}
        )
    assert result["success"] is True
    assert result["display_name"] == "About Us"


# ── duplicate_page ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_duplicate_page_success():
    mock_result = {
        "success": True, "page_id": "pg2", "display_name": "Homepage (Copy)",
        "version": None, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.duplicate_page_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import duplicate_page
        result = await duplicate_page.ainvoke({"site_id": "s1", "environment": "e1", "page_id": "pg1"})
    assert result["success"] is True
    assert result["page_id"] == "pg2"


# ── update_page_fields ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_update_page_fields_success():
    mock_result = {
        "success": True, "page_id": "pg1", "display_name": None, "version": None, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.update_page_fields_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import update_page_fields
        result = await update_page_fields.ainvoke({
            "site_id": "s1", "environment": "e1", "page_id": "pg1",
            "fields": {"title": "Summer 2026 Campaign"}, "language": "en",
        })
    assert result["success"] is True


# ── create_page_version ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_page_version_success():
    mock_result = {
        "success": True, "page_id": "pg1", "display_name": None, "version": 3, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.create_page_version_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import create_page_version
        result = await create_page_version.ainvoke(
            {"site_id": "s1", "environment": "e1", "page_id": "pg1", "language": "en"}
        )
    assert result["success"] is True
    assert result["version"] == 3


# ── delete_page ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_delete_page_success():
    mock_result = {
        "success": True, "page_id": None, "display_name": None, "version": None, "error": None,
    }
    with patch("app.clients.pages_api.get_sitecore_automation_token", new_callable=AsyncMock, return_value="tok"), \
         patch("app.clients.pages_api.delete_page_api", new_callable=AsyncMock, return_value=mock_result):
        from app.clients.pages_api import delete_page
        result = await delete_page.ainvoke({"site_id": "s1", "environment": "e1", "page_id": "pg1"})
    assert result["success"] is True
    assert result["page_id"] is None


# ── HTTP contract tests for pages_service.py ─────────────────────────────────
#
# The @tool tests above mock the *_api functions entirely, so a wrong URL or
# wrong request body in pages_service.py would never be caught. These tests
# intercept httpx.AsyncClient at the transport level and assert the exact URL,
# HTTP method, headers, and request body — the same failure mode that caused
# the production 404 in content_workflow_service.py.

class TestPagesServiceHTTP:
    """Validate HTTP calls made by pages_service.py directly (not via @tool wrapper)."""

    def _make_fake_client(self, status_code=200, body=None, raise_exc=None):
        """Return (FakeClientClass, captured_dict).

        FakeClientClass replaces httpx.AsyncClient. After the call, captured
        contains method, url, headers, params, and json from the request.
        """
        captured = {}

        class FakeResponse:
            def __init__(self):
                self.status_code = status_code
                self.text = ""

            def raise_for_status(self):
                if status_code >= 400:
                    req = httpx.Request("GET", "https://example.com")
                    resp = httpx.Response(status_code, content=b"")
                    raise httpx.HTTPStatusError(
                        f"HTTP {status_code}", request=req, response=resp
                    )

            def json(self):
                return body or {}

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, **kwargs):
                if raise_exc:
                    raise raise_exc
                captured["method"] = "GET"
                captured["url"] = url
                captured["headers"] = kwargs.get("headers", {})
                captured["params"] = kwargs.get("params", {})
                return FakeResponse()

            async def post(self, url, **kwargs):
                if raise_exc:
                    raise raise_exc
                captured["method"] = "POST"
                captured["url"] = url
                captured["headers"] = kwargs.get("headers", {})
                captured["json"] = kwargs.get("json", {})
                return FakeResponse()

            async def delete(self, url, **kwargs):
                if raise_exc:
                    raise raise_exc
                captured["method"] = "DELETE"
                captured["url"] = url
                captured["headers"] = kwargs.get("headers", {})
                return FakeResponse()

        return FakeClient, captured

    # ── URL / path correctness ───────────────────────────────────────────────

    async def test_search_pages_url(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        FakeClient, captured = self._make_fake_client(200, {"data": []})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await search_pages_api("site1", "env1", "summer", "en", "tok")

        assert captured["url"].endswith("/search")

    async def test_get_insert_options_url(self, monkeypatch):
        from app.services.pages_service import get_insert_options_api

        FakeClient, captured = self._make_fake_client(200, [])
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await get_insert_options_api("parent-page-id", "tok")

        assert captured["url"].endswith("/parent-page-id/insertoptions")

    async def test_get_page_state_url(self, monkeypatch):
        from app.services.pages_service import get_page_state_api

        FakeClient, captured = self._make_fake_client(200, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await get_page_state_api("page-abc", "tok")

        assert captured["url"].endswith("/page-abc/state")

    async def test_create_page_posts_to_base_url(self, monkeypatch):
        from app.services.pages_service import create_page_api, _get_base_url

        FakeClient, captured = self._make_fake_client(201, {"id": "new-page"})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await create_page_api("site1", "parent1", "tmpl1", "My Page", "en", "tok")

        assert captured["url"] == _get_base_url()

    async def test_rename_page_url(self, monkeypatch):
        from app.services.pages_service import rename_page_api

        FakeClient, captured = self._make_fake_client(200, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await rename_page_api("page-xyz", "New Name", "tok")

        assert captured["url"].endswith("/page-xyz/rename")

    async def test_duplicate_page_url(self, monkeypatch):
        from app.services.pages_service import duplicate_page_api

        FakeClient, captured = self._make_fake_client(201, {"id": "pg-copy"})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await duplicate_page_api("page-xyz", "tok")

        assert captured["url"].endswith("/page-xyz/duplicate")

    async def test_update_page_fields_url(self, monkeypatch):
        from app.services.pages_service import update_page_fields_api

        FakeClient, captured = self._make_fake_client(200, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await update_page_fields_api("page-xyz", {"title": "v"}, "en", "tok")

        assert captured["url"].endswith("/page-xyz/fields")

    async def test_create_page_version_url(self, monkeypatch):
        from app.services.pages_service import create_page_version_api

        FakeClient, captured = self._make_fake_client(201, {"version": 2})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await create_page_version_api("page-xyz", "en", "tok")

        assert captured["url"].endswith("/page-xyz/version")

    async def test_delete_page_url_and_method(self, monkeypatch):
        from app.services.pages_service import delete_page_api

        FakeClient, captured = self._make_fake_client(204, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await delete_page_api("page-xyz", "tok")

        assert captured["method"] == "DELETE"
        assert captured["url"].endswith("/page-xyz")

    # ── Request body correctness ─────────────────────────────────────────────

    async def test_search_pages_query_params(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        FakeClient, captured = self._make_fake_client(200, {"data": []})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await search_pages_api("site-1", "env1", "campaign", "en", "tok")

        params = captured["params"]
        assert params.get("siteId") == "site-1"
        assert params.get("search") == "campaign"
        assert params.get("language") == "en"

    async def test_create_page_body_fields(self, monkeypatch):
        from app.services.pages_service import create_page_api

        FakeClient, captured = self._make_fake_client(201, {"id": "new-page"})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await create_page_api("s1", "parent1", "tmpl1", "Summer Campaign", "en", "tok")

        body = captured["json"]
        assert body["site"] == "s1"
        assert body["parent"] == "parent1"
        assert body["template"] == "tmpl1"
        assert body["displayName"] == "Summer Campaign"
        assert body["language"] == "en"

    async def test_rename_page_body_uses_display_name(self, monkeypatch):
        from app.services.pages_service import rename_page_api

        FakeClient, captured = self._make_fake_client(200, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await rename_page_api("pg1", "About Us Renamed", "tok")

        assert captured["json"] == {"displayName": "About Us Renamed"}

    async def test_update_page_fields_body(self, monkeypatch):
        from app.services.pages_service import update_page_fields_api

        FakeClient, captured = self._make_fake_client(200, {})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await update_page_fields_api("pg1", {"title": "New Title", "body": "Text"}, "fr", "tok")

        body = captured["json"]
        assert body["fields"] == {"title": "New Title", "body": "Text"}
        assert body["language"] == "fr"

    async def test_create_page_version_body_includes_language(self, monkeypatch):
        from app.services.pages_service import create_page_version_api

        FakeClient, captured = self._make_fake_client(201, {"version": 3})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await create_page_version_api("pg1", "de", "tok")

        assert captured["json"] == {"language": "de"}

    # ── Auth header ───────────────────────────────────────────────────────────

    async def test_bearer_token_in_auth_header(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        FakeClient, captured = self._make_fake_client(200, {"data": []})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await search_pages_api("s1", "e1", "q", "en", "my-secret-token")

        assert captured["headers"].get("Authorization") == "Bearer my-secret-token"

    # ── Base URL resolution ───────────────────────────────────────────────────

    async def test_default_base_url_is_xmapps_api(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        monkeypatch.delenv("SITECORE_PAGES_API_BASE_URL", raising=False)
        FakeClient, captured = self._make_fake_client(200, {"data": []})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await search_pages_api("s1", "e1", "q", "en", "tok")

        assert "xmapps-api.sitecorecloud.io" in captured["url"]

    async def test_env_var_overrides_base_url(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        monkeypatch.setenv("SITECORE_PAGES_API_BASE_URL", "https://custom-pages.example.com/api/v2/pages")
        FakeClient, captured = self._make_fake_client(200, {"data": []})
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        await search_pages_api("s1", "e1", "q", "en", "tok")

        assert "custom-pages.example.com" in captured["url"]

    # ── Error handling ────────────────────────────────────────────────────────

    async def test_http_error_returns_failure(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        FakeClient, _captured = self._make_fake_client(403)
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        result = await search_pages_api("s1", "e1", "q", "en", "tok")

        assert result["success"] is False
        assert "403" in result["error"]

    async def test_network_error_returns_failure(self, monkeypatch):
        from app.services.pages_service import search_pages_api

        FakeClient, _captured = self._make_fake_client(
            raise_exc=httpx.ConnectError("connection refused")
        )
        monkeypatch.setattr("app.services.pages_service.httpx.AsyncClient", FakeClient)

        result = await search_pages_api("s1", "e1", "q", "en", "tok")

        assert result["success"] is False
        assert result["error"] is not None
