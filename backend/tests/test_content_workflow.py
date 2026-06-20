import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# LangChain's ainvoke uses asyncio.gather internally — trio backend is incompatible.
pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestBuildArtifactMediaPath:
    def test_all_six_phases_produce_correct_paths(self):
        from app.services.content_workflow_service import build_artifact_media_path

        cases = {
            "Research": "research-brief.docx",
            "Strategy": "content-strategy.docx",
            "Structure": "content-structure.docx",
            "Content": "content-plan.docx",
            "Variation": "variation-plan.docx",
            "Execution": "execution-checklist.docx",
        }
        tenant = "acme-corp"
        site = "us-site"
        for phase, filename in cases.items():
            path = build_artifact_media_path(tenant, site, phase)
            expected = (
                f"/sitecore/Media Library/Project/{tenant}/{site}"
                f"/Content Strategy/{phase}/{filename}"
            )
            assert path == expected, f"Phase {phase}: expected {expected!r}, got {path!r}"

    def test_unknown_phase_raises(self):
        from app.services.content_workflow_service import build_artifact_media_path

        with pytest.raises(ValueError, match="Unknown phase"):
            build_artifact_media_path("t", "s", "Publish")

    def test_tenant_and_site_interpolated(self):
        from app.services.content_workflow_service import build_artifact_media_path

        path = build_artifact_media_path("my-tenant", "my-site", "Content")
        assert "/my-tenant/my-site/" in path


# ── Upload artifact HTTP contract ─────────────────────────────────────────────
#
# These tests exercise upload_artifact_to_media_library directly — NOT via the
# @tool wrapper — so the actual URL, headers, and multipart body are validated.
# This is the layer that produced the production 404 when the URL and request
# format were wrong.

class TestUploadArtifactToMediaLibrary:
    """Validate the HTTP call made by upload_artifact_to_media_library.

    These tests intercept the httpx.AsyncClient at the module level so we can
    assert on the exact URL, headers, and multipart body sent to the Sitecore
    Agent API — the layer that was broken and untested before.
    """

    def _make_fake_client(self, status_code=201, raise_exc=None, resp_text=""):
        """Return (FakeClientClass, captured_dict).

        FakeClientClass is a drop-in for httpx.AsyncClient.
        captured_dict is populated when post() is called.
        """
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, **kwargs):
                if raise_exc:
                    raise raise_exc
                captured["url"] = url
                captured["headers"] = kwargs.get("headers", {})
                captured["data"] = kwargs.get("data", {})
                captured["files"] = kwargs.get("files", {})
                resp = MagicMock()
                resp.status_code = status_code
                resp.is_success = 200 <= status_code < 300
                resp.text = resp_text
                return resp

        return FakeClient, captured

    async def test_posts_to_correct_url_path(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("tenant", "site", "Research", b"bytes", "tok")

        assert "/api/v1/assets/upload" in captured["url"]

    async def test_url_does_not_use_old_streaming_path(self, monkeypatch):
        """Regression: old URL was /api/stream/agents/media/upload — always 404."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("tenant", "site", "Research", b"bytes", "tok")

        assert "api/stream/agents" not in captured["url"]
        assert "/media/upload" not in captured["url"]

    async def test_default_base_url_is_ai_agent_api(self, monkeypatch):
        """Without SITECORE_AGENTS_API_BASE_URL set, default must be the REST Agent API."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        monkeypatch.delenv("SITECORE_AGENTS_API_BASE_URL", raising=False)

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("tenant", "site", "Research", b"bytes", "tok")

        assert "stream/ai-agent-api" in captured["url"]

    async def test_upload_request_is_valid_json_string(self, monkeypatch):
        """upload_request field must be a JSON-encoded string, not separate form fields."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        monkeypatch.delenv("SITECORE_PUBLIC_DEFAULT_SITE_NAME", raising=False)

        await upload_artifact_to_media_library("my-tenant", "my-site", "Research", b"bytes", "tok")

        files = captured["files"]
        assert "upload_request" in files, "upload_request field missing from multipart body"
        # upload_request is sent as (None, json_string) — a filename-less multipart part
        parsed = json.loads(files["upload_request"][1])
        assert parsed["name"] == "research-brief"  # extension stripped — item name only
        assert parsed["extension"] == "docx"
        assert parsed["language"] == "en"
        assert parsed["siteName"] == "my-site"  # falls back to site param when env not set
        assert "my-tenant" in parsed["itemPath"]
        assert "Research" in parsed["itemPath"]

    async def test_sitename_uses_env_var_over_site_param(self, monkeypatch):
        """SITECORE_PUBLIC_DEFAULT_SITE_NAME takes priority over the tool's site parameter."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        monkeypatch.setenv("SITECORE_PUBLIC_DEFAULT_SITE_NAME", "real-site-name")
        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("t", "stub-site-id", "Research", b"bytes", "tok")

        parsed = json.loads(captured["files"]["upload_request"][1])
        assert parsed["siteName"] == "real-site-name"  # env var wins

    async def test_upload_request_does_not_use_old_field_names(self, monkeypatch):
        """Regression: old code sent mediaPath/itemName/overwrite — not accepted by the API."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        files = captured["files"]
        assert "upload_request" in files
        upload_req = json.loads(files["upload_request"][1])
        assert "mediaPath" not in upload_req
        assert "itemName" not in upload_req
        assert "overwrite" not in upload_req

    async def test_file_field_has_docx_content_type(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("t", "s", "Research", b"docx-content", "tok")

        files = captured["files"]
        assert "file" in files
        _filename, content, content_type = files["file"]
        assert content == b"docx-content"
        assert "wordprocessingml" in content_type

    async def test_auth_bearer_token_in_header(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client(201)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "my-token")

        assert captured["headers"].get("Authorization") == "Bearer my-token"

    async def test_known_api_bug_400_returns_user_friendly_error(self, monkeypatch):
        """HTTP 400 'upload_request Field required' → docx_generated/upload_unavailable flags."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        known_bug_body = '{"errors":{"(\'body\', \'upload_request\')":"Field required"}}'
        FakeClient, _captured = self._make_fake_client(400, resp_text=known_bug_body)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert result.get("docx_generated") is True
        assert result.get("upload_unavailable") is True
        assert "upload API unavailable" in result["error"]
        # Raw API error must not be surfaced to the user
        assert "Field required" not in result["error"]
        assert "400" not in result["error"]

    async def test_http_error_returns_failure_with_status(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, _captured = self._make_fake_client(404)
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "404" in result["error"]

    async def test_timeout_returns_failure(self, monkeypatch):
        import httpx as _httpx
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, _captured = self._make_fake_client(raise_exc=_httpx.TimeoutException("timeout"))
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    async def test_unknown_phase_returns_failure(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        result = await upload_artifact_to_media_library("t", "s", "Nonexistent", b"bytes", "tok")

        assert result["success"] is False
        assert "Unknown phase" in result["error"]


# ── @tool wrapper tests (mock upload_artifact_to_media_library entirely) ──────

class TestScanContentProjectStatus:
    async def test_all_not_started(self, monkeypatch):
        from app.clients.content_workflow import scan_content_project_status

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            return {"exists": False, "modified_at": None, "age_days": None}

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )

        result = await scan_content_project_status.ainvoke(
            {"tenant": "t", "site": "s"}
        )
        assert result["next_recommended_phase"] == "Research"
        assert result["last_completed_phase"] is None
        assert result["has_stale_phases"] is False
        assert all(p["status"] == "not_started" for p in result["phases"])

    async def test_research_complete(self, monkeypatch):
        from app.clients.content_workflow import scan_content_project_status

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            if phase == "Research":
                return {"exists": True, "modified_at": "2026-01-01T00:00:00+00:00", "age_days": 30}
            return {"exists": False, "modified_at": None, "age_days": None}

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )

        result = await scan_content_project_status.ainvoke(
            {"tenant": "t", "site": "s"}
        )
        research = next(p for p in result["phases"] if p["phase"] == "Research")
        assert research["status"] == "complete"
        assert result["next_recommended_phase"] == "Strategy"
        assert result["last_completed_phase"] == "Research"

    async def test_stale_phase_detected(self, monkeypatch):
        from app.clients.content_workflow import scan_content_project_status

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            if phase == "Research":
                return {"exists": True, "modified_at": "2024-01-01T00:00:00+00:00", "age_days": 400}
            return {"exists": False, "modified_at": None, "age_days": None}

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )

        result = await scan_content_project_status.ainvoke(
            {"tenant": "t", "site": "s"}
        )
        research = next(p for p in result["phases"] if p["phase"] == "Research")
        assert research["status"] == "stale"
        assert result["has_stale_phases"] is True
        assert "Research" in result["stale_phase_names"]

    async def test_auth_failure_returns_error(self, monkeypatch):
        from app.clients.content_workflow import scan_content_project_status

        async def _fail_token():
            raise RuntimeError("Missing credentials")

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fail_token
        )

        result = await scan_content_project_status.ainvoke(
            {"tenant": "t", "site": "s"}
        )
        assert result["success"] is False
        assert "Missing credentials" in result["error"]
        assert result["phases"] == []


class TestSavePhaseArtifact:
    async def test_success_path(self, monkeypatch):
        from app.clients.content_workflow import save_phase_artifact

        async def _fake_token():
            return "tok"

        def _fake_docx(phase, title, tenant, site, sections):
            return b"docx-bytes"

        async def _fake_upload(tenant, site, phase, docx_bytes, auth_token):
            return {
                "success": True,
                "media_path": f"/sitecore/Media Library/Project/{tenant}/{site}/Content Strategy/{phase}/research-brief.docx",
                "overwrite": False,
                "error": None,
            }

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.generate_phase_docx", _fake_docx
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.upload_artifact_to_media_library", _fake_upload
        )

        result = await save_phase_artifact.ainvoke(
            {
                "tenant": "t",
                "site": "s",
                "phase": "Research",
                "title": "Research Brief",
                "content": "## Summary\nContent",
            }
        )
        assert result["success"] is True
        assert result["phase"] == "Research"
        assert result["filename"] == "research-brief.docx"
        assert result["overwrite"] is False
        assert result["error"] is None

    async def test_unknown_phase_error(self, monkeypatch):
        from app.clients.content_workflow import save_phase_artifact

        result = await save_phase_artifact.ainvoke(
            {
                "tenant": "t",
                "site": "s",
                "phase": "Publish",
                "title": "Bad Phase",
                "content": "",
            }
        )
        assert result["success"] is False
        assert "Unknown phase" in result["error"]
        assert "Publish" in result["error"]

    async def test_upload_failure_propagated(self, monkeypatch):
        from app.clients.content_workflow import save_phase_artifact

        async def _fake_token():
            return "tok"

        def _fake_docx(phase, title, tenant, site, sections):
            return b"bytes"

        async def _fake_upload(tenant, site, phase, docx_bytes, auth_token):
            return {
                "success": False,
                "media_path": "/some/path",
                "overwrite": False,
                "error": "HTTP 503",
            }

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.generate_phase_docx", _fake_docx
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.upload_artifact_to_media_library", _fake_upload
        )

        result = await save_phase_artifact.ainvoke(
            {
                "tenant": "t",
                "site": "s",
                "phase": "Strategy",
                "title": "Strategy",
                "content": "",
            }
        )
        assert result["success"] is False
        assert "HTTP 503" in result["error"]


class TestGetPhaseArtifactContent:
    async def test_success_path(self, monkeypatch):
        from app.clients.content_workflow import get_phase_artifact_content

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            return {"exists": True, "modified_at": "2026-06-01T00:00:00+00:00", "age_days": 18}

        async def _fake_extract(media_path, auth_token):
            return True, "Extracted text content", None

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.download_and_extract_artifact", _fake_extract
        )

        result = await get_phase_artifact_content.ainvoke(
            {"tenant": "t", "site": "s", "phase": "Research"}
        )
        assert result["success"] is True
        assert result["text_content"] == "Extracted text content"
        assert result["phase"] == "Research"
        assert result["error"] is None

    async def test_missing_artifact(self, monkeypatch):
        from app.clients.content_workflow import get_phase_artifact_content

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            return {"exists": False, "modified_at": None, "age_days": None}

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )

        result = await get_phase_artifact_content.ainvoke(
            {"tenant": "t", "site": "s", "phase": "Strategy"}
        )
        assert result["success"] is False
        assert result["text_content"] is None
        assert "not be complete yet" in result["error"]

    async def test_extraction_failure(self, monkeypatch):
        from app.clients.content_workflow import get_phase_artifact_content

        async def _fake_token():
            return "tok"

        async def _fake_check(tenant, site, phase, auth_token):
            return {"exists": True, "modified_at": "2026-01-01T00:00:00+00:00", "age_days": 10}

        async def _fake_extract(media_path, auth_token):
            return False, None, "Corrupted file"

        monkeypatch.setattr(
            "app.clients.content_workflow.get_sitecore_media_auth_token", _fake_token
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.check_media_artifact_exists", _fake_check
        )
        monkeypatch.setattr(
            "app.clients.content_workflow.download_and_extract_artifact", _fake_extract
        )

        result = await get_phase_artifact_content.ainvoke(
            {"tenant": "t", "site": "s", "phase": "Content"}
        )
        assert result["success"] is False
        assert result["text_content"] is None
        assert "Corrupted file" in result["error"]

    async def test_unknown_phase_error(self, monkeypatch):
        from app.clients.content_workflow import get_phase_artifact_content

        result = await get_phase_artifact_content.ainvoke(
            {"tenant": "t", "site": "s", "phase": "Nonexistent"}
        )
        assert result["success"] is False
        assert "Unknown phase" in result["error"]


class TestParseMarkdownSections:
    def _parse(self, text):
        from app.clients.content_workflow import _parse_markdown_sections
        return _parse_markdown_sections(text)

    def test_h2_sections_extracted(self):
        md = "## Overview\nSome intro text.\n\n## Objectives\nBe great."
        sections = self._parse(md)
        assert len(sections) == 2
        assert sections[0]["heading"] == "Overview"
        assert "intro text" in sections[0]["content"]
        assert sections[1]["heading"] == "Objectives"

    def test_h3_becomes_subsection(self):
        md = "## Goals\nTop-level.\n### Primary\nFirst.\n### Secondary\nSecond."
        sections = self._parse(md)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Goals"
        assert len(sections[0]["subsections"]) == 2
        assert sections[0]["subsections"][0]["heading"] == "Primary"
        assert sections[0]["subsections"][1]["heading"] == "Secondary"

    def test_h1_title_is_skipped(self):
        md = "# Document Title\n## Section One\nBody."
        sections = self._parse(md)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Section One"

    def test_plain_text_no_headings(self):
        md = "Just some plain text with no headings."
        sections = self._parse(md)
        assert len(sections) == 1
        assert sections[0]["heading"] == ""
        assert "plain text" in sections[0]["content"]

    def test_empty_string_returns_empty_list(self):
        assert self._parse("") == []

    def test_subsection_content_flushed_on_next_h2(self):
        md = "## Alpha\n### Sub\nSub content.\n## Beta\nBeta content."
        sections = self._parse(md)
        assert len(sections) == 2
        assert sections[0]["subsections"][0]["content"] == "Sub content."
        assert sections[1]["content"] == "Beta content."
