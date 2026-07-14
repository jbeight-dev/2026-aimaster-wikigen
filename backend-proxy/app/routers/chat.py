import logging
import os

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..errors import AppError
from ..ids import new_id
from ..models import ChatMessage, Document, Space, User
from ..schemas import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageListResponse,
    ChatMessageSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

NO_APPROVED_DOCUMENTS_TEXT = "아직 승인된 문서가 없어서 답변할 수 없어요. 문서를 먼저 승인해주세요."

ASSISTANT_API_BASE_URL = os.getenv("assistant_API_BASE_URL", "http://127.0.0.1:8001")


def _get_space_or_404(db: Session, space_id: str) -> Space:
    space = db.get(Space, space_id)
    if not space:
        raise AppError(404, "SPACE_NOT_FOUND", "존재하지 않는 Space입니다.")
    return space


async def _call_assistant_chat(
    space_id: str, user_id: str, question: str, history: list[dict]
) -> dict:
    url = f"{ASSISTANT_API_BASE_URL}/assistant/v1/chat"
    payload = {
        "space_id": space_id,
        "user_id": user_id,
        "question": question,
        "history": history,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("assistant chat call failed for space_id %s", space_id)
        raise AppError(502, "ASSISTANT_CALL_FAILED", "답변 생성 중 오류가 발생했어요.") from None
    return response.json()


@router.post(
    "/spaces/{space_id}/chat/messages",
    response_model=ChatMessageCreateResponse,
)
async def create_chat_message(
    space_id: str,
    body: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_space_or_404(db, space_id)

    history = [
        {"role": m.role, "text": m.text}
        for m in (
            db.query(ChatMessage)
            .filter(ChatMessage.space_id == space_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
    ]

    user_message = ChatMessage(
        message_id=new_id("msg"),
        space_id=space_id,
        role="user",
        text=body.text,
        source_document_ids=[],
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    approved_documents = (
        db.query(Document)
        .filter(Document.space_id == space_id, Document.status == "approved")
        .all()
    )

    if not approved_documents:
        assistant_text = NO_APPROVED_DOCUMENTS_TEXT
        source_document_ids: list[str] = []
    else:
        result = await _call_assistant_chat(space_id, current_user.user_id, body.text, history)
        assistant_text = result.get("answer", "")
        source_document_ids = [
            source["document_id"] for source in result.get("sources", [])
        ]

    assistant_message = ChatMessage(
        message_id=new_id("msg"),
        space_id=space_id,
        role="assistant",
        text=assistant_text,
        source_document_ids=source_document_ids,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return ChatMessageCreateResponse(
        user_message=ChatMessageSchema.model_validate(user_message),
        assistant_message=ChatMessageSchema.model_validate(assistant_message),
    )


@router.get("/spaces/{space_id}/chat/messages", response_model=ChatMessageListResponse)
def list_chat_messages(
    space_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_space_or_404(db, space_id)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.space_id == space_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return ChatMessageListResponse(
        items=[ChatMessageSchema.model_validate(m) for m in messages]
    )
