# AI Wiki Assistant — PRD v3

## 0. 문서 안내

이 문서는 두 개의 층을 통합한다.

- **목표 설계 (Target)** — [PRD_v2.md](./PRD_v2.md)에 기술된 LangGraph 다단계 파이프라인(질문 분석 → 쿼리 최적화 → 검색 → 재랭킹 → 신뢰도 평가/재시도 → 답변 생성). 아직 코드로 구현되지 않은 목표 아키텍처다.
- **현재 구현 (Phase 1)** — `assistant/app/` 아래 실제로 동작 중인 코드. `docs/prd-assistant.md`(최초 설계안)을 바탕으로 구현됐으며, PRD_v2보다 훨씬 단순한 선형 그래프다. **Qdrant 컬렉션 2개(`wiki_summary`, `wiki_chunk`)를 순차 검색해 문서 단위로 병합하는 방식**이 이 Phase의 핵심이다.

두 층은 코드 구조·프로바이더·재시도/신뢰도 로직 등에서 상당히 다르다. 아래 4장이 "현재 실제로 동작하는 것", 5장이 "PRD_v2가 그리는 목표", 6장이 그 사이의 격차다. **지금 코드를 수정하거나 API를 호출할 때는 반드시 4장을 기준으로 삼을 것.**

## 1. 개요

`assistant`는 사내 Wiki(승인된 문서)만을 근거로 사용자 질문에 답하는 RAG 챗봇 백엔드다. FastAPI로 HTTP API를 제공하며, 핵심 로직은 LangGraph 기반 상태 그래프로 구현되어 있다.

- **답변 범위**: `status=approved`인 문서만 근거로 사용. 근거가 부족하면 "관련 문서를 찾지 못했다"는 고정 답변으로 종료한다.
- **Space 격리**: Qdrant payload가 아니라 매 요청 시 Postgres에서 `space_id`로 승인 문서의 `doc_id` 목록을 조회해 Qdrant 검색 필터(allow-list)로 사용한다.
- **2단계 벡터 검색**: 문서 요약(`wiki_summary`)과 문서 청크(`wiki_chunk`) 두 컬렉션을 각각 검색한 뒤, `doc_id`별 최고 점수로 병합해 문서를 랭킹한다.

## 2. 전체 시스템 내 위치

```
User
  │
  ▼
Frontend            localhost:3000
  │
  ▼
Proxy Backend       localhost:8000
  │
  ├─ 문서 분석/Wiki 생성 요청 ──▶ Builder Backend    localhost:8002 ─▶ Qdrant(wiki_chunk, wiki_summary) 색인(upsert)
  │
  └─ 질문하기 요청       ──▶ Assistant Backend  localhost:8001 ─▶ Qdrant(wiki_chunk, wiki_summary) 검색(read-only)
```

- Builder(색인/쓰기)와 Assistant(검색/읽기)는 대칭 관계다. **Assistant는 두 Qdrant 컬렉션에 대해 읽기 전용**이며, 임베딩 생성·upsert는 이 리포지토리에 없는 Builder 서비스가 승인 시점에 수행한다.
- Postgres(`DATABASE_URL`)는 `backend-proxy`와 동일 DB를 공유하며, `documents`/`wikimd` 테이블을 읽기 전용으로 조회한다([models.py](app/models.py)).
- **Proxy 연동은 이미 완료된 상태다.** `backend-proxy/app/routers/chat.py`의 `_call_assistant_chat`이 `POST {ASSISTANT_API_BASE_URL}/assistant/v1/chat`을 호출한다(기본값 `http://127.0.0.1:8001`). `assistant/readme.md`와 `docs/prd-assistant.md` 9장은 "연동 미완료"라고 적혀 있으나 이는 최신 상태를 반영하지 못한 것 — 실제로는 승인 문서가 1건 이상인 Space에서 채팅 메시지를 보내면 항상 Assistant가 호출된다.

## 3. 계층별 역할 (현재 코드 기준)

| 계층 | 경로 | 역할 |
|---|---|---|
| API | [app/main.py](app/main.py), [app/routers/chat.py](app/routers/chat.py) | FastAPI 앱, `/health`, `POST /assistant/v1/chat`, `AppError` 예외 핸들러 |
| 스키마 | [app/schemas.py](app/schemas.py) | `ChatRequest`(space_id, user_id, question, history), `ChatResponse`(answer, sources) |
| 그래프 | [app/graph/graph.py](app/graph/graph.py) | 노드 연결, 조건부 라우팅(`has_context`) |
| 노드 | [app/graph/nodes.py](app/graph/nodes.py) | 단일 파일에 6개 노드 함수 모두 구현 (retrieve_summary/retrieve_chunk/has_context/no_context_answer/build_context/generate_answer/extract_sources) |
| 상태 | [app/graph/state.py](app/graph/state.py) | `AssistantState` (TypedDict) |
| 클라이언트 | [app/clients/llm.py](app/clients/llm.py), [app/clients/vectordb.py](app/clients/vectordb.py) | Azure OpenAI(채팅+임베딩), Qdrant(2개 컬렉션 검색) |
| 모델 | [app/models.py](app/models.py) | `Document`, `WikiMd` — backend-proxy 소유 테이블에 대한 읽기 전용 SQLAlchemy 매핑 |
| 설정 | [app/config.py](app/config.py) | 환경변수 기반 설정(`.env`) |

PRD_v2가 기술한 `src/nodes/*.py` 개별 파일 구조, `src/lib/ragas_metrics.py`, `src/lib/chunk.py`, `scripts/ingest.py`, Gemini/Azure 프로바이더 스위칭 등은 **현재 코드베이스에 존재하지 않는다.** 색인 스크립트가 아예 없는 이유는 색인 자체가 Assistant의 책임이 아니기 때문이다(Builder 담당).

## 4. 현재 구현 — LangGraph 파이프라인과 2-Collection 검색

### 4.1 그래프 구조 ([app/graph/graph.py](app/graph/graph.py))

```
START
  → retrieve_summary
  → retrieve_chunk
  → has_context ──(조건부 라우팅)──┬─→ build_context → generate_answer → extract_sources → END
                                   └─→ no_context_answer → END
```

재시도 루프, 재랭킹 노드, 신뢰도 게이트(RAGAS)는 없다. 순수 선형 흐름이며 그래프가 한 번 이상 반복 실행되는 경우는 없다.

### 4.2 노드별 상세

#### ① `retrieve_summary` ([nodes.py:12-26](app/graph/nodes.py))
- `llm.embed_text(question)`으로 질문을 1회 임베딩(Azure OpenAI Embeddings, `EMBEDDING_MODEL`) → `state["question_embedding"]`에 캐시.
- `vectordb.search_summary(embedding, allowed_doc_ids, TOP_K_SUMMARY)` 호출 → **컬렉션 1: `wiki_summary`**를 검색.
- 결과를 `state["summary_hits"]`에 저장 (`{doc_id, title, score}` 리스트).

#### ② `retrieve_chunk` ([nodes.py:29-41](app/graph/nodes.py))
- ①에서 캐시한 동일 임베딩을 **재사용**(임베딩 API를 두 번 호출하지 않음).
- `vectordb.search_chunk(embedding, allowed_doc_ids, TOP_K_CHUNK)` 호출 → **컬렉션 2: `wiki_chunk`**를 검색.
- 결과를 `state["chunk_hits"]`에 저장 (`{doc_id, section_path, score}` 리스트).

#### 컬렉션 검색 구현 ([app/clients/vectordb.py](app/clients/vectordb.py))
```python
QdrantClient.query_points(
    collection_name=QDRANT_SUMMARY_COLLECTION,  # 또는 QDRANT_CHUNK_COLLECTION
    query=query_vector,
    query_filter=Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=allowed_doc_ids))]),
    limit=top_k,
)
```
- 두 검색 모두 동일한 필터 로직(`doc_id` allow-list)을 쓴다. 이 allow-list는 [routers/chat.py](app/routers/chat.py)의 `_allowed_documents`가 매 요청마다 Postgres `documents` 테이블에서 `space_id` + `status=approved`로 조회해 만든 값이다. **Qdrant payload 자체에는 `space_id` 필드가 없다** — Space 격리는 Qdrant가 아니라 Postgres 조회 결과로 이루어진다.
- `wiki_summary`/`wiki_chunk` payload에는 본문 텍스트가 없다(`title`/`section_path`만). 즉 두 컬렉션은 **문서 랭킹 용도로만 쓰이고, 실제 답변 컨텍스트는 Qdrant가 아니라 Postgres에서 가져온다** (④ 참고).

#### ③ `has_context` ([nodes.py:44-51](app/graph/nodes.py))
- `summary_hits + chunk_hits`를 합친 뒤 최댓값 점수가 `MIN_SCORE`(기본 0.2) 이상이면 `build_context`로, 아니면 `no_context_answer`로 라우팅.
- 미달 시 [nodes.py:54-55](app/graph/nodes.py) `no_context_answer`가 고정 문구("질문에 관련된 문서를 찾지 못했어요.")를 반환하고 종료. LLM 호출 없음.

#### ④ `build_context` ([nodes.py:58-89](app/graph/nodes.py), `make_build_context(db)` 클로저)
- **두 컬렉션 병합 로직**: `summary_hits + chunk_hits`를 순회하며 `doc_id`별로 **두 컬렉션을 통틀어 가장 높은 점수**를 `doc_scores` 딕셔너리에 기록 → 이 병합 점수로 `doc_id`를 내림차순 정렬.
- 정렬된 `doc_id` 순서대로 Postgres `WikiMd` 테이블에서 문서 **전문(body)**을 조회해 `## {title}\n{body}` 블록으로 이어붙여 `context` 문자열 구성.
- `source_document_ids`(정렬된 doc_id 목록), `doc_scores`(병합 점수)를 상태에 반환.

#### ⑤ `generate_answer_node` ([nodes.py:92-99](app/graph/nodes.py))
- Azure OpenAI Chat Completions 1회 호출(`llm.generate_answer`). 시스템 프롬프트는 하드코딩된 한 문장: "컨텍스트에 있는 내용만 근거로 답하고, 없는 내용은 추측하지 말고 모른다고 답해라."
- `history`(멀티턴 이력)를 메시지에 포함. 재시도/재작성/신뢰도 평가 없음.

#### ⑥ `extract_sources` ([nodes.py:102-107](app/graph/nodes.py))
- 로깅만 수행, 상태 변경 없음.

### 4.3 상태 ([app/graph/state.py](app/graph/state.py))

```python
class AssistantState(TypedDict, total=False):
    space_id: str
    question: str
    history: list[dict]
    allowed_doc_ids: list[str]
    doc_id_map: dict[str, DocRef]      # wiki_doc_id -> {document_id, title}

    question_embedding: list[float]
    summary_hits: list[Hit]            # wiki_summary 검색 결과
    chunk_hits: list[Hit]              # wiki_chunk 검색 결과

    context: str
    answer: str
    source_document_ids: list[str]     # wiki_doc_id 목록
    doc_scores: dict[str, float]       # wiki_doc_id -> 병합된 최고 점수
```

PRD_v2의 `retrieved_docs`/`reranked_docs`/`confidence_score`/`retry_count`/`ragas_score` 등에 대응하는 필드는 없다.

### 4.4 API 스펙

#### `POST /assistant/v1/chat`

**Request**
```json
{
  "space_id": "spc_ab12cd34ef",
  "user_id": "string",
  "question": "orders 테이블의 결제 금액 컬럼은 어떤 타입이야?",
  "history": [{ "role": "user", "text": "..." }]
}
```

**Response** (200)
```json
{
  "answer": "orders 테이블의 total_price는 REAL 타입입니다.",
  "sources": [{ "document_id": "doc_102", "title": "orders 테이블", "score": 0.83 }]
}
```

- `space_id`/`question` 누락 시 400 `INVALID_REQUEST`.
- 승인 문서가 0건이면 그래프를 실행하지 않고 즉시 `NO_CONTEXT_TEXT` + 빈 `sources` 반환 ([routers/chat.py:46-47](app/routers/chat.py)).
- Qdrant 연결 실패 → 502 `QDRANT_UNAVAILABLE`, LLM 호출 실패 → 502 `LLM_API_ERROR`, Postgres 실패 → 502 `DB_UNAVAILABLE` ([app/errors.py](app/errors.py), [nodes.py](app/graph/nodes.py)).

#### `GET /health`
`{"status": "ok"}`

### 4.5 설정 (환경변수, `.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/wikigen` | backend-proxy와 공유하는 Postgres |
| `QDRANT_URL` / `QDRANT_API_KEY` | (필수, 비어있으면 502) | Qdrant 접속 정보 |
| `QDRANT_SUMMARY_COLLECTION` | `wiki_summary` | **컬렉션 1**: 문서 요약 임베딩 |
| `QDRANT_CHUNK_COLLECTION` | `wiki_chunk` | **컬렉션 2**: 문서 청크(섹션) 임베딩 |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_API_VERSION` | (필수) | Azure OpenAI 접속 정보(사내 게이트웨이 경유 가능) |
| `EMBEDDING_MODEL` | `aitl-prd-text-embedding-3-small` | 임베딩 모델 |
| `CHAT_MODEL` | `gpt-4o` | 채팅 모델 |
| `TOP_K_SUMMARY` | 5 | `wiki_summary` 검색 결과 수 |
| `TOP_K_CHUNK` | 8 | `wiki_chunk` 검색 결과 수 |
| `MIN_SCORE` | 0.2 | `has_context` 게이트 임계값 (실제 Qdrant 점수 분포 기준 튜닝 필요) |

Gemini 프로바이더, `CONFIDENCE_THRESHOLD`, `MAX_RETRIES`, `RERANK_TOP_N` 등 PRD_v2의 설정 항목은 존재하지 않는다.

### 4.6 데이터 소스

- **Qdrant**: 두 컬렉션 모두 Builder가 문서 승인 시점에 upsert(색인)한다. Assistant는 읽기 전용. payload에 본문 텍스트가 없어 순수 랭킹 신호로만 쓰인다.
  - `wiki_summary`: `doc_id`, `title` (+벡터)
  - `wiki_chunk`: `doc_id`, `section_path` (+벡터)
- **Postgres**:
  - `documents` — `document_id`, `space_id`, `wiki_doc_id`, `status`, `title`. Space 내 승인 문서 필터링(allow-list 생성)에 사용.
  - `wikimd` — `doc_id`, `space_id`, `title`, `summary`, `body`. **답변 컨텍스트의 실제 텍스트 소스**(`body` 전문을 그대로 프롬프트에 포함).

### 4.7 설계상 특징 / 알려진 한계

- **랭킹과 본문 소스의 분리**: 벡터 검색(Qdrant)은 "어떤 문서가 관련 있는가"만 결정하고, 실제 프롬프트에 들어가는 텍스트는 Postgres의 문서 전문이다. 청크 단위 세밀한 발췌가 아니라 문서 전체를 통째로 컨텍스트에 넣으므로, 문서가 길면 프롬프트가 비대해질 수 있다.
- **재시도/신뢰도 평가 없음**: 검색 품질이 낮아도(`MIN_SCORE` 이상이기만 하면) 곧바로 답변을 생성한다. "그럴듯하지만 무관한" 검색 결과에 대한 방어 로직(PRD_v2의 RAGAS 사전 평가)이 없다.
- **LLM 프로바이더 고정**: Azure OpenAI만 지원. 프로바이더 추상화 계층 없음.
- **stateless**: 대화 이력은 Proxy Backend(Postgres `ChatMessage`)가 저장하고, 매 요청마다 `history`로 전달받는다. Assistant 자체는 상태를 갖지 않는다.
- **readme.md/`docs/prd-assistant.md` 일부 내용이 최신 상태를 반영하지 못함**: "Proxy 연동 미완료"라고 적혀 있으나 실제로는 이미 연동되어 있다(2장 참고). 문서 업데이트가 필요하다.

## 5. 목표 설계 (Target — PRD_v2 원안)

아래는 [PRD_v2.md](./PRD_v2.md)가 기술한 목표 아키텍처의 요약이다. 전체 세부사항(프롬프트 설계, RAGAS 산식, 노드별 책임 등)은 PRD_v2.md 원문을 참고할 것. **이 장의 내용은 현재 코드에 구현되어 있지 않다.**

### 5.1 목표 그래프 구조

```
START
  → question_analyzer
  → query_optimizer
  → wiki_retriever
  → document_reranker
  → context_builder
  → confidence_checker  ──(조건부 라우팅)──┬─→ answer_generator → END
                                          ├─→ query_rewriter → question_analyzer (루프, 최대 3회)
                                          └─→ END (재시도 소진, 담당자 안내)
```

### 5.2 현재 대비 목표가 추가하는 것

| 기능 | 목표 설계 (PRD_v2) | 현재 구현 (Phase 1) |
|---|---|---|
| 질문 분석 | LLM이 intent/entities/keywords 추출 | 없음 — 질문 원문을 그대로 임베딩 |
| 검색 질의 구성 | entities 가중치 반복, 결정론적 조합 | 질문 원문 임베딩 1회 |
| 벡터 컬렉션 | 단일 컬렉션(`ai_wiki_chunks`), 청크 텍스트 자체가 컨텍스트 | **2개 컬렉션**(`wiki_summary`+`wiki_chunk`), 병합은 doc_id 최고점수 기준, 텍스트는 Postgres에서 별도 조회 |
| 재랭킹 | 벡터 유사도+entity+keyword+최신성 가중합 | 없음 — Qdrant 점수 그대로 사용 |
| 신뢰도 게이트 | RAGAS(context_precision/recall) + similarity 가중합, threshold 미달 시 재시도 | 단일 threshold(`MIN_SCORE`)만 max-score에 적용 |
| 재시도 | 최대 3회, 기법별 쿼리 재작성(rewriting → expansion → multi-query) | 없음 — 1회 검색 실패 시 즉시 안내 문구로 종료 |
| 답변 후 평가 | faithfulness/answer_relevancy(RAGAS, 참고용) | 없음 |
| LLM 프로바이더 | Gemini/Azure 스위칭 가능 | Azure 고정 |
| 답변 포맷 | `[핵심 답변]/[상세 설명]/[관련 메뉴]/[참고 출처]` 구조화 | 자유 형식 텍스트 1개 |

## 6. 로드맵 제안 (현재 → 목표)

구현 우선순위는 PRD_v2가 방어하고자 하는 실패 모드(무관한 검색 결과에 낮은 신뢰도로 답변)를 기준으로 판단하는 것을 권장한다.

1. **신뢰도 게이트 고도화**: 지금은 `MIN_SCORE` 하나로만 판단한다. PRD_v2의 RAGAS 사전 지표(context_precision/recall)를 `confidence_checker`에 해당하는 노드로 추가하면 "점수는 높지만 무관한" 케이스를 걸러낼 수 있다.
2. **재시도 루프**: 검색 실패 시 즉시 포기하는 대신, 쿼리 재작성(1차) 정도만이라도 먼저 도입해 재검색 기회를 준다.
3. **재랭킹**: `doc_scores` 병합 로직에 entity/keyword 가중치를 추가하는 것은 question_analyzer 없이는 불가능 — 질문 분석 노드 도입이 선행되어야 한다.
4. **청크 단위 컨텍스트**: 현재는 문서 전문을 통째로 넣는다. 문서가 길어지면 토큰 비용 문제가 생기므로, Qdrant `wiki_chunk` payload에 실제 텍스트를 채워 넣거나 Postgres에서 섹션 단위로 발췌하는 방식으로 전환을 검토.
5. **Gemini 프로바이더 추상화**: 우선순위는 낮음 — 현재 Azure 단일 프로바이더로 운영에 지장 없음.

## 7. Open Questions

- `MIN_SCORE`(0.2) 임계값이 실제 Qdrant 점수 분포에 맞게 튜닝되었는지 검증 필요 — 실 데이터 기준 재조정 필요([app/config.py:24-26](app/config.py) 주석 참고).
- 문서 반려/재검토(`reopen`)로 승인이 취소된 경우 Qdrant 두 컬렉션에서도 해당 벡터가 함께 제거/갱신되는지 — Builder 소스가 이 리포지토리에 없어 확인 불가.
- PRD_v2의 목표 아키텍처를 실제 로드맵으로 채택할지, 채택한다면 어떤 순서로 단계적 마이그레이션할지 — 6장은 제안일 뿐 합의된 계획은 아니다.
- `assistant/readme.md`, `docs/prd-assistant.md`의 "Proxy 연동 미완료" 서술을 실제 상태(연동 완료)에 맞게 갱신 필요.
