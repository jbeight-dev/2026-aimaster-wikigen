from typing import TypedDict


class DocRef(TypedDict):
    document_id: str
    title: str


class Hit(TypedDict, total=False):
    doc_id: str
    score: float
    title: str  # summary_hits
    chunk_id: str  # chunk_hits
    heading: str  # chunk_hits
    section_path: str  # chunk_hits
    content: str  # chunk_hits (Builder가 아직 채우지 않았을 수 있음)
    keywords: list[str]  # chunk_hits
    rerank_score: float  # reranked_chunks


class AssistantState(TypedDict, total=False):
    request_id: str  # 로그 상관관계 추적용 (observability.py)
    space_id: str
    question: str  # Question Analyzer/Query Optimizer가 재작성 (검색 질의)
    original_question: str  # 재시도에도 불변, 최종 답변 생성에 사용
    history: list[dict]
    allowed_doc_ids: list[str]
    doc_id_map: dict[str, DocRef]  # wiki_doc_id -> {document_id, title}

    question_embedding: list[float]
    summary_hits: list[Hit]
    chunk_hits: list[Hit]
    reranked_chunks: list[Hit]  # Chunk Reranker 결과 (Top N)

    context: str
    answer: str
    source_document_ids: list[str]  # wiki_doc_id 목록 (proxy document_id 아님)
    doc_scores: dict[str, float]  # wiki_doc_id -> 최고 매칭 점수
    doc_headings: dict[str, str]  # wiki_doc_id -> 최상위 랭크 chunk의 heading

    retry_count: int
    step_count: int  # 콘솔 로그용 STEP 번호 누적 (nodes.py의 _step 데코레이터가 관리)
    similarity_score: float
    context_precision: float
    context_recall: float
    ragas_score: float
    confidence_score: float
