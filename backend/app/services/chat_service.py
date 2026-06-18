import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Optional

import mlflow
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlmodel.ext.asyncio.session import AsyncSession

from app.resources.models import MessageRole
from app.resources.schemas import ChatRequest
from app.services.chat_graph import get_chat_graph
from app.services.conversation_service import (
    append_message,
    create_conversation,
    get_conversation_messages,
    update_title,
)
from app.services.guardrails import classify_message
from app.services.instruction_loader import load_instructions

logger = logging.getLogger(__name__)

_MAX_HISTORY = 100
_TRUNCATED_HISTORY = 50


async def stream_chat(
    db: AsyncSession,
    user_id: str,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted event strings for the chat stream."""
    task_name: Optional[str] = None  # future: extract from context or message

    try:
        _span_ctx = mlflow.start_span(
            name="chat_service.stream",
            attributes={
                "conversation_id": request.conversation_id or "new",
                "user_id": user_id,
                "task_name": task_name or "",
                "guardrail_category": classify_message(request.message) or "",
            },
        )
    except Exception:
        _span_ctx = contextlib.nullcontext()

    with _span_ctx:
        # Resolve or create conversation
        if request.conversation_id:
            result = await get_conversation_messages(db, request.conversation_id, user_id)
            if result is None:
                yield _event({"type": "error", "code": "unauthorized"})
                return
            conversation, history = result
        else:
            conversation = await create_conversation(
                db, user_id, request.context.site_id
            )
            history = []

        conversation_id = conversation.id
        yield _event({"type": "conversationId", "id": conversation_id})

        # Persist user message
        await append_message(db, conversation_id, MessageRole.user, request.message)

        # Build message list for LangGraph
        system_prompt = load_instructions(task_name)
        lc_messages = [SystemMessage(content=system_prompt)]

        # Truncate history if too long
        if len(history) > _MAX_HISTORY:
            history = history[-_TRUNCATED_HISTORY:]
        for msg in history:
            if msg.role == MessageRole.user:
                lc_messages.append(HumanMessage(content=msg.content))
            else:
                lc_messages.append(AIMessage(content=msg.content))
        lc_messages.append(HumanMessage(content=request.message))

        # Stream from LangGraph — 30 s timeout per event to detect hung tool calls
        full_response = ""
        try:
            gen = get_chat_graph().astream_events(
                {"messages": lc_messages}, version="v2"
            )
            while True:
                try:
                    event = await asyncio.wait_for(gen.__anext__(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield _event({"type": "error", "code": "timeout"})
                    return
                except StopAsyncIteration:
                    break

                evt = event["event"]
                if evt == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = chunk.content if hasattr(chunk, "content") else ""
                    if text:
                        full_response += text
                        yield _event({"type": "delta", "text": text})
                elif evt == "on_tool_start":
                    yield _event({"type": "tool_start", "tool": event.get("name", "")})
                elif evt == "on_tool_end":
                    yield _event({"type": "tool_end", "tool": event.get("name", "")})
        except Exception as exc:
            code = _map_error(exc)
            yield _event({"type": "error", "code": code})
            return

        # Persist assistant message
        await append_message(db, conversation_id, MessageRole.assistant, full_response)

        # Auto-title first message
        if not history and full_response:
            asyncio.create_task(
                _auto_title(conversation_id, request.message)
            )

        yield _event({"type": "done"})


async def _auto_title(conversation_id: str, first_message: str) -> None:
    from app.resources.database import _get_session_factory

    title = first_message[:60].strip()
    if len(first_message) > 60:
        title += "…"
    try:
        async with _get_session_factory()() as db:
            await update_title(db, conversation_id, title)
    except Exception:
        pass


def _event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _map_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "ratelimit" in name:
        return "rate_limit"
    if "timeout" in name:
        return "timeout"
    if "authentication" in name or "api" in name:
        return "upstream_error"
    logger.exception("Unexpected error in chat stream: %s", exc)
    return "internal_error"
