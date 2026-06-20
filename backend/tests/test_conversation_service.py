"""Unit tests for conversation_service.py — DB persistence layer."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.models import Conversation, Message, MessageRole

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ── Session helpers ───────────────────────────────────────────────────────────

def _mock_session(scalar_result=None, scalars_list=None):
    """Build a mock AsyncSession with configurable execute() results.

    scalar_result  → returned by result.scalar_one_or_none()
    scalars_list   → returned by result.scalars().all()
    """
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    mock_result.scalars.return_value.all.return_value = scalars_list or []
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _mock_session_multi(*results):
    """Build a mock session where successive execute() calls return different results."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock(side_effect=list(results))
    return db


def _fake_result(scalar=None, all_list=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    r.scalars.return_value.all.return_value = all_list or []
    return r


# ── create_conversation ───────────────────────────────────────────────────────

async def test_create_conversation_returns_correct_fields():
    from app.services.conversation_service import create_conversation

    db = _mock_session()
    conv = await create_conversation(db, "user-1", "site-1")

    assert conv.user_id == "user-1"
    assert conv.site_id == "site-1"
    assert conv.id  # CUID generated
    assert conv.deleted_at is None


async def test_create_conversation_commits_and_refreshes():
    from app.services.conversation_service import create_conversation

    db = _mock_session()
    await create_conversation(db, "u", "s")

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


# ── get_conversation ──────────────────────────────────────────────────────────

async def test_get_conversation_returns_match():
    from app.services.conversation_service import get_conversation

    fake_conv = MagicMock(spec=Conversation)
    db = _mock_session(scalar_result=fake_conv)

    result = await get_conversation(db, "conv-1", "user-1")

    assert result is fake_conv
    db.execute.assert_awaited_once()


async def test_get_conversation_returns_none_when_not_found():
    from app.services.conversation_service import get_conversation

    db = _mock_session(scalar_result=None)
    result = await get_conversation(db, "missing", "user-1")

    assert result is None


# ── append_message ────────────────────────────────────────────────────────────

async def test_append_message_returns_correct_fields():
    from app.services.conversation_service import append_message

    db = _mock_session()
    msg = await append_message(db, "conv-1", MessageRole.user, "Hello world")

    assert msg.conversation_id == "conv-1"
    assert msg.role == MessageRole.user
    assert msg.content == "Hello world"
    assert msg.id  # CUID generated


async def test_append_message_commits():
    from app.services.conversation_service import append_message

    db = _mock_session()
    await append_message(db, "conv-1", MessageRole.assistant, "Hi")

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


# ── get_conversation_messages ─────────────────────────────────────────────────

async def test_get_conversation_messages_returns_tuple():
    from app.services.conversation_service import get_conversation_messages

    fake_conv = MagicMock(spec=Conversation)
    fake_msgs = [MagicMock(spec=Message), MagicMock(spec=Message)]

    db = _mock_session_multi(
        _fake_result(scalar=fake_conv),   # get_conversation query
        _fake_result(all_list=fake_msgs), # messages query
    )

    result = await get_conversation_messages(db, "conv-1", "user-1")

    assert result is not None
    conv, messages = result
    assert conv is fake_conv
    assert messages == fake_msgs


async def test_get_conversation_messages_returns_none_when_not_found():
    from app.services.conversation_service import get_conversation_messages

    db = _mock_session(scalar_result=None)
    result = await get_conversation_messages(db, "missing", "user-1")

    assert result is None


# ── soft_delete_conversation ──────────────────────────────────────────────────

async def test_soft_delete_sets_deleted_at_and_returns_true():
    from app.services.conversation_service import soft_delete_conversation

    fake_conv = MagicMock(spec=Conversation)
    fake_conv.deleted_at = None
    db = _mock_session(scalar_result=fake_conv)

    result = await soft_delete_conversation(db, "conv-1", "user-1")

    assert result is True
    assert fake_conv.deleted_at is not None  # was set by the service
    db.add.assert_called_once_with(fake_conv)
    db.commit.assert_awaited_once()


async def test_soft_delete_returns_false_when_not_found():
    from app.services.conversation_service import soft_delete_conversation

    db = _mock_session(scalar_result=None)
    result = await soft_delete_conversation(db, "missing", "user-1")

    assert result is False
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


# ── list_conversations ────────────────────────────────────────────────────────

async def test_list_conversations_returns_list_and_total():
    from app.services.conversation_service import list_conversations

    fake_convs = [MagicMock(spec=Conversation) for _ in range(3)]
    count_ids = ["id1", "id2", "id3"]  # 3 total

    db = _mock_session_multi(
        _fake_result(all_list=count_ids),   # count query
        _fake_result(all_list=fake_convs),  # data query
    )

    convs, total = await list_conversations(db, "user-1", "site-1")

    assert total == 3
    assert convs == fake_convs


async def test_list_conversations_empty():
    from app.services.conversation_service import list_conversations

    db = _mock_session_multi(
        _fake_result(all_list=[]),  # count query → 0
        _fake_result(all_list=[]),  # data query → []
    )

    convs, total = await list_conversations(db, "user-1", "site-1")

    assert total == 0
    assert convs == []


# ── update_title ──────────────────────────────────────────────────────────────

async def test_update_title_commits():
    from app.services.conversation_service import update_title

    db = _mock_session()
    await update_title(db, "conv-1", "My New Title")

    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
