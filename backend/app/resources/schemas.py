from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, field_validator
from pydantic.alias_generators import to_camel
from sqlmodel import SQLModel


class _CamelModel(SQLModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class RuntimeContext(_CamelModel):
    page_id: str
    site_id: str
    language: str


class ChatRequest(_CamelModel):
    message: str
    conversation_id: Optional[str] = None
    context: RuntimeContext

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


class MessageRead(SQLModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationSummary(SQLModel):
    id: str
    title: Optional[str]
    site_id: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageRead] = []


class ConversationList(SQLModel):
    conversations: list[ConversationSummary]
    total: int


class UserRead(SQLModel):
    id: str
    email: str


class AuthStatus(SQLModel):
    authenticated: bool
    user: Optional[UserRead] = None
    expires_at: Optional[datetime] = None


class TokenRefreshResponse(SQLModel):
    expires_at: datetime
