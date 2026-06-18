import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.clients.auth_verifier import get_user_id
from app.resources.database import get_db
from app.resources.schemas import ChatRequest
from app.services.chat_service import stream_chat

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    user_id = await get_user_id(request)

    async def _generator():
        try:
            async for chunk in stream_chat(db, user_id, body):
                yield chunk
        except Exception as exc:
            logger.exception("Unhandled exception in chat stream generator")
            yield f"data: {json.dumps({'type': 'error', 'code': 'internal_error'})}\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
