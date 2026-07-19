import logging
import re
import time

from sqlalchemy.orm import Session

from .. import config, observability
from ..clients import llm, vectordb
from ..errors import AppError
from ..models import WikiMd
from .state import AssistantState

logger = logging.getLogger("assistant.nodes")

NO_CONTEXT_TEXT = "질문에 관련된 문서를 찾지 못했어요."

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) >= 2]


def _match_ratio(query_tokens: list[str], target_tokens: list[str]) -> float:
    """target_tokens 중 query_tokens와 부분일치(포함 관계)하는 비율.

    한국어는 조사가 어근에 그대로 붙어(예: '인덱스를') 정확 토큰 일치가 잘 안 맞으므로
    부분 문자열 포함 여부로 완화해서 비교한다.
    """
    if not query_tokens or not target_tokens:
        return 0.0
    matched = sum(
        1
        for qt in query_tokens
        if any(qt in tt or tt in qt for tt in target_tokens)
    )
    return matched / len(query_tokens)


def analyze_question(state: AssistantState) -> dict:
    """Question Analyzer: 공백 정리 + 멀티턴 History 반영해 독립적인 검색 질문을 만든다."""
    question = " ".join(state["question"].split())
    history = state.get("history", [])
    if not history:
        return {"question": question}

    try:
        search_question = llm.analyze_question(question, history)
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    logger.info(
        "analyzed_question=%r request_id=%s space_id=%s",
        search_question, state.get("request_id"), state["space_id"],
    )
    return {"question": search_question}


def optimize_query(state: AssistantState) -> dict:
    """Query Optimizer: 제품명/기능명/기술 용어를 명확히 해 검색 질의를 최적화한다."""
    try:
        optimized = llm.optimize_query(state["question"])
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    logger.info(
        "optimized_query=%r request_id=%s space_id=%s",
        optimized, state.get("request_id"), state["space_id"],
    )
    return {"question": optimized}


def retrieve_summary(state: AssistantState) -> dict:
    try:
        embedding = llm.embed_text(state["question"])
    except Exception as e:
        raise AppError(502, "LLM_API_ERROR", "LLM 호출에 실패했어요.") from e

    start = time.perf_counter()
    try:
        hits = vectordb.search_summary(
            embedding, state["allowed_doc_ids"], config.TOP_K_SUMMARY
        )
    except Exception as e:
        raise AppError(502, "QDRANT_UNAVAILABLE", "검색 엔진 연결에 실패했어요.") from e
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "summary_hits=%d elapsed_ms=%.1f request_id=%s space_id=%s",
        len(hits), elapsed_ms, state.get("request_id"), state["space_id"],
    )
    return {"question_embedding": embedding, "summary_hits": hits}


def retrieve_chunk(state: AssistantState) -> dict:
    start = time.perf_counter()
    try:
        hits = vectordb.search_chunk(
            state["question_embedding"], state["allowed_doc_ids"], config.TOP_K_CHUNK
        )
    except Exception as e:
        raise AppError(502, "QDRANT_UNAVAILABLE", "검색 엔진 연결에 실패했어요.") from e
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "chunk_hits=%d elapsed_ms=%.1f request_id=%s space_id=%s",
        len(hits), elapsed_ms, state.get("request_id"), state["space_id"],
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
        return "rerank_chunks"
    return _retry_or_give_up(state)


def rerank_chunks(state: AssistantState) -> dict:
    """Chunk Reranker: Semantic Similarity + Heading/Keyword/Metadata Match로 재정렬."""
    chunk_hits = state.get("chunk_hits", [])
    if not chunk_hits:
        return {"reranked_chunks": []}

    query_tokens = _tokenize(f"{state.get('original_question', '')} {state.get('question', '')}")
    summary_scores = {h["doc_id"]: h["score"] for h in state.get("summary_hits", [])}
    max_summary_score = max(summary_scores.values(), default=0.0) or 1.0

    scored = []
    for hit in chunk_hits:
        heading_tokens = _tokenize(f"{hit.get('heading', '')} {hit.get('section_path', '')}")
        keyword_tokens = _tokenize(" ".join(hit.get("keywords") or []))

        heading_match = _match_ratio(query_tokens, heading_tokens)
        keyword_match = _match_ratio(query_tokens, keyword_tokens)
        metadata_match = summary_scores.get(hit["doc_id"], 0.0) / max_summary_score

        rerank_score = (
            hit["score"] * config.RERANK_WEIGHT_SEMANTIC
            + heading_match * config.RERANK_WEIGHT_HEADING
            + keyword_match * config.RERANK_WEIGHT_KEYWORD
            + metadata_match * config.RERANK_WEIGHT_METADATA
        )
        scored.append({**hit, "rerank_score": rerank_score})

    scored.sort(key=lambda h: h["rerank_score"], reverse=True)
    top = scored[: config.TOP_K_RERANK]

    logger.info(
        "reranked_chunks=%d/%d top=%r request_id=%s space_id=%s",
        len(top), len(chunk_hits),
        [(c["doc_id"], round(c["rerank_score"], 4)) for c in top],
        state.get("request_id"), state["space_id"],
    )
    return {"reranked_chunks": top}


def route_after_confidence(state: AssistantState) -> str:
    """2차(심층) 필터: RAGAS 스타일 confidence_score 기준으로 답변/재시도/포기를 결정."""
    if state.get("confidence_score", 0.0) >= config.CONFIDENCE_THRESHOLD:
        return "generate_answer"
    return _retry_or_give_up(state)


def no_context_answer(state: AssistantState) -> dict:
    return {
        "answer": NO_CONTEXT_TEXT,
        "source_document_ids": [],
        "doc_scores": {},
        "doc_headings": {},
    }


def make_build_context(db: Session):
    def build_context(state: AssistantState) -> dict:
        reranked = state.get("reranked_chunks", [])

        doc_scores: dict[str, float] = {}
        for hit in state.get("summary_hits", []):
            doc_scores[hit["doc_id"]] = max(doc_scores.get(hit["doc_id"], 0.0), hit["score"])
        for hit in reranked:
            score = hit.get("rerank_score", hit["score"])
            doc_scores[hit["doc_id"]] = max(doc_scores.get(hit["doc_id"], 0.0), score)

        doc_ids = list(dict.fromkeys(hit["doc_id"] for hit in reranked))
        wiki_docs_by_id = {
            d.doc_id: d for d in db.query(WikiMd).filter(WikiMd.doc_id.in_(doc_ids)).all()
        }

        # PRD 6.6: Rerank된 Chunk만 Context로 구성한다. Qdrant chunk payload에
        # 실제 본문(content)이 아직 없으면(Builder 미구현) 문서 전문으로 doc_id당
        # 1회만 폴백한다 — 문서 전체를 반복해서 Context에 밀어넣지 않기 위함이다.
        blocks = []
        used_doc_ids: list[str] = []
        doc_headings: dict[str, str] = {}
        full_body_used: set[str] = set()
        for hit in reranked:
            doc_id = hit["doc_id"]
            doc = wiki_docs_by_id.get(doc_id)
            if not doc:
                continue

            heading = hit.get("heading") or hit.get("section_path") or doc.title
            content = hit.get("content")
            if content:
                blocks.append(f"## {heading}\n{content}")
            elif doc_id not in full_body_used:
                full_body_used.add(doc_id)
                blocks.append(f"## {doc.title}\n{doc.body}")

            if doc_id not in used_doc_ids:
                used_doc_ids.append(doc_id)
                doc_headings[doc_id] = heading

        return {
            "context": "\n\n".join(blocks),
            "source_document_ids": used_doc_ids,
            "doc_scores": doc_scores,
            "doc_headings": doc_headings,
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

    logger.info(
        "confidence_score=%.2f (similarity=%.2f, ragas=%.2f) retry_count=%d "
        "request_id=%s space_id=%s",
        confidence_score, similarity_score, ragas_score,
        state.get("retry_count", 0), state.get("request_id"), state["space_id"],
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
    logger.info(
        "retry_count=%d rewritten_query=%r request_id=%s space_id=%s",
        retry_count, rewritten, state.get("request_id"), state["space_id"],
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
    logger.info(
        "answer generated sources=%d request_id=%s space_id=%s",
        len(state.get("source_document_ids", [])), state.get("request_id"), state["space_id"],
    )
    return {}
