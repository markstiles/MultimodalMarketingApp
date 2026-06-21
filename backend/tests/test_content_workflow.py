from unittest.mock import AsyncMock, MagicMock

import pytest

# LangChain's ainvoke uses asyncio.gather internally — trio backend is incompatible.
pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestBuildArtifactMediaPath:
    def test_all_five_phases_produce_correct_paths(self):
        from app.services.content_workflow_service import build_artifact_media_path

        # All phase artifacts live flat under "Content Strategy" — no per-phase subfolders.
        # Paths use item names WITHOUT extension: this instance's InvalidItemNameChars
        # includes '.', so Sitecore stores items as "research-brief" not "research-brief.docx".
        cases = {
            "Research":   "research-brief",
            "Strategy":   "marketing-strategy",
            "BrandVoice": "brand-voice-summary",
            "Brief":      "campaign-brief",
            "Campaign":   "campaign-plan",
        }
        tenant = "acme-corp"
        site = "us-site"
        for phase, item_name in cases.items():
            path = build_artifact_media_path(tenant, site, phase)
            expected = (
                f"/sitecore/Media Library/Project/{tenant}/{site}"
                f"/Content Strategy/{item_name}"
            )
            assert path == expected, f"Phase {phase}: expected {expected!r}, got {path!r}"

    def test_unknown_phase_raises(self):
        from app.services.content_workflow_service import build_artifact_media_path

        with pytest.raises(ValueError, match="Unknown phase"):
            build_artifact_media_path("t", "s", "Publish")

    def test_tenant_and_site_interpolated(self):
        from app.services.content_workflow_service import build_artifact_media_path

        path = build_artifact_media_path("my-tenant", "my-site", "Campaign")
        assert "/my-tenant/my-site/" in path


# ── Upload artifact HTTP contract ─────────────────────────────────────────────
#
# Upload now uses a two-step GraphQL presigned-URL flow:
#   1. POST uploadMedia mutation → receive presignedUploadUrl
#   2. POST file bytes to the presigned URL (no auth header — self-signed)

_PRESIGNED_URL = "https://presigned.example.com/upload?sig=abc"
_PRESIGNED_RESPONSE = {"data": {"uploadMedia": {"presignedUploadUrl": _PRESIGNED_URL}}}


class TestUploadArtifactToMediaLibrary:
    """Validate the two-step GraphQL + presigned-URL upload flow."""

    def _make_fake_client(self, responses=None, raise_exc=None):
        """Return (FakeClientClass, captured_list).

        responses: list of (status_code, body) where body is a dict (JSON-serialised)
                   or a plain string. Calls are served in order.
        Default: two-step success — GraphQL returns presigned URL, presigned upload returns 200.
        """
        if responses is None:
            responses = [
                (200, _PRESIGNED_RESPONSE),
                (200, ""),
            ]

        captured = []
        call_idx = [0]

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, **kwargs):
                resp = MagicMock()
                resp.status_code = 404
                resp.is_success = False
                return resp

            async def post(self, url, **kwargs):
                if raise_exc:
                    raise raise_exc
                idx = call_idx[0]
                call_idx[0] += 1
                status, body = responses[idx] if idx < len(responses) else (500, "unexpected call")
                entry = {
                    "url": url,
                    "headers": kwargs.get("headers", {}),
                    "json": kwargs.get("json"),
                    "files": kwargs.get("files", {}),
                }
                captured.append(entry)
                resp = MagicMock()
                resp.status_code = status
                resp.is_success = 200 <= status < 300
                if isinstance(body, dict):
                    resp.json = lambda b=body: b
                    resp.text = str(body)
                else:
                    resp.json = MagicMock(side_effect=ValueError("not json"))
                    resp.text = body or ""
                return resp

        return FakeClient, captured

    def _common_patches(self, monkeypatch, FakeClient):
        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": False, "modified_at": None, "age_days": None}),
        )
        monkeypatch.setattr(
            "app.services.content_workflow_service.ensure_phase_upload_folders",
            AsyncMock(return_value=None),
        )

    async def test_graphql_mutation_targets_cm_host(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert captured[0]["url"] == "https://cm.example.com/sitecore/api/authoring/graphql/v1"

    async def test_graphql_mutation_uses_full_media_path(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library, build_artifact_media_path

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("my-tenant", "my-site", "Research", b"bytes", "tok")

        # itemPath must be relative to media library root: no slash prefix, no
        # obsolete "sitecore/Media Library" segment, and no file extension
        # (dots are invalid in item names on this instance).
        item_path = captured[0]["json"]["variables"]["itemPath"]
        assert not item_path.startswith("/")
        assert not item_path.lower().startswith("sitecore")
        assert "." not in item_path.split("/")[-1], "item name must not contain extension"
        assert "my-tenant" in item_path
        assert "my-site" in item_path
        assert "research-brief" in item_path
        query = captured[0]["json"]["query"]
        assert "includeExtensionInItemName" not in query

    async def test_graphql_mutation_sets_overwrite_existing(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        query = captured[0]["json"]["query"]
        assert "overwriteExisting: true" in query

    async def test_existing_artifact_is_overwritten(self, monkeypatch):
        """When an artifact already exists, upload succeeds and result reports overwrite=True."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        monkeypatch.setenv("SITECORE_CM_HOST", "https://cm.example.com")
        monkeypatch.setattr("app.services.content_workflow_service.httpx.AsyncClient", FakeClient)
        monkeypatch.setattr(
            "app.services.content_workflow_service.check_media_artifact_exists",
            AsyncMock(return_value={"exists": True, "modified_at": "2026-01-01T00:00:00+00:00", "age_days": 5}),
        )
        monkeypatch.setattr(
            "app.services.content_workflow_service.ensure_phase_upload_folders",
            AsyncMock(return_value=None),
        )

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is True
        assert result["overwrite"] is True
        query = captured[0]["json"]["query"]
        assert "overwriteExisting: true" in query

    async def test_graphql_request_sends_auth_token(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "my-token")

        assert captured[0]["headers"].get("Authorization") == "Bearer my-token"

    async def test_file_uploaded_to_presigned_url(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert captured[1]["url"] == _PRESIGNED_URL

    async def test_presigned_upload_sends_auth_header(self, monkeypatch):
        """This instance routes presigned URLs through its own CM host, so the Bearer token is required."""
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert captured[1]["headers"].get("Authorization") == "Bearer tok"

    async def test_presigned_upload_file_has_docx_content_type(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, captured = self._make_fake_client()
        self._common_patches(monkeypatch, FakeClient)

        await upload_artifact_to_media_library("t", "s", "Research", b"docx-content", "tok")

        _filename, content, content_type = captured[1]["files"]["file"]
        assert content == b"docx-content"
        assert "wordprocessingml" in content_type

    async def test_graphql_http_error_returns_failure(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, _ = self._make_fake_client(responses=[(503, "unavailable")])
        self._common_patches(monkeypatch, FakeClient)

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "503" in result["error"]

    async def test_graphql_error_field_returns_failure(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        gql_error = {"data": None, "errors": [{"message": "Unauthorized"}]}
        FakeClient, _ = self._make_fake_client(responses=[(200, gql_error)])
        self._common_patches(monkeypatch, FakeClient)

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "Unauthorized" in result["error"]

    async def test_presigned_upload_failure_returns_failure(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, _ = self._make_fake_client(responses=[
            (200, _PRESIGNED_RESPONSE),
            (400, "bad request"),
        ])
        self._common_patches(monkeypatch, FakeClient)

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "400" in result["error"]

    async def test_timeout_returns_failure(self, monkeypatch):
        import httpx as _httpx
        from app.services.content_workflow_service import upload_artifact_to_media_library

        FakeClient, _ = self._make_fake_client(raise_exc=_httpx.TimeoutException("timeout"))
        self._common_patches(monkeypatch, FakeClient)

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    async def test_cm_host_not_configured_returns_failure(self, monkeypatch):
        from app.services.content_workflow_service import upload_artifact_to_media_library

        monkeypatch.delenv("SITECORE_CM_HOST", raising=False)

        result = await upload_artifact_to_media_library("t", "s", "Research", b"bytes", "tok")

        assert result["success"] is False
        assert "SITECORE_CM_HOST" in result["error"]

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
            {"tenant": "t", "site": "s", "phase": "Brief"}
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


class TestMediaItemPath:
    def _strip(self, path):
        from app.services.content_workflow_service import _media_item_path
        return _media_item_path(path)

    def test_strips_slash_prefix_and_extension(self):
        result = self._strip("/sitecore/Media Library/Project/t/s/Content Strategy/Research/research-brief.docx")
        assert result == "Project/t/s/Content Strategy/Research/research-brief"

    def test_strips_prefix_without_leading_slash(self):
        result = self._strip("sitecore/Media Library/Project/t/s/research-brief.docx")
        assert result == "Project/t/s/research-brief"

    def test_case_insensitive_prefix_strip(self):
        result = self._strip("/sitecore/media library/Project/t/s/file.docx")
        assert result == "Project/t/s/file"

    def test_strips_extension_from_item_name(self):
        result = self._strip("Project/t/s/content-strategy.docx")
        assert result == "Project/t/s/content-strategy"

    def test_path_already_relative_no_extension_unchanged(self):
        result = self._strip("Project/t/s/file")
        assert result == "Project/t/s/file"

    def test_result_never_starts_with_slash(self):
        result = self._strip("/sitecore/Media Library/Project/t/s/f.docx")
        assert not result.startswith("/")

    def test_result_never_starts_with_sitecore(self):
        result = self._strip("/sitecore/Media Library/Project/t/s/f.docx")
        assert not result.lower().startswith("sitecore")

    def test_result_never_has_extension(self):
        result = self._strip("/sitecore/Media Library/Project/t/s/research-brief.docx")
        assert "." not in result.split("/")[-1]


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
