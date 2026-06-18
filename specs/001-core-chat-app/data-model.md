# Data Model: Core Chat Application

**Feature**: `001-core-chat-app`
**Date**: 2026-06-17 (revised for SQLModel unified modeling)

All entities use CUID string primary keys (`cuid2` Python package). Timestamps are UTC `datetime` with timezone.

SQLModel is the unified data modeling layer. `SQLModel(table=True)` classes define database tables and are simultaneously valid Pydantic models — used directly for database operations, API response serialization, and LangChain tool schemas.

---

## Entities

### User

Represents an authenticated Sitecore Cloud user.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `str` | PK, CUID | |
| `sitecore_id` | `str` | UNIQUE, NOT NULL | Auth0 `sub` claim |
| `email` | `str` | NOT NULL | |
| `created_at` | `datetime` | NOT NULL, default now | UTC |

**Relationships**: one → many Conversations; one → one UserSession

---

### UserSession

Stores encrypted OAuth tokens for a user.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `str` | PK, CUID | |
| `user_id` | `str` | FK → User.id, UNIQUE, NOT NULL | One session per user |
| `access_token` | `str` | NOT NULL | Encrypted at rest |
| `refresh_token` | `str` | NOT NULL | Encrypted at rest |
| `expires_at` | `datetime` | NOT NULL | UTC token expiry |
| `updated_at` | `datetime` | NOT NULL, auto-update | UTC |

---

### Conversation

A single chat session scoped to a user and a Sitecore site.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `str` | PK, CUID | |
| `user_id` | `str` | FK → User.id, NOT NULL | |
| `site_id` | `str` | NOT NULL | Sitecore site identifier |
| `title` | `str \| None` | NULLABLE | Derived from first message |
| `deleted_at` | `datetime \| None` | NULLABLE | Soft delete |
| `created_at` | `datetime` | NOT NULL, default now | UTC |
| `updated_at` | `datetime` | NOT NULL, auto-update | UTC |

**Indexes**: `(user_id, site_id, deleted_at)`, `(updated_at)`

---

### Message

A single turn in a conversation.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `str` | PK, CUID | |
| `conversation_id` | `str` | FK → Conversation.id, NOT NULL | |
| `role` | `MessageRole` | NOT NULL | Enum: `user`, `assistant` |
| `content` | `str` | NOT NULL | Full message text |
| `created_at` | `datetime` | NOT NULL, default now | UTC |

**Indexes**: `(conversation_id, created_at)`

---

## SQLModel Table Models

```python
# backend/app/resources/models.py

import enum
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, Column, Index
from sqlalchemy import UniqueConstraint, Text, Enum as SAEnum, DateTime
from cuid2 import cuid_wrapper

cuid = cuid_wrapper()

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=cuid, primary_key=True)
    sitecore_id: str = Field(unique=True)
    email: str
    created_at: datetime = Field(default_factory=utcnow)

    session: Optional["UserSession"] = Relationship(back_populates="user")
    conversations: list["Conversation"] = Relationship(back_populates="user")


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: str = Field(default_factory=cuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", unique=True)
    access_token: str
    refresh_token: str
    expires_at: datetime
    updated_at: datetime = Field(default_factory=utcnow)

    user: Optional[User] = Relationship(back_populates="session")


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_site_deleted", "user_id", "site_id", "deleted_at"),
        Index("ix_conversations_updated_at", "updated_at"),
    )

    id: str = Field(default_factory=cuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    site_id: str
    title: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    messages: list["Message"] = Relationship(back_populates="conversation")
    user: Optional[User] = Relationship(back_populates="conversations")


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: str = Field(default_factory=cuid, primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id")
    role: MessageRole
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utcnow)

    conversation: Optional[Conversation] = Relationship(back_populates="messages")
```

---

## API Schemas

Non-table SQLModel subclasses for shapes that differ from the table model — keeping definitions DRY via inheritance.

```python
# backend/app/resources/schemas.py

from sqlmodel import SQLModel
from datetime import datetime

# ── Chat ────────────────────────────────────────────────────────────────────────

class RuntimeContext(SQLModel):
    page_id: str
    site_id: str
    language: str


class ChatRequest(SQLModel):
    message: str
    conversation_id: str | None = None
    context: RuntimeContext


# ── Conversation responses ──────────────────────────────────────────────────────

class MessageRead(SQLModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationSummary(SQLModel):
    id: str
    title: str | None
    site_id: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageRead] = []


class ConversationList(SQLModel):
    conversations: list[ConversationSummary]
    total: int


# ── Auth ────────────────────────────────────────────────────────────────────────

class UserRead(SQLModel):
    id: str
    email: str


class AuthStatus(SQLModel):
    authenticated: bool
    user: UserRead | None = None
    expires_at: datetime | None = None


class TokenRefreshResponse(SQLModel):
    expires_at: datetime
```

---

## Async Engine & Session

```python
# backend/app/resources/database.py

import os
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

def _get_db_url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _get_db_url(),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Alembic Notes

`alembic/env.py` uses `target_metadata = SQLModel.metadata` (not `Base.metadata`). All table models must be imported before Alembic reads the metadata:

```python
# alembic/env.py
from app.resources.models import User, UserSession, Conversation, Message  # noqa: F401
from sqlmodel import SQLModel
target_metadata = SQLModel.metadata
```

Railway start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## Relationship Loading

SQLModel relationships defined via `Relationship()` use SQLAlchemy under the hood. In async contexts, lazy loading is disabled — all relationship traversals must be explicit:

```python
# Correct: eager load messages when fetching a conversation
stmt = select(Conversation).where(
    Conversation.id == conversation_id
).options(selectinload(Conversation.messages))
```

---

## Validation Rules

| Rule | Enforced at |
|------|-------------|
| `sitecore_id` required, non-empty | SQLModel field (no default) |
| `access_token`/`refresh_token` encrypted before write | Service layer |
| `site_id` required, non-empty | SQLModel field (no default) |
| `content` max 32,000 chars | `ChatRequest` Pydantic validator |
| All queries scoped by `user_id` | Service layer |
| Conversation ownership verified before message append | Service layer |
