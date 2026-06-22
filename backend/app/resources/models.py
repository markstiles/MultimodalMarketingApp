import enum
from datetime import datetime, timezone
from typing import Optional

from cuid2 import cuid_wrapper
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

cuid = cuid_wrapper()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    user_id: str = Field(index=True)
    site_id: str
    title: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    messages: list["Message"] = Relationship(back_populates="conversation")


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


# Embedding dimension from Cohere embed-english-v3.0 / embed-multilingual-v3.0
_EMBEDDING_DIM = 1024


class ImageEmbedding(SQLModel, table=True):
    """Vector index of Sitecore media library images.

    Requires the pgvector PostgreSQL extension:
        CREATE EXTENSION IF NOT EXISTS vector;

    One row per (item_id, environment, site_id) — unique constraint prevents
    duplicates when a webhook fires twice for the same item.
    """

    __tablename__ = "image_embeddings"
    __table_args__ = (
        UniqueConstraint("item_id", "environment", "site_id", name="uq_image_embedding"),
        Index("ix_image_embeddings_site", "site_id", "environment", "collection"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: str = Field(index=True)
    environment: str
    site_id: str
    collection: str
    media_path: str
    item_name: str
    alt_text: Optional[str] = None
    description: Optional[str] = None
    embedding: list = Field(sa_column=Column(Vector(_EMBEDDING_DIM)))
    indexed_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
