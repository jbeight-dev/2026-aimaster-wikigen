import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import observability
from ..database import get_db
from ..errors import AppError
from ..graph.graph import build_graph
from ..graph.nodes import NO_CONTEXT_TEXT
from ..models import Document
from ..schemas import ChatRequest, ChatResponse, Source

router = APIRouter(tags=["assistant"])


def _top_hits(hits: list[dict], limit: int = 5) -> list[dict]:
    return [
        {"doc_id": h["doc_id"], "score": round(h["score"], 4)} for h in hits[:limit]
    ]


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

    request_id = observability.new_request_id()
    observability.start_request_metrics()
    request_start = time.perf_counter()

    observability.log_event(
        "chat_requested", request_id=request_id, space_id=body.space_id, user_id=body.user_id
    )

    doc_id_map = _allowed_documents(db, body.space_id)
    if not doc_id_map:
        observability.log_event(
            "assistant_chat",
            request_id=request_id,
            space_id=body.space_id,
            user_id=body.user_id,
            user_question=body.question,
            no_approved_documents=True,
            total_response_time_ms=round((time.perf_counter() - request_start) * 1000, 1),
        )
        return ChatResponse(answer=NO_CONTEXT_TEXT, sources=[])

    graph = build_graph(db)
    result = graph.invoke(
        {
            "request_id": request_id,
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

    total_response_time_ms = (time.perf_counter() - request_start) * 1000
    metrics = observability.get_request_metrics()

    doc_scores = result.get("doc_scores", {})
    doc_headings = result.get("doc_headings", {})
    sources = [
        Source(
            document_id=doc_id_map[doc_id]["document_id"],
            title=doc_id_map[doc_id].get("title", ""),
            score=doc_scores.get(doc_id, 0.0),
            heading=doc_headings.get(doc_id, ""),
        )
        for doc_id in result.get("source_document_ids", [])
    ]

    reranked_chunks = result.get("reranked_chunks", [])
    observability.log_event(
        "assistant_chat",
        request_id=request_id,
        space_id=body.space_id,
        user_id=body.user_id,
        user_question=body.question,
        optimized_query=result.get("question"),
        summary_retrieval={
            "count": len(result.get("summary_hits", [])),
            "top": _top_hits(result.get("summary_hits", [])),
        },
        chunk_retrieval={
            "count": len(result.get("chunk_hits", [])),
            "top": _top_hits(result.get("chunk_hits", [])),
        },
        rerank_result=[
            {
                "doc_id": c["doc_id"],
                "heading": c.get("heading") or c.get("section_path", ""),
                "rerank_score": round(c.get("rerank_score", 0.0), 4),
            }
            for c in reranked_chunks
        ],
        context_length=len(result.get("context", "")),
        confidence_score=result.get("confidence_score"),
        retry_count=result.get("retry_count", 0),
        llm_response_time_ms=round(metrics.get("llm_time_ms", 0.0), 1),
        token_usage={
            "prompt_tokens": metrics.get("prompt_tokens", 0),
            "completion_tokens": metrics.get("completion_tokens", 0),
            "total_tokens": metrics.get("total_tokens", 0),
        },
        total_response_time_ms=round(total_response_time_ms, 1),
        source_count=len(sources),
    )

    return ChatResponse(answer=result["answer"], sources=sources)
