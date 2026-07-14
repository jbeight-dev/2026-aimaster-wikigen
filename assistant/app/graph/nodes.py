from sqlalchemy.orm import Session

from .. import config
from ..clients import llm, vectordb
from ..errors import AppError
from ..models import WikiMd
from .state import AssistantState

NO_CONTEXT_TEXT = "질문에 관련된 문서를 찾지 못했어요."


def retrieve_summary(state: AssistantState) -> dict:
    try:
        embedding = llm.embed_text(state["question"])
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    try:
        hits = vectordb.search_summary(
            embedding, state["allowed_doc_ids"], config.TOP_K_SUMMARY
        )
    except Exception as e:
        raise AppError(502, "QDRANT_UNAVAILABLE", "검색 엔진 연결에 실패했어요.") from e

    print(f"[assistant] summary_hits={len(hits)} space_id={state['space_id']}")
    return {"question_embedding": embedding, "summary_hits": hits}


def retrieve_chunk(state: AssistantState) -> dict:
    try:
        hits = vectordb.search_chunk(
            state["question_embedding"], state["allowed_doc_ids"], config.TOP_K_CHUNK
        )
    except Exception as e:
        raise AppError(502, "QDRANT_UNAVAILABLE", "검색 엔진 연결에 실패했어요.") from e

    print(
        f"[assistant] summary_hits={len(state.get('summary_hits', []))} "
        f"chunk_hits={len(hits)} space_id={state['space_id']}"
    )
    return {"chunk_hits": hits}


def has_context(state: AssistantState) -> str:
    best = [
        h["score"]
        for h in state.get("summary_hits", []) + state.get("chunk_hits", [])
    ]
    if best and max(best) >= config.MIN_SCORE:
        return "build_context"
    return "no_context_answer"


def no_context_answer(state: AssistantState) -> dict:
    return {"answer": NO_CONTEXT_TEXT, "source_document_ids": [], "doc_scores": {}}


def make_build_context(db: Session):
    def build_context(state: AssistantState) -> dict:
        doc_scores: dict[str, float] = {}
        for hit in state.get("summary_hits", []) + state.get("chunk_hits", []):
            doc_scores[hit["doc_id"]] = max(
                doc_scores.get(hit["doc_id"], 0.0), hit["score"]
            )
        ranked_doc_ids = sorted(
            doc_scores, key=lambda doc_id: doc_scores[doc_id], reverse=True
        )

        wiki_docs = (
            db.query(WikiMd).filter(WikiMd.doc_id.in_(ranked_doc_ids)).all()
        )
        wiki_docs_by_id = {d.doc_id: d for d in wiki_docs}

        blocks = []
        used_doc_ids = []
        for doc_id in ranked_doc_ids:
            doc = wiki_docs_by_id.get(doc_id)
            if not doc:
                continue
            blocks.append(f"## {doc.title}\n{doc.body}")
            used_doc_ids.append(doc_id)

        return {
            "context": "\n\n".join(blocks),
            "source_document_ids": used_doc_ids,
            "doc_scores": doc_scores,
        }

    return build_context


def generate_answer_node(state: AssistantState) -> dict:
    try:
        answer = llm.generate_answer(
            state["context"], state["question"], state.get("history", [])
        )
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e
    return {"answer": answer}


def extract_sources(state: AssistantState) -> dict:
    print(
        f"[assistant] answer generated space_id={state['space_id']} "
        f"sources={len(state.get('source_document_ids', []))}"
    )
    return {}
