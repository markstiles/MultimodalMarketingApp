from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.clients.auth_verifier import get_user_id
from app.resources.database import get_db
from app.resources.schemas import ConversationDetail, ConversationList, ConversationSummary, MessageRead
from app.services.conversation_service import (
    get_conversation_messages,
    list_conversations,
    soft_delete_conversation,
)

router = APIRouter()


@router.get("/conversations", response_model=ConversationList)
async def list_conversations_endpoint(
    request: Request,
    site_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ConversationList:
    user_id = await get_user_id(request)
    conversations, total = await list_conversations(db, user_id, site_id, limit, offset)
    return ConversationList(
        conversations=[
            ConversationSummary(
                id=c.id,
                title=c.title,
                site_id=c.site_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in conversations
        ],
        total=total,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    user_id = await get_user_id(request)
    result = await get_conversation_messages(db, conversation_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv, messages = result
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        site_id=conv.site_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageRead(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    user_id = await get_user_id(request)
    deleted = await soft_delete_conversation(db, conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
