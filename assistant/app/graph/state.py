from typing import TypedDict


class DocRef(TypedDict):
    document_id: str
    title: str


class Hit(TypedDict):
    doc_id: str
    score: float


class AssistantState(TypedDict, total=False):
    space_id: str
    question: str  # 재작성될 수 있음 (검색 질의)
    original_question: str  # 재시도에도 불변, 최종 답변 생성에 사용
    history: list[dict]
    allowed_doc_ids: list[str]
    doc_id_map: dict[str, DocRef]  # wiki_doc_id -> {document_id, title}

    question_embedding: list[float]
    summary_hits: list[Hit]
    chunk_hits: list[Hit]

    context: str
    answer: str
    source_document_ids: list[str]  # wiki_doc_id 목록 (proxy document_id 아님)
    doc_scores: dict[str, float]  # wiki_doc_id -> 최고 매칭 점수

    retry_count: int
    similarity_score: float
    context_precision: float
    context_recall: float
    ragas_score: float
    confidence_score: float
