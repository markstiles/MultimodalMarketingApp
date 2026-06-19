import pytest


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
                f"/sitecore/media library/Project/{tenant}/{site}"
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
                "media_path": f"/sitecore/media library/Project/{tenant}/{site}/Content Strategy/{phase}/research-brief.docx",
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
                "sections": [{"heading": "Summary", "content": "Content", "subsections": []}],
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
                "sections": [],
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
                "sections": [],
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
