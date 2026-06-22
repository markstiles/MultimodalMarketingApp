"""Unit tests for the headless conversation module.

Tests context.py, files.py, and runner._process_message() without
network calls or a real database session.
"""
import base64
import os
import tempfile
from pathlib import Path

import pytest

# ─── ProxyContext / load_proxy_context ──────────────────────────────────────


class TestLoadProxyContext:
    def test_defaults_without_env(self, monkeypatch):
        for key in [
            "HEADLESS_SITE_ID", "HEADLESS_PAGE_ID", "HEADLESS_LANGUAGE",
            "HEADLESS_USER_ID", "HEADLESS_USER_NAME", "HEADLESS_USER_EMAIL",
            "LOCAL_SITE_ID", "LOCAL_PAGE_ID", "LOCAL_LANGUAGE",
        ]:
            monkeypatch.delenv(key, raising=False)

        from app.headless.context import load_proxy_context
        ctx = load_proxy_context()
        assert ctx.site_id == "stub-site-id"
        assert ctx.page_id == "stub-page-id"
        assert ctx.language == "en"
        assert ctx.user_id == "headless-runner"
        assert ctx.user_name is None
        assert ctx.user_email is None

    def test_headless_vars_take_priority(self, monkeypatch):
        monkeypatch.setenv("HEADLESS_SITE_ID", "real-site")
        monkeypatch.setenv("HEADLESS_PAGE_ID", "real-page")
        monkeypatch.setenv("HEADLESS_LANGUAGE", "fr-FR")
        monkeypatch.setenv("HEADLESS_USER_ID", "bot-01")
        monkeypatch.setenv("HEADLESS_USER_NAME", "Bot One")
        monkeypatch.setenv("HEADLESS_USER_EMAIL", "bot@example.com")
        monkeypatch.setenv("LOCAL_SITE_ID", "local-site")

        from app.headless.context import load_proxy_context
        ctx = load_proxy_context()
        assert ctx.site_id == "real-site"
        assert ctx.page_id == "real-page"
        assert ctx.language == "fr-FR"
        assert ctx.user_id == "bot-01"
        assert ctx.user_name == "Bot One"
        assert ctx.user_email == "bot@example.com"

    def test_local_vars_used_as_fallback(self, monkeypatch):
        for key in ["HEADLESS_SITE_ID", "HEADLESS_PAGE_ID", "HEADLESS_LANGUAGE"]:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("LOCAL_SITE_ID", "local-site-123")
        monkeypatch.setenv("LOCAL_PAGE_ID", "local-page-456")
        monkeypatch.setenv("LOCAL_LANGUAGE", "de-DE")

        from app.headless.context import load_proxy_context
        ctx = load_proxy_context()
        assert ctx.site_id == "local-site-123"
        assert ctx.page_id == "local-page-456"
        assert ctx.language == "de-DE"

    def test_to_runtime_context(self, monkeypatch):
        monkeypatch.setenv("HEADLESS_SITE_ID", "s1")
        monkeypatch.setenv("HEADLESS_PAGE_ID", "p1")
        monkeypatch.setenv("HEADLESS_LANGUAGE", "en")
        monkeypatch.setenv("HEADLESS_USER_NAME", "Test User")

        # Stub the schemas module so sqlmodel isn't required in unit-test env
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        captured = {}

        def _fake_runtime_context(**kw):
            captured.update(kw)
            return MagicMock(**kw)

        fake_schemas = ModuleType("app.resources.schemas")
        fake_schemas.RuntimeContext = _fake_runtime_context  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "app.resources.schemas", fake_schemas)

        # Re-import context after stub is in place
        import importlib
        import app.headless.context as _ctx_mod
        importlib.reload(_ctx_mod)

        ctx = _ctx_mod.load_proxy_context()
        ctx.to_runtime_context()

        assert captured.get("site_id") == "s1"
        assert captured.get("page_id") == "p1"
        assert captured.get("language") == "en"
        assert captured.get("user_name") == "Test User"

    def test_summary_includes_key_fields(self, monkeypatch):
        monkeypatch.setenv("HEADLESS_SITE_ID", "site-abc")
        monkeypatch.setenv("HEADLESS_PAGE_ID", "page-xyz")
        monkeypatch.setenv("HEADLESS_LANGUAGE", "en")
        monkeypatch.setenv("HEADLESS_USER_NAME", "Alice")

        from app.headless.context import load_proxy_context
        ctx = load_proxy_context()
        s = ctx.summary()
        assert "site-abc" in s
        assert "page-xyz" in s
        assert "Alice" in s


# ─── FileRegistry ────────────────────────────────────────────────────────────


class TestFileRegistryEmpty:
    def test_empty_source(self):
        from app.headless.files import FileRegistry
        reg = FileRegistry(None)
        assert reg.names == []
        assert not reg

    def test_format_listing_empty(self):
        from app.headless.files import FileRegistry
        assert FileRegistry(None).format_listing() == "No files available."


class TestFileRegistryDirectory:
    def test_loads_files_from_directory(self):
        from app.headless.files import FileRegistry

        with tempfile.TemporaryDirectory() as d:
            Path(d, "brief.md").write_text("# Brief", encoding="utf-8")
            Path(d, "data.csv").write_text("a,b\n1,2", encoding="utf-8")
            Path(d, ".hidden").write_text("skip", encoding="utf-8")

            reg = FileRegistry(d)
            assert "brief.md" in reg.names
            assert "data.csv" in reg.names
            assert ".hidden" not in reg.names

    def test_read_text_returns_content(self):
        from app.headless.files import FileRegistry

        with tempfile.TemporaryDirectory() as d:
            Path(d, "note.txt").write_text("hello world", encoding="utf-8")
            reg = FileRegistry(d)
            assert reg.read_text("note.txt") == "hello world"

    def test_read_text_missing_returns_none(self):
        from app.headless.files import FileRegistry
        reg = FileRegistry(None)
        assert reg.read_text("does_not_exist.txt") is None

    def test_read_bytes_returns_bytes_and_mime(self):
        from app.headless.files import FileRegistry

        with tempfile.TemporaryDirectory() as d:
            raw = b"\x89PNG\r\n\x1a\n"
            Path(d, "image.png").write_bytes(raw)
            reg = FileRegistry(d)
            result = reg.read_bytes("image.png")
            assert result is not None
            data, mime = result
            assert data == raw
            assert "image" in mime

    def test_read_b64_returns_base64_string(self):
        from app.headless.files import FileRegistry

        with tempfile.TemporaryDirectory() as d:
            raw = b"binary content"
            Path(d, "file.bin").write_bytes(raw)
            reg = FileRegistry(d)
            result = reg.read_b64("file.bin")
            assert result is not None
            encoded, _ = result
            assert base64.b64decode(encoded) == raw

    def test_format_listing_shows_names_and_kind(self):
        from app.headless.files import FileRegistry

        with tempfile.TemporaryDirectory() as d:
            Path(d, "doc.md").write_text("# doc", encoding="utf-8")
            reg = FileRegistry(d)
            listing = reg.format_listing()
            assert "doc.md" in listing
            assert "text" in listing


class TestFileRegistryNamedPairs:
    def test_named_pairs_format(self):
        from app.headless.files import FileRegistry

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("content")
            fpath = f.name

        try:
            reg = FileRegistry(f"myfile={fpath}")
            assert "myfile" in reg.names
            assert reg.read_text("myfile") == "content"
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_multiple_pairs(self):
        from app.headless.files import FileRegistry

        with (
            tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f1,
            tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f2,
        ):
            f1.write("file1")
            f2.write("file2")
            p1, p2 = f1.name, f2.name

        try:
            reg = FileRegistry(f"a={p1},b={p2}")
            assert "a" in reg.names
            assert "b" in reg.names
            assert reg.read_text("a") == "file1"
            assert reg.read_text("b") == "file2"
        finally:
            Path(p1).unlink(missing_ok=True)
            Path(p2).unlink(missing_ok=True)

    def test_nonexistent_path_skipped(self):
        from app.headless.files import FileRegistry
        reg = FileRegistry("missing=/no/such/path/file.txt")
        assert "missing" not in reg.names


# ─── HeadlessRunner._process_message ─────────────────────────────────────────


class TestProcessMessage:
    def _make_runner(self, files_source=None):
        """Build a HeadlessRunner instance bypassing env/LLM init."""
        from unittest.mock import MagicMock

        from app.headless.runner import HeadlessRunner

        runner = object.__new__(HeadlessRunner)
        runner.scenario = "test"
        runner.max_turns = 5
        runner.verbose = False

        from app.headless.context import ProxyContext
        runner.context = ProxyContext(
            site_id="s", page_id="p", language="en", user_id="u"
        )
        from app.headless.files import FileRegistry
        runner.files = FileRegistry(files_source)
        runner.session = MagicMock()
        runner.driver = MagicMock()
        return runner

    def test_no_attach_markers_unchanged(self):
        runner = self._make_runner()
        msg, attached = runner._process_message("Hello, world!")
        assert msg == "Hello, world!"
        assert attached == []

    def test_text_file_injected_inline(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "brief.md").write_text("# Marketing Brief", encoding="utf-8")
            runner = self._make_runner(d)
            msg, attached = runner._process_message(
                "Here is my brief:\n[ATTACH: brief.md]"
            )
            assert "# Marketing Brief" in msg
            assert "brief.md" in attached
            assert "[ATTACH:" not in msg

    def test_missing_file_replaced_with_notice(self):
        runner = self._make_runner()
        msg, attached = runner._process_message("[ATTACH: ghost.pdf]")
        assert "[File not found: ghost.pdf]" in msg
        assert "ghost.pdf" in attached

    def test_binary_file_gets_descriptive_notice(self):
        with tempfile.TemporaryDirectory() as d:
            # Write a fake PDF (binary)
            Path(d, "deck.pdf").write_bytes(b"%PDF-1.4 binary content")
            runner = self._make_runner(d)
            msg, attached = runner._process_message("Attach my deck [ATTACH: deck.pdf]")
            assert "deck.pdf" in msg
            assert "binary" in msg.lower() or "application/pdf" in msg
            assert "deck.pdf" in attached

    def test_multiple_attachments(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.txt").write_text("aaa", encoding="utf-8")
            Path(d, "b.txt").write_text("bbb", encoding="utf-8")
            runner = self._make_runner(d)
            msg, attached = runner._process_message("[ATTACH: a.txt] and [ATTACH: b.txt]")
            assert "aaa" in msg
            assert "bbb" in msg
            assert "a.txt" in attached
            assert "b.txt" in attached
