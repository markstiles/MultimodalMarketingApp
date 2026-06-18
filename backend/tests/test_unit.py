"""
Pure-Python unit tests — no DB, no LLM, no running server required.
Run: just test-unit
"""
import pytest
from datetime import datetime, timezone


# ─────────────────────────── datetime helpers ────────────────────

class TestDatetimeHelpers:
    def test_utcnow_is_naive(self):
        from app.resources.models import utcnow
        dt = utcnow()
        assert dt.tzinfo is None, "utcnow() must return a naive datetime for TIMESTAMP WITHOUT TIME ZONE columns"

    def test_conversation_service_now_is_naive(self):
        from app.services.conversation_service import _now
        dt = _now()
        assert dt.tzinfo is None, "_now() must return a naive datetime"

    def test_now_is_utc_approximately(self):
        from app.services.conversation_service import _now
        dt = _now()
        utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = abs((utc_naive - dt).total_seconds())
        assert diff < 2, f"_now() should be close to UTC now, diff={diff}s"


# ─────────────────────────── schemas ─────────────────────────────

class TestChatRequestSchema:
    def test_accepts_valid_request(self):
        from app.resources.schemas import ChatRequest, RuntimeContext
        req = ChatRequest(
            message="hello",
            context=RuntimeContext(page_id="p1", site_id="s1", language="en"),
        )
        assert req.message == "hello"

    def test_accepts_camelcase_json(self):
        from app.resources.schemas import ChatRequest
        req = ChatRequest.model_validate({
            "message": "hello",
            "context": {"pageId": "p1", "siteId": "s1", "language": "en"},
        })
        assert req.context.page_id == "p1"
        assert req.context.site_id == "s1"

    def test_rejects_blank_message(self):
        from app.resources.schemas import ChatRequest, RuntimeContext
        with pytest.raises(Exception):
            ChatRequest(
                message="   ",
                context=RuntimeContext(page_id="p1", site_id="s1", language="en"),
            )

    def test_rejects_empty_message(self):
        from app.resources.schemas import ChatRequest, RuntimeContext
        with pytest.raises(Exception):
            ChatRequest(
                message="",
                context=RuntimeContext(page_id="p1", site_id="s1", language="en"),
            )

    def test_optional_conversation_id_defaults_none(self):
        from app.resources.schemas import ChatRequest, RuntimeContext
        req = ChatRequest(
            message="hi",
            context=RuntimeContext(page_id="p", site_id="s", language="en"),
        )
        assert req.conversation_id is None


# ─────────────────────────── guardrails ──────────────────────────

class TestGuardrails:
    def test_political_message_detected(self):
        from app.services.guardrails import classify_message
        assert classify_message("Who should I vote for?") == "politics"

    def test_election_detected(self):
        from app.services.guardrails import classify_message
        assert classify_message("Tell me about the upcoming election") == "politics"

    def test_medical_detected(self):
        from app.services.guardrails import classify_message
        assert classify_message("What are my symptoms telling me?") == "medical"

    def test_marketing_message_not_flagged(self):
        from app.services.guardrails import classify_message
        assert classify_message("Help me write a landing page headline") is None

    def test_sitecore_content_not_flagged(self):
        from app.services.guardrails import classify_message
        assert classify_message("How should I structure my site navigation?") is None

    def test_returns_none_for_benign(self):
        from app.services.guardrails import classify_message
        assert classify_message("What can you help me with?") is None


# ─────────────────────────── instruction loader ──────────────────

class TestInstructionLoader:
    def test_base_instructions_load(self):
        from app.services.instruction_loader import load_instructions
        result = load_instructions()
        assert len(result) > 0, "Instruction loader returned empty string"

    def test_includes_guardrails(self):
        from app.services.instruction_loader import load_instructions
        result = load_instructions()
        assert "Guardrails" in result, "Loaded instructions should include Guardrails section"

    def test_task_overlay_appended(self):
        from app.services.instruction_loader import load_instructions
        without = load_instructions()
        with_task = load_instructions("seo-optimization")
        assert len(with_task) > len(without), "Task overlay should add content"
        assert "Task Context" in with_task

    def test_unknown_task_ignored_safely(self):
        from app.services.instruction_loader import load_instructions
        result = load_instructions("nonexistent-task")
        base = load_instructions()
        assert result == base, "Unknown task name should fall back to base instructions"

    def test_path_traversal_blocked(self):
        from app.services.instruction_loader import load_instructions
        result = load_instructions("../system/base")
        base = load_instructions()
        assert result == base, "Path traversal attempt should be blocked"

    def test_malicious_task_name_blocked(self):
        from app.services.instruction_loader import load_instructions
        result = load_instructions("../../etc/passwd")
        base = load_instructions()
        assert result == base


# ─────────────────────────── SSE event format ────────────────────

class TestSseEventFormat:
    def test_event_format(self):
        from app.services.chat_service import _event
        raw = _event({"type": "done"})
        assert raw.startswith("data: "), "SSE events must start with 'data: '"
        assert raw.endswith("\n\n"), "SSE events must end with double newline"

    def test_event_is_valid_json(self):
        import json
        from app.services.chat_service import _event
        raw = _event({"type": "delta", "text": "hello"})
        line = raw.strip()
        assert line.startswith("data: ")
        data = json.loads(line[6:])
        assert data == {"type": "delta", "text": "hello"}

    def test_error_mapping_rate_limit(self):
        from app.services.chat_service import _map_error
        class RateLimitError(Exception):
            pass
        assert _map_error(RateLimitError()) == "rate_limit"

    def test_error_mapping_unknown(self):
        from app.services.chat_service import _map_error
        assert _map_error(ValueError("something")) == "internal_error"


# ─────────────────────────── auth verifier ───────────────────────

class TestAuthVerifier:
    @pytest.mark.asyncio
    async def test_local_mode_uses_header(self, monkeypatch):
        import os
        monkeypatch.setenv("RUNTIME_CONTEXT", "local")
        from unittest.mock import MagicMock
        from app.clients.auth_verifier import get_user_id

        request = MagicMock()
        request.headers.get = lambda k, default="": "my-local-user" if k == "X-Local-User-Id" else default

        user_id = await get_user_id(request)
        assert user_id == "my-local-user"

    @pytest.mark.asyncio
    async def test_local_mode_defaults_local_user(self, monkeypatch):
        import os
        monkeypatch.setenv("RUNTIME_CONTEXT", "local")
        from unittest.mock import MagicMock
        from app.clients.auth_verifier import get_user_id

        request = MagicMock()
        request.headers.get = lambda k, default="": default

        user_id = await get_user_id(request)
        assert user_id == "local-user"
