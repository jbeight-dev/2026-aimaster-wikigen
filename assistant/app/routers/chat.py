from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import AppError
from ..graph.graph import build_graph
from ..graph.nodes import NO_CONTEXT_TEXT
from ..models import Document
from ..schemas import ChatRequest, ChatResponse, Source

router = APIRouter(tags=["assistant"])


def _allowed_documents(db: Session, space_id: str) -> dict[str, dict]:
    """space_id 내 승인된 문서의 wiki_doc_id -> {document_id, title} 매핑."""
    try:
        rows = (
            db.query(Document.document_id, Document.wiki_doc_id, Document.title)
            .filter(
                Document.space_id == space_id,
                Document.status == "approved",
                Document.wiki_doc_id.isnot(None),
            )
            .all()
        )
    except Exception as e:
        raise AppError(502, "DB_UNAVAILABLE", "데이터베이스 연결에 실패했어요.") from e

    return {
        row.wiki_doc_id: {"document_id": row.document_id, "title": row.title}
        for row in rows
    }


@router.post("/assistant/v1/chat", response_model=ChatResponse)
def create_chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
):
    if not body.space_id or not body.question:
        raise AppError(400, "INVALID_REQUEST", "space_id/question은 필수예요.")

    print(f"[assistant] chat requested space_id={body.space_id} user_id={body.user_id}")

    doc_id_map = _allowed_documents(db, body.space_id)
    if not doc_id_map:
        return ChatResponse(answer=NO_CONTEXT_TEXT, sources=[])

    graph = build_graph(db)
    result = graph.invoke(
        {
            "space_id": body.space_id,
            "question": body.question,
            "original_question": body.question,
            "history": [turn.model_dump() for turn in body.history],
            "allowed_doc_ids": list(doc_id_map.keys()),
            "doc_id_map": doc_id_map,
            "retry_count": 0,
        },
        config={"recursion_limit": 50},
    )

    doc_scores = result.get("doc_scores", {})
    sources = [
        Source(
            document_id=doc_id_map[doc_id]["document_id"],
            title=doc_id_map[doc_id].get("title", ""),
            score=doc_scores.get(doc_id, 0.0),
        )
        for doc_id in result.get("source_document_ids", [])
    ]

    return ChatResponse(answer=result["answer"], sources=sources)
