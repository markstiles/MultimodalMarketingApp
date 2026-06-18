from datetime import datetime, timezone
from typing import Optional

from cuid2 import cuid_wrapper
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.resources.models import Conversation, Message, MessageRole

_cuid = cuid_wrapper()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_conversation(
    db: AsyncSession, user_id: str, site_id: str
) -> Conversation:
    conv = Conversation(
        id=_cuid(),
        user_id=user_id,
        site_id=site_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(
    db: AsyncSession, conversation_id: str, user_id: str
) -> Optional[Conversation]:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def append_message(
    db: AsyncSession,
    conversation_id: str,
    role: MessageRole,
    content: str,
) -> Message:
    msg = Message(
        id=_cuid(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=_now(),
    )
    db.add(msg)
    await db.execute(
        Conversation.__table__.update()
        .where(Conversation.id == conversation_id)
        .values(updated_at=_now())
    )
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_conversation_messages(
    db: AsyncSession, conversation_id: str, user_id: str
) -> Optional[tuple[Conversation, list[Message]]]:
    conv = await get_conversation(db, conversation_id, user_id)
    if conv is None:
        return None
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return conv, list(messages)


async def soft_delete_conversation(
    db: AsyncSession, conversation_id: str, user_id: str
) -> bool:
    conv = await get_conversation(db, conversation_id, user_id)
    if conv is None:
        return False
    conv.deleted_at = _now()
    db.add(conv)
    await db.commit()
    return True


async def list_conversations(
    db: AsyncSession,
    user_id: str,
    site_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Conversation], int]:
    base = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.site_id == site_id,
        Conversation.deleted_at.is_(None),
    )
    count_result = await db.execute(
        select(Conversation.id)
        .where(
            Conversation.user_id == user_id,
            Conversation.site_id == site_id,
            Conversation.deleted_at.is_(None),
        )
    )
    total = len(count_result.scalars().all())

    result = await db.execute(
        base.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    )
    conversations = result.scalars().all()
    return list(conversations), total


async def update_title(
    db: AsyncSession, conversation_id: str, title: str
) -> None:
    await db.execute(
        Conversation.__table__.update()
        .where(Conversation.id == conversation_id)
        .values(title=title)
    )
    await db.commit()
