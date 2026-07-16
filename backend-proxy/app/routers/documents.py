import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..errors import AppError
from ..models import Document, Space, User
from ..schemas import (
    DocumentRejectRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSchema,
    DocumentUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

BUILDER_API_BASE_URL = os.getenv("builder_API_BASE_URL", "http://localhost:8002")


def _get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if not document or document.status == "deleted":
        raise AppError(404, "DOCUMENT_NOT_FOUND", "존재하지 않는 문서입니다.")
    return document


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


async def _call_builder_approve(wiki_doc_id: str) -> None:
    url = f"{BUILDER_API_BASE_URL}/builderapi/v1/documents/{wiki_doc_id}/approve"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("builder approve call failed for wiki_doc_id %s", wiki_doc_id)
        raise AppError(502, "BUILDER_APPROVE_FAILED", "위키 색인 처리 중 오류가 발생했어요.") from None


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id)
    return DocumentResponse(document=DocumentSchema.model_validate(document))


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id)
    if document.status not in ("pending", "rejected"):
        raise AppError(400, "DOCUMENT_NOT_EDITABLE", "검토 대기 또는 반려 상태에서만 내용을 수정할 수 있어요.")

    document.sections = [section.model_dump(exclude_none=True) for section in body.sections]
    document.history = document.history + [
        {"label": "내용이 수정됨", "time": _now_iso()}
    ]
    db.commit()
    db.refresh(document)
    return DocumentResponse(document=DocumentSchema.model_validate(document))


@router.get("/spaces/{space_id}/documents", response_model=DocumentListResponse)
def list_documents(
    space_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    space = db.get(Space, space_id)
    if not space:
        raise AppError(404, "SPACE_NOT_FOUND", "존재하지 않는 Space입니다.")

    query = db.query(Document).filter(Document.space_id == space_id)
    if status:
        query = query.filter(Document.status == status)
    else:
        query = query.filter(Document.status != "deleted")
    documents = query.all()
    return DocumentListResponse(
        items=[DocumentSchema.model_validate(d) for d in documents]
    )


@router.post("/documents/{document_id}/approve", response_model=DocumentResponse)
async def approve_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id)
    if document.status != "pending":
        raise AppError(400, "DOCUMENT_NOT_PENDING", "검토 대기 상태가 아닙니다.")
    if not document.wiki_doc_id:
        raise AppError(
            400, "DOCUMENT_NOT_LINKED", "원본 위키 문서와 연결되어 있지 않아 승인할 수 없습니다."
        )

    await _call_builder_approve(document.wiki_doc_id)

    document.version += 1
    document.status = "approved"
    document.history = document.history + [
        {"label": f"v{document.version}로 승인됨", "time": _now_iso()}
    ]
    db.commit()
    db.refresh(document)
    return DocumentResponse(document=DocumentSchema.model_validate(document))


@router.post("/documents/{document_id}/reject", response_model=DocumentResponse)
def reject_document(
    document_id: str,
    body: DocumentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id)
    if document.status != "pending":
        raise AppError(400, "DOCUMENT_NOT_PENDING", "검토 대기 상태가 아닙니다.")

    document.status = "rejected"
    document.reject_reason = body.reason or "사유 미입력"
    document.history = document.history + [
        {"label": "반려됨", "time": _now_iso()}
    ]
    db.commit()
    db.refresh(document)
    return DocumentResponse(document=DocumentSchema.model_validate(document))


@router.post("/documents/{document_id}/reopen", response_model=DocumentResponse)
def reopen_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id)
    if document.status != "rejected":
        raise AppError(400, "DOCUMENT_NOT_REJECTED", "반려 상태가 아닙니다.")

    document.status = "pending"
    document.reject_reason = None
    document.history = document.history + [
        {"label": "재검토 대기로 전환됨", "time": _now_iso()}
    ]
    db.commit()
    db.refresh(document)
    return DocumentResponse(document=DocumentSchema.model_validate(document))
