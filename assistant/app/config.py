import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_SUMMARY_COLLECTION = os.getenv("QDRANT_SUMMARY_COLLECTION", "wiki_summary")
QDRANT_CHUNK_COLLECTION = os.getenv("QDRANT_CHUNK_COLLECTION", "wiki_chunk")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "aitl-prd-text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")

TOP_K_SUMMARY = int(os.getenv("TOP_K_SUMMARY", "5"))
TOP_K_CHUNK = int(os.getenv("TOP_K_CHUNK", "8"))
# Chunk Reranker가 최종적으로 Context Builder에 넘기는 Chunk 개수.
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))
# Chunk Reranker 점수 = semantic*W_SEMANTIC + heading_match*W_HEADING
#                      + keyword_match*W_KEYWORD + metadata_match*W_METADATA (합 1.0)
RERANK_WEIGHT_SEMANTIC = float(os.getenv("RERANK_WEIGHT_SEMANTIC", "0.6"))
RERANK_WEIGHT_HEADING = float(os.getenv("RERANK_WEIGHT_HEADING", "0.2"))
RERANK_WEIGHT_KEYWORD = float(os.getenv("RERANK_WEIGHT_KEYWORD", "0.15"))
RERANK_WEIGHT_METADATA = float(os.getenv("RERANK_WEIGHT_METADATA", "0.05"))
# 관련성 없는 검색 결과를 no_context로 보내기 위한 1차(저비용) 임계값. 실제 Qdrant
# 데이터의 점수 분포를 보고 튜닝이 필요하다(assistant/readme.md 참고).
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.2"))
# 컨텍스트 구성 후 RAGAS 스타일 평가를 더한 2차(심층) 임계값. 미달 시 쿼리를
# 재작성해 재검색한다.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
# 답변 생성 시 원문 그대로 사용할 최근 대화 턴 수. 이보다 이전 턴은 요약해서 사용한다.
RECENT_HISTORY_TURNS = int(os.getenv("RECENT_HISTORY_TURNS", "4"))
