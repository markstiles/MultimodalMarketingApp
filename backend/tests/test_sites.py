"""Tests for sites_service.py and sites.py client tools."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_cache():
    from app.services.sites_service import _clear_site_cache
    _clear_site_cache()
    yield
    _clear_site_cache()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_http(status: int, body, raise_exc=None):
    """Return a context-manager-compatible httpx.AsyncClient mock."""
    resp = MagicMock()
    resp.status_code = status
    resp.is_success = 200 <= status < 300
    if isinstance(body, dict) or isinstance(body, list):
        resp.json = lambda: body
        resp.content = b"data"
    else:
        resp.json = MagicMock(side_effect=ValueError("not json"))
        resp.content = body.encode() if isinstance(body, str) else b""
    resp.raise_for_status = MagicMock(
        side_effect=None if resp.is_success else Exception(f"HTTP {status}")
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    if raise_exc:
        mock_client.get = AsyncMock(side_effect=raise_exc)
        mock_client.post = AsyncMock(side_effect=raise_exc)
    else:
        mock_client.get = AsyncMock(return_value=resp)
        mock_client.post = AsyncMock(return_value=resp)

    return mock_client


# ── get_site_info ─────────────────────────────────────────────────────────────

class TestGetSiteInfo:
    async def test_success_string_collection(self):
        from app.services.sites_service import get_site_info

        body = {"id": "site-123", "name": "acme-us", "collection": "acme-corp"}
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_info("site-123", "tok")

        assert result["success"] is True
        assert result["name"] == "acme-us"
        assert result["collection"] == "acme-corp"

    async def test_success_nested_site_collection(self):
        from app.services.sites_service import get_site_info

        body = {"id": "site-456", "name": "eu-site", "siteCollection": {"id": "c1", "name": "eu-corp"}}
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_info("site-456", "tok")

        assert result["success"] is True
        assert result["collection"] == "eu-corp"

    async def test_site_not_found(self):
        from app.services.sites_service import get_site_info

        mock = _mock_http(404, "not found")
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_info("missing", "tok")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    async def test_result_is_cached(self):
        from app.services.sites_service import get_site_info

        body = {"id": "s", "name": "my-site", "collection": "my-col"}
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            r1 = await get_site_info("s", "tok")
            r2 = await get_site_info("s", "tok")

        assert r1 == r2
        assert mock.get.call_count == 1  # second call hit the cache

    async def test_timeout_returns_error(self):
        import httpx
        from app.services.sites_service import get_site_info

        mock = _mock_http(0, "", raise_exc=httpx.TimeoutException("timeout"))
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_info("s", "tok")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()


# ── get_site_languages ────────────────────────────────────────────────────────

class TestGetSiteLanguages:
    async def test_list_of_objects(self):
        from app.services.sites_service import get_site_languages

        body = [{"isoCode": "en", "displayName": "English"}, {"isoCode": "fr-FR", "displayName": "French"}]
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("s", "tok")

        assert result["success"] is True
        assert result["count"] == 2
        assert result["languages"][0]["isoCode"] == "en"
        assert result["languages"][1]["isoCode"] == "fr-FR"

    async def test_list_of_strings_normalized(self):
        from app.services.sites_service import get_site_languages

        mock = _mock_http(200, ["en", "de-DE", "ja-JP"])
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("s", "tok")

        assert result["success"] is True
        assert result["count"] == 3
        codes = [lang["isoCode"] for lang in result["languages"]]
        assert codes == ["en", "de-DE", "ja-JP"]

    async def test_wrapped_in_data_key(self):
        from app.services.sites_service import get_site_languages

        body = {"data": [{"isoCode": "en"}, {"isoCode": "es-MX"}]}
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("s", "tok")

        assert result["success"] is True
        assert result["count"] == 2

    async def test_objects_without_iso_code_normalized(self):
        from app.services.sites_service import get_site_languages

        body = [{"language": "fr-FR", "englishName": "French (France)"}]
        mock = _mock_http(200, body)
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("s", "tok")

        assert result["languages"][0]["isoCode"] == "fr-FR"

    async def test_site_not_found(self):
        from app.services.sites_service import get_site_languages

        mock = _mock_http(404, "not found")
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("missing", "tok")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    async def test_timeout_returns_error(self):
        import httpx
        from app.services.sites_service import get_site_languages

        mock = _mock_http(0, "", raise_exc=httpx.TimeoutException("timeout"))
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await get_site_languages("s", "tok")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()


# ── add_site_language ─────────────────────────────────────────────────────────

class TestAddSiteLanguage:
    async def test_success(self):
        from app.services.sites_service import add_site_language

        mock = _mock_http(201, {"language": "fr-FR"})
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await add_site_language("s", "fr-FR", "tok")

        assert result["success"] is True
        assert result["language"] == "fr-FR"
        assert result["site_id"] == "s"

    async def test_already_exists_returns_descriptive_error(self):
        from app.services.sites_service import add_site_language

        mock = _mock_http(409, "conflict")
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await add_site_language("s", "en", "tok")

        assert result["success"] is False
        assert "already exists" in result["error"]
        assert "en" in result["error"]

    async def test_site_not_found(self):
        from app.services.sites_service import add_site_language

        mock = _mock_http(404, "not found")
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await add_site_language("missing", "fr-FR", "tok")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    async def test_timeout_returns_error(self):
        import httpx
        from app.services.sites_service import add_site_language

        mock = _mock_http(0, "", raise_exc=httpx.TimeoutException("timeout"))
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            result = await add_site_language("s", "fr-FR", "tok")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    async def test_post_body_sends_language_key(self):
        from app.services.sites_service import add_site_language

        mock = _mock_http(201, {})
        with patch("app.services.sites_service.httpx.AsyncClient", return_value=mock):
            await add_site_language("my-site", "de-DE", "tok")

        call_kwargs = mock.post.call_args[1]
        assert call_kwargs["json"] == {"language": "de-DE"}


# ── @tool wrappers ────────────────────────────────────────────────────────────

class TestListSiteLanguagesTool:
    async def test_success_path(self, monkeypatch):
        from app.clients.sites import list_site_languages

        async def _fake_token():
            return "tok"

        async def _fake_get_languages(site_id, auth_token):
            return {
                "success": True,
                "site_id": site_id,
                "languages": [{"isoCode": "en"}, {"isoCode": "fr-FR"}],
                "count": 2,
            }

        monkeypatch.setattr("app.clients.sites.get_sitecore_automation_token", _fake_token)
        monkeypatch.setattr("app.clients.sites._svc_get_languages", _fake_get_languages)

        result = await list_site_languages.ainvoke({"site_id": "stub-id"})
        assert result["success"] is True
        assert result["count"] == 2
        codes = [lang["isoCode"] for lang in result["languages"]]
        assert "en" in codes and "fr-FR" in codes

    async def test_auth_failure(self, monkeypatch):
        from app.clients.sites import list_site_languages

        async def _fail_token():
            raise RuntimeError("Missing credentials")

        monkeypatch.setattr("app.clients.sites.get_sitecore_automation_token", _fail_token)

        result = await list_site_languages.ainvoke({"site_id": "stub-id"})
        assert result["success"] is False
        assert "Missing credentials" in result["error"]


class TestAddLanguageToSiteTool:
    async def test_success_path(self, monkeypatch):
        from app.clients.sites import add_language_to_site

        async def _fake_token():
            return "tok"

        async def _fake_add(site_id, language, auth_token):
            return {"success": True, "site_id": site_id, "language": language, "data": {}}

        monkeypatch.setattr("app.clients.sites.get_sitecore_automation_token", _fake_token)
        monkeypatch.setattr("app.clients.sites._svc_add_language", _fake_add)

        result = await add_language_to_site.ainvoke({"site_id": "stub-id", "language": "fr-FR"})
        assert result["success"] is True
        assert result["language"] == "fr-FR"

    async def test_conflict_error_propagated(self, monkeypatch):
        from app.clients.sites import add_language_to_site

        async def _fake_token():
            return "tok"

        async def _fake_add(site_id, language, auth_token):
            return {"success": False, "error": f"Language {language!r} already exists on site {site_id!r}"}

        monkeypatch.setattr("app.clients.sites.get_sitecore_automation_token", _fake_token)
        monkeypatch.setattr("app.clients.sites._svc_add_language", _fake_add)

        result = await add_language_to_site.ainvoke({"site_id": "stub-id", "language": "en"})
        assert result["success"] is False
        assert "already exists" in result["error"]

    async def test_auth_failure(self, monkeypatch):
        from app.clients.sites import add_language_to_site

        async def _fail_token():
            raise RuntimeError("Missing credentials")

        monkeypatch.setattr("app.clients.sites.get_sitecore_automation_token", _fail_token)

        result = await add_language_to_site.ainvoke({"site_id": "stub-id", "language": "de-DE"})
        assert result["success"] is False
        assert "Missing credentials" in result["error"]
