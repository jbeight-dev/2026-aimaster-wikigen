# AI Wiki Assistant (wiki-assistant-py) — PRD

## 1. 개요

`wiki-assistant-py`는 사내 AI Wiki(승인된 문서)만을 근거로 사용자 질문에 답하는 RAG(Retrieval-Augmented Generation) 챗봇 백엔드다. FastAPI로 HTTP API를 제공하며, 핵심 로직은 LangGraph 기반 상태 그래프(`src/graph.py`)로 구현되어 있다.

- **답변 범위**: `approval_status=approved`인 Wiki 문서만 근거로 사용. 근거가 부족하면 추측하지 않고 "담당자 문의" 또는 "정보 부족" 안내로 종료한다.
- **신뢰도 기반 재시도**: 검색 결과의 신뢰도(confidence)를 자체 평가해 기준 미달 시 최대 3회까지 질의를 자동 개선하며 재검색한다.
- **LLM 프로바이더 중립**: Gemini / Azure OpenAI 중 환경변수로 선택 가능하며, 노드 코드는 특정 프로바이더를 몰라도 되도록 추상화되어 있다.

## 2. 시스템 구성

```
HTTP 요청
  → app/main.py (FastAPI 앱)
    → app/api/chat.py (POST /api/v1/chat)
      → app/services/assistant_service.py (AssistantService.chat)
        → src/graph.py (LangGraph 컴파일 그래프, 1회 컴파일 후 재사용)
```

CLI로도 동일 그래프를 실행할 수 있다 (`python -m src.ask "질문"`, `src/ask.py`).

### 계층별 역할

| 계층 | 경로 | 역할 |
|---|---|---|
| API | `app/main.py`, `app/api/chat.py` | FastAPI 앱, 라우팅, 예외 핸들러(400/500), CORS |
| 서비스 | `app/services/assistant_service.py` | 그래프 invoke, 요청/응답 스키마 매핑, 로깅, 실행시간 측정 |
| 스키마 | `app/schemas/request.py`, `response.py` | `ChatRequest`(user_id, question), `ChatResponse`(intent, keywords, answer, confidence_score, retry_count, runtime) |
| 그래프 | `src/graph.py` | 노드 연결, 조건부 라우팅 정의 |
| 노드 | `src/nodes/*.py` | 그래프의 각 처리 단계(질문 분석 → 검색 → 재랭킹 → 컨텍스트 구성 → 신뢰도 평가 → 답변 생성/재작성) |
| 상태 | `src/state.py` | 그래프 전체에서 공유되는 `WikiAssistantState` (TypedDict) |
| 클라이언트 | `src/clients/*.py` | LLM(Gemini/Azure), Vector DB(Qdrant), 메타데이터 DB(Postgres) 연동 |
| 라이브러리 | `src/lib/*.py` | 청킹(`chunk.py`), RAGAS 스타일 평가(`ragas_metrics.py`) |
| 프롬프트 | `src/prompts.py` | 노드별 시스템/사용자 프롬프트 템플릿 |
| 적재 스크립트 | `scripts/ingest.py` | Wiki 마크다운 문서를 청킹 → 임베딩 → Qdrant/Postgres 적재 |
| 설정 | `src/config.py`, `app/core/config.py` | 환경변수 기반 설정(`.env`) |

## 3. 핵심 플로우 — LangGraph 파이프라인

### 3.1 그래프 구조 (`src/graph.py`)

```
START
  → question_analyzer
  → query_optimizer
  → wiki_retriever
  → document_reranker
  → context_builder
  → confidence_checker  ──(조건부 라우팅)──┬─→ answer_generator → END
                                          ├─→ query_rewriter → question_analyzer (루프)
                                          └─→ END (재시도 소진, 담당자 안내)
```

- 그래프 차원의 자동 재시도(`RetryPolicy`)는 `max_attempts=1`로 꺼둔다. LLM 호출 자체의 재시도는 클라이언트 레벨(`_with_retry`, 최대 3회)에서만 처리해 재시도 횟수가 중복 증폭되지 않도록 한다.
- 재시도 루프 때문에 그래프가 최대 4회(최초 1회 + 재시도 3회) 반복 실행될 수 있어, `recursion_limit=50`으로 넉넉히 설정한다.

### 3.2 노드별 상세

#### ① Question Analyzer (`src/nodes/question_analyzer.py`)
- LLM 호출(`generate_json`)로 질문을 분석해 다음을 추출:
  - `intent`: `기능문의` / `용어` / `메뉴/업무절차` / `데이터유입문제` / `기타` 중 하나
  - `entities`: 질문에 명시된 정확한 고유명사(메뉴명, 용어, 시스템명 등) — 검색 정밀도의 핵심 앵커
  - `keywords`: 검색에 유용한 명사구 3~6개 (entities보다 넓은 범위, 동의어 포함 가능)
- `original_question`은 최초 진입 시에만 저장되고 이후 재시도 루프에서도 보존된다 (재작성되는 `question`과 구분).

#### ② Query Optimizer (`src/nodes/query_optimizer.py`)
- LLM 호출 없이 결정론적으로 검색 질의(`search_query`)를 조합.
- `entities`는 검색 정밀도 기여도가 높아 임베딩 텍스트에 2회 반복 포함해 가중치를 준다: `entity + entity + keywords + question`.

#### ③ Wiki Retriever (`src/nodes/wiki_retriever.py`)
- `search_query`(+ 재시도 3차의 `query_variants`)를 임베딩(`embed_text`)한 뒤 Qdrant에서 벡터 검색(`search_chunks`, `top_k`개, `approval_status=approved` 필터).
- Multi Query Retrieval(3차 재시도) 시 여러 질의로 각각 검색 후, 동일 청크(id)는 최고 점수만 남기고 병합.
- 결과를 `retrieved_docs`에 점수 내림차순으로 저장.

#### ④ Document Reranker (`src/nodes/document_reranker.py`)
- LLM 호출 없이 결정론적 스코어 재계산으로 `retrieved_docs`를 재정렬:
  - 벡터 유사도 65% + entity 일치율 15% + keyword 일치율 10% + 최신성(updated_date 정규화) 10%
- 상위 `rerank_top_n`개만 `reranked_docs`로 남긴다.

#### ⑤ Context Builder (`src/nodes/context_builder.py`)
- LLM 호출 없이 `reranked_docs`를 `[번호] (doc_id · title · section)\n텍스트` 형식으로 이어붙여 `context` 문자열 구성.
- 중복 제거한 `sources`(출처 목록: doc_id, title, source_file, doc_type) 생성.

#### ⑥ Confidence Checker (`src/nodes/confidence_checker.py`)
- 답변 생성 전 검색 품질을 평가해 통과/재시도/포기를 결정하는 핵심 게이트.
- **Similarity Score**: reranked 1위 문서의 점수(0~1 클램프).
- **RAGAS 사전 지표** (`src/lib/ragas_metrics.py`의 `evaluate_context`, LLM 심사):
  - `context_precision`: 검색된 내용 중 질문과 실제 관련 있는 비율
  - `context_recall`: 질문에 답하기 위해 필요한 정보가 충분히 포함되었는지
  - `ragas_score = (context_precision + context_recall) / 2`
- **Confidence Score = similarity_score × 0.4 + ragas_score × 0.6**
  - RAGAS 쪽에 더 높은 가중치를 두는 이유: similarity_score는 top-1 벡터 유사도 하나뿐이라 "그럴듯하지만 무관한" 검색에 취약(과거 실제 발생 사례). RAGAS는 검색 문서 전체가 질문에 충분한지 LLM이 직접 판단해 이 실패 모드를 보완.
- 판정 로직:
  - `reranked_docs`가 있고 `confidence_score >= CONFIDENCE_THRESHOLD`(기본 0.7) → **Answer Generator**로 진행
  - 미달 & `retry_count <= MAX_RETRIES`(기본 3) → **Query Rewriter**로 루프 (retry_count +1)
  - 미달 & 재시도 소진 → `escalation_required=True`, "담당자 문의" 안내로 즉시 종료 (Answer Generator 미실행, LLM 호출 절약)
- 이 시점엔 답변이 없어 Faithfulness/Answer Relevancy는 계산 불가 → Answer Generator 단계에서 참고용으로만 평가.

#### ⑦ Query Rewriter (`src/nodes/query_rewriter.py`) — 재시도 전용
- `retry_count`(confidence_checker에서 이미 +1된 값) 에 따라 재시도 차수별로 다른 기법 사용:
  1. **1차: Query Rewriting** — 모호한 표현을 구체화, 플랫폼 용어로 재작성한 한 문장
  2. **2차: Query Expansion** — 동의어/상위어/하위어 등 관련 용어를 덧붙여 확장 질의 생성 (`related_terms` 포함)
  3. **3차: Multi Query Retrieval** — 서로 다른 관점의 검색 질의 3개(`query_variants`) 생성, 원본 질의는 유지
- 도메인 무관 질의(날씨, 잡담 등) 가드: 억지로 플랫폼 용어를 끌어붙이지 않고 원문을 그대로 반환하도록 프롬프트에 명시(`_OUT_OF_DOMAIN_GUARD`).
- 재작성 후 `question_analyzer`로 되돌아가 파이프라인을 처음부터 다시 수행.

#### ⑧ Answer Generator (`src/nodes/answer_generator.py`)
- Confidence Checker 통과 시에만 실행(그래프 조건부 엣지로 보장).
- `context`가 비어있으면 방어적으로 "정보를 찾지 못했다"는 고정 답변(`_NO_CONTEXT_ANSWER`) 반환.
- 시스템 프롬프트(`load_system_prompt`, 외부 파일 `개발환경/AI Wiki Assistant Agent - System Prompt.md`)와 사용자 프롬프트로 LLM 호출 → 구조화 답변(`core_answer`, `detail`, `related_menus`, `references`) 생성.
- 검색에는 재작성된 `question`을 쓰지만, 최종 답변은 `original_question` 기준으로 생성.
- 생성 후 참고용 RAGAS 사후 지표 평가(`evaluate_answer`):
  - `faithfulness`: 답변 주장이 컨텍스트에 실제 근거하는 비율
  - `answer_relevancy`: 답변이 질문 요지에 부합하는 정도
  - `ragas_full_score = (context_precision + context_recall + faithfulness + answer_relevancy) / 4` (4개 지표 균등 가중, 참고용, 재시도 트리거에는 미반영)
- 사용자에게 보여줄 `final_message`를 `[핵심 답변] / [상세 설명] / [관련 메뉴·업무 절차] / [참고 출처]` 형식으로 조립.

### 3.3 상태 (`src/state.py`)

`WikiAssistantState`(TypedDict, total=False)가 그래프 전체에서 공유되는 단일 상태 객체. 주요 필드:
- 질문 관련: `question`(재작성됨), `original_question`(불변), `intent`, `entities`, `keywords`
- 검색 관련: `search_query`, `query_variants`, `retrieved_docs`, `reranked_docs`, `context`, `sources`
- 평가 관련: `similarity_score`, `context_precision`, `context_recall`, `ragas_score`, `confidence_score`, `faithfulness`, `answer_relevancy`, `ragas_full_score`
- 제어 관련: `retry_count`, `last_rewrite_technique`, `escalation_required`, `attempt_log`(누적 로그, `operator.add`로 병합)
- 결과: `answer`(구조화), `final_message`(사용자 노출 텍스트)

## 4. 신뢰도 평가 체계 (RAGAS 스타일)

`src/lib/ragas_metrics.py`는 실제 `ragas` 패키지 대신, 정답 레퍼런스가 없는 라이브 질의 환경에 맞춰 LLM을 평가자로 사용하는 reference-free 방식을 채택한다.

| 지표 | 계산 시점 | 용도 |
|---|---|---|
| context_precision | 검색 직후 (Confidence Checker) | 재시도 트리거 |
| context_recall | 검색 직후 (Confidence Checker) | 재시도 트리거 |
| similarity_score | 검색 직후 (Confidence Checker) | 재시도 트리거 (RAGAS 노이즈 보정용) |
| faithfulness | 답변 생성 후 (Answer Generator) | 참고/로깅 전용 |
| answer_relevancy | 답변 생성 후 (Answer Generator) | 참고/로깅 전용 |

- Confidence Score(재시도 판단 기준) = `similarity_score × 0.4 + ragas_score × 0.6`
- RAGAS Full Score(참고용) = 4개 지표 단순 평균

## 5. LLM / 임베딩 프로바이더 추상화

`src/clients/llm.py`가 `LLM_PROVIDER` 환경변수(`gemini` | `azure`)에 따라 구현체를 스위칭하는 진입점. 노드는 이 모듈만 import하며 구체 SDK를 몰라도 된다.

| | Gemini (`gemini.py`) | Azure OpenAI (`azure_openai.py`) |
|---|---|---|
| 채팅 모델 | `MODEL_NAME` (기본 gemini-3.5-flash) | `AZURE_CHAT_DEPLOYMENT` (기본 gpt-4.1) |
| 임베딩 모델 | `EMBEDDING_MODEL` (기본 gemini-embedding-001, 3072차원) | `AZURE_EMBEDDING_DEPLOYMENT` (기본 text-embedding-3-large, 3072차원) |
| 구조화 출력 | `response_schema` + `response_mime_type=application/json` | JSON Schema `strict: true` (object마다 `additionalProperties: false` 자동 보강) |
| 재시도 | 429/500/503 시 지수 백오프 최대 3회, RetryInfo 헤더 우선 반영 | 429/500/503 시 지수 백오프 최대 3회, Retry-After 헤더 우선 반영 |

노드는 소문자 JSON Schema(`"type": "object"` 등)로 스키마를 정의하며, 각 클라이언트가 프로바이더 고유 포맷으로 변환한다.

## 6. 데이터 저장소

- **Qdrant** (`src/clients/qdrant.py`): 청크 임베딩 벡터 저장. `docId`, `approvalStatus`를 payload 인덱스로 생성해 필터링 지원. 컬렉션명은 `QDRANT_COLLECTION`(기본 ai_wiki_chunks), 벡터 차원 3072(코사인 유사도).
- **Postgres** (`src/clients/postgres.py`): 문서 메타데이터 테이블(`wiki_documents`) — id, title, doc_type, category, version, 승인 상태, 태그, 관련 메뉴, 요약 등을 upsert.

## 7. 문서 적재 파이프라인 (`scripts/ingest.py`)

```
wiki/*.md (frontmatter 포함, _template.md·AI-Wiki.md 제외)
  → frontmatter 파싱 (id, title, doc_type, tags, related_menus, approval_status 등)
  → chunk_markdown() (src/lib/chunk.py)
  → embed_texts() (선택된 LLM 프로바이더)
  → Qdrant upsert (기존 doc_id 삭제 후 재적재)
  → Postgres upsert_document_metadata
```

- 실행: `python -m scripts.ingest [--no-approve]`. 기본은 데모 목적으로 `approval_status`를 강제로 `approved` 처리하며, `--no-approve` 시 frontmatter의 원래 값(기본 pending)을 유지한다.
- **청킹 규칙** (`src/lib/chunk.py`): `##`/`###` 헤더 기준으로 섹션 분리 → 섹션이 길면 500~1000 토큰(단어 수 근사, target 650 단어) 구간으로 15% 오버랩 슬라이딩 윈도우 분할. 섹션명은 헤딩 경로(`H2 > H3`)로 유지, 분할 시 `(part n/m)` 접미사 부여.

## 8. API 스펙

### `POST /api/v1/chat`

**Request** (`ChatRequest`)
```json
{ "user_id": "string", "question": "string (빈 문자열 불가, 400 반환)" }
```

**Response** (`ChatResponse`, 200)
```json
{
  "status": "success",
  "intent": "메뉴/업무절차",
  "keywords": ["...", "..."],
  "answer": "[핵심 답변]\n...\n\n[상세 설명]\n...\n\n[참고 출처]\n...",
  "confidence_score": 0.82,
  "retry_count": 0,
  "runtime": 1.234
}
```

**오류 응답**
- 400 (`RequestValidationError`): question 누락/공백 등 → `{"status": "error", "answer": "...", intent/keywords/confidence_score/retry_count/runtime: null}`
- 500 (일반 예외): `app/api/chat.py`에서 그래프 실행 중 예외 캐치, `app/core/exception.py`의 `generic_exception_handler`가 전역 핸들러로도 커버.

### `GET /health`
`{"status": "UP"}`

그래프 실행은 동기(블로킹) 호출이라 `asyncio.to_thread`로 이벤트 루프를 막지 않도록 처리(`app/api/chat.py`).

## 9. 설정 (환경변수, `.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LLM_PROVIDER` | gemini | gemini \| azure |
| `GOOGLE_API_KEY` | 필수(gemini) | Gemini API 키 |
| `MODEL_NAME` | gemini-3.5-flash | Gemini 채팅 모델 |
| `EMBEDDING_MODEL` | gemini-embedding-001 | Gemini 임베딩 모델 |
| `AZURE_API_KEY` / `AZURE_ENDPOINT` | 필수(azure) | Azure OpenAI 인증 |
| `AZURE_CHAT_DEPLOYMENT` | gpt-4.1 | Azure 채팅 배포명 |
| `AZURE_EMBEDDING_DEPLOYMENT` | text-embedding-3-large | Azure 임베딩 배포명 |
| `DATABASE_URL` | 필수 | Postgres 연결 문자열 |
| `QDRANT_URL` / `QDRANT_API_KEY` | 필수 | Qdrant 연결 정보 |
| `QDRANT_COLLECTION` | ai_wiki_chunks | Qdrant 컬렉션명 |
| `TOP_K` | 5 | 1차 검색 결과 수 |
| `RERANK_TOP_N` | 3 | 재랭킹 후 유지할 문서 수 |
| `CONFIDENCE_THRESHOLD` | 0.7 | 답변 생성 진입 기준 |
| `MAX_RETRIES` | 3 | 최대 재시도 횟수 |
| `PORT` | 8000 | FastAPI 서버 포트 (`app/core/config.py`) |
| `LOG_LEVEL` | INFO | 로그 레벨 |

## 10. 관측성 / 로깅

- `app/core/logger.py` 기반 구조화 로깅: `CHAT_REQUEST`(user_id, question 길이), `CHAT_RESPONSE`(confidence, retry_count, runtime), `CHAT_ERROR`.
- 그래프 내부적으로는 `attempt_log`(상태 필드, 리스트 누적)에 각 노드의 판단 근거를 텍스트로 기록 — Confidence Checker의 지표 요약, 재시도 시 사용한 기법과 재작성 질의, Answer Generator의 참고 지표 등. CLI(`src/ask.py`)는 이 로그를 그대로 출력해 디버깅에 활용.

## 11. 설계상 트레이드오프 / 의도된 결정

- **그래프 재시도 vs 클라이언트 재시도 분리**: LangGraph 자체 재시도를 끄고 LLM 클라이언트 레벨 재시도(최대 3회)만 사용 — 재시도 횟수가 3×4로 불어나는 것을 방지.
- **사전 지표만 재시도 트리거로 사용**: Faithfulness/Answer Relevancy는 답변 생성 후에만 계산 가능하므로 재시도 로직에 넣지 않고 참고용으로만 기록 — 재시도 여부 판단은 항상 답변 생성 "전" 단계에서 결정.
- **재시도 소진 시 Answer Generator 스킵**: 담당자 문의로 확정될 게 뻔한 경우 불필요한 LLM 호출(비용/지연)을 절약.
- **결정론적 노드와 LLM 노드의 분리**: Query Optimizer/Document Reranker/Context Builder는 LLM 호출 없이 항상 실행 가능해 비용 부담이 없음. LLM 호출은 Question Analyzer/Query Rewriter/Confidence Checker(RAGAS 평가)/Answer Generator에 국한.
- **entities vs keywords 구분**: entities는 질문에 명시된 정확한 고유명사로 검색 정밀도 신호로 가중치를 더 준다(재랭킹 15% vs keywords 10%, query_optimizer에서 2배 반복).
