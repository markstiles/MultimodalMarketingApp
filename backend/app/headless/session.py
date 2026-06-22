"""Headless conversation session.

Wraps stream_chat() directly — no HTTP server required.
Parses SSE events and returns clean turn results.
"""
import json
import logging
from dataclasses import dataclass, field

from app.headless.context import ProxyContext

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    response: str
    conversation_id: str
    tool_calls: list[str] = field(default_factory=list)
    canvas_reload: bool = False


class HeadlessSession:
    """Manages a single ongoing conversation via the chat service layer."""

    def __init__(self, context: ProxyContext):
        self.context = context
        self.conversation_id: str | None = None

    async def send(self, message: str) -> TurnResult:
        """Send a user message and return the assistant's complete response.

        Calls stream_chat() directly — the backend must be importable (i.e.
        DATABASE_URL and LLM_API_KEY must be configured in the environment).
        """
        from app.resources.database import _get_session_factory
        from app.resources.schemas import ChatRequest
        from app.services.chat_service import stream_chat

        request = ChatRequest(
            message=message,
            conversation_id=self.conversation_id,
            context=self.context.to_runtime_context(),
        )

        full_response = ""
        tool_calls: list[str] = []
        canvas_reload = False
        new_conversation_id = self.conversation_id

        async with _get_session_factory()() as db:
            async for chunk in stream_chat(db, self.context.user_id, request):
                if not chunk.startswith("data: "):
                    continue
                try:
                    event = json.loads(chunk[6:])
                except json.JSONDecodeError:
                    logger.debug("Unparseable SSE chunk: %r", chunk[:80])
                    continue

                etype = event.get("type")
                if etype == "conversationId":
                    new_conversation_id = event["id"]
                    self.conversation_id = new_conversation_id
                elif etype == "delta":
                    full_response += event.get("text", "")
                elif etype == "tool_start":
                    name = event.get("tool", "")
                    if name:
                        tool_calls.append(name)
                        logger.debug("Tool called: %s", name)
                elif etype == "canvas_reload":
                    canvas_reload = True
                elif etype == "error":
                    code = event.get("code", "unknown")
                    raise RuntimeError(f"Chat service error: {code}")
                elif etype == "done":
                    break

        return TurnResult(
            response=full_response.strip(),
            conversation_id=new_conversation_id or "",
            tool_calls=tool_calls,
            canvas_reload=canvas_reload,
        )
