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


def _retry_or_give_up(state: AssistantState) -> str:
    if state.get("retry_count", 0) < config.MAX_RETRIES:
        return "query_rewriter"
    return "no_context_answer"


def route_after_hits(state: AssistantState) -> str:
    """1차(저비용) 필터: 검색 히트 자체가 없거나 너무 낮으면 컨텍스트를 만들지 않는다."""
    best = [
        h["score"]
        for h in state.get("summary_hits", []) + state.get("chunk_hits", [])
    ]
    if best and max(best) >= config.MIN_SCORE:
        return "build_context"
    return _retry_or_give_up(state)


def route_after_confidence(state: AssistantState) -> str:
    """2차(심층) 필터: RAGAS 스타일 confidence_score 기준으로 답변/재시도/포기를 결정."""
    if state.get("confidence_score", 0.0) >= config.CONFIDENCE_THRESHOLD:
        return "generate_answer"
    return _retry_or_give_up(state)


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


def confidence_checker(state: AssistantState) -> dict:
    doc_scores = state.get("doc_scores", {})
    similarity_score = max(0.0, min(1.0, max(doc_scores.values(), default=0.0)))

    context = state.get("context", "")
    if not context:
        return {
            "similarity_score": similarity_score,
            "context_precision": 0.0,
            "context_recall": 0.0,
            "ragas_score": 0.0,
            "confidence_score": 0.0,
        }

    try:
        ragas = llm.evaluate_context(state["original_question"], context)
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    ragas_score = (ragas["context_precision"] + ragas["context_recall"]) / 2
    confidence_score = similarity_score * 0.4 + ragas_score * 0.6

    print(
        f"[assistant] confidence_score={confidence_score:.2f} "
        f"(similarity={similarity_score:.2f}, ragas={ragas_score:.2f}) "
        f"retry_count={state.get('retry_count', 0)} space_id={state['space_id']}"
    )

    return {
        "similarity_score": similarity_score,
        "context_precision": ragas["context_precision"],
        "context_recall": ragas["context_recall"],
        "ragas_score": ragas_score,
        "confidence_score": confidence_score,
    }


def query_rewriter(state: AssistantState) -> dict:
    try:
        rewritten = llm.rewrite_query(state["original_question"], state["question"])
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    retry_count = state.get("retry_count", 0) + 1
    print(
        f"[assistant] retry_count={retry_count} rewritten_query={rewritten!r} "
        f"space_id={state['space_id']}"
    )
    return {"question": rewritten, "retry_count": retry_count}


def generate_answer_node(state: AssistantState) -> dict:
    history = state.get("history", [])
    recent_turns = config.RECENT_HISTORY_TURNS
    recent_history = history[-recent_turns:] if recent_turns else history
    older_history = history[: len(history) - len(recent_history)]

    try:
        conversation_summary = (
            llm.summarize_history(older_history) if older_history else ""
        )
        answer = llm.generate_answer(
            state["context"],
            state["original_question"],
            recent_history,
            conversation_summary,
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
