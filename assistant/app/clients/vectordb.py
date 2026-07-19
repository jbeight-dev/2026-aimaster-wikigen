from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from .. import config

_client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY or None)


def _doc_id_filter(allowed_doc_ids: list[str]) -> Filter:
    return Filter(
        must=[FieldCondition(key="doc_id", match=MatchAny(any=allowed_doc_ids))]
    )


def search_summary(
    query_vector: list[float], allowed_doc_ids: list[str], top_k: int
) -> list[dict]:
    hits = _client.query_points(
        collection_name=config.QDRANT_SUMMARY_COLLECTION,
        query=query_vector,
        query_filter=_doc_id_filter(allowed_doc_ids),
        limit=top_k,
    ).points
    return [
        {
            "doc_id": h.payload["doc_id"],
            "title": h.payload.get("title", ""),
            "keywords": h.payload.get("keywords", []),
            "score": h.score,
        }
        for h in hits
    ]


def search_chunk(
    query_vector: list[float], allowed_doc_ids: list[str], top_k: int
) -> list[dict]:
    hits = _client.query_points(
        collection_name=config.QDRANT_CHUNK_COLLECTION,
        query=query_vector,
        query_filter=_doc_id_filter(allowed_doc_ids),
        limit=top_k,
    ).points
    return [
        {
            "doc_id": h.payload["doc_id"],
            "chunk_id": h.payload.get("chunk_id", ""),
            "heading": h.payload.get("heading", ""),
            "section_path": h.payload.get("section_path", ""),
            # Builder가 아직 채우지 않았을 수 있는 필드 - 없으면 nodes.build_context가
            # Postgres 문서 전문으로 폴백한다.
            "content": h.payload.get("content", ""),
            "keywords": h.payload.get("keywords", []),
            "score": h.score,
        }
        for h in hits
    ]
