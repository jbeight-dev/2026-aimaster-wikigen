# Backend Proxy

Knowledge Space API (FastAPI + SQLAlchemy + PostgreSQL). 명세: [../docs/api-spec.md](../docs/api-spec.md)

## 실행 방법

1. 가상환경 활성화 (저장소 루트에 `.venv` 존재)

   ```bash
   source ../.venv/bin/activate
   ```

2. 의존성 설치

   ```bash
   pip install -r requirements.txt
   ```

3. `.env` 작성 (`backend-proxy/.env`)

   ```
   DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<db>
   ```

4. 서버 실행 (localhost:8000)

   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. 확인: http://localhost:8000/docs (Swagger UI)

서버 시작 시 테이블 자동 생성(`create_all`) 및 데모 사용자(`usr_hong`, `usr_lee`) 시딩이 수행됩니다.

## 업무 흐름도

### 전체 흐름 (인증 → Space → File → Document → Chat)

```mermaid
flowchart TD
    A[클라이언트] -->|"GET /auth/users"| B[데모 사용자 목록 조회]
    B -->|"POST /auth/switch user_id"| C["토큰 발급 demo.usr_xxx"]
    C -->|"Authorization: Bearer 토큰"| D[이후 모든 요청 인증<br/>deps.get_current_user]

    D --> E["POST /spaces<br/>Space 생성"]
    E --> F["POST /spaces/id/files<br/>파일 업로드 multipart"]
    F -->|확장자 검증| F1{지원 확장자?<br/>pdf/docx/txt/md/db..}
    F1 -->|Yes| F2["File 저장(idle)<br/>storage/uploads/file_id/"]
    F1 -->|No| F3["File(upload_failed)"]

    F2 --> G["POST /files/id/analyze<br/>(idle 상태만 가능)"]
    G --> H["status=analyzing<br/>Builder 서비스로 SSE 스트리밍 요청"]
    H --> I{Builder 분석 결과}
    I -->|성공 doc_ids| J[각 문서 Builder에서 조회<br/>WikiMd 테이블 upsert]
    J --> K{15% 랜덤 실패<br/>or wiki 없음}
    K -->|실패| L["status=analysis_failed"]
    K -->|성공| M["WikiMd → Document 변환<br/>status=done"]
    L -->|"POST /files/id/retry"| G

    M --> N["GET /spaces/id/documents<br/>검토 대기 문서 목록"]
    N --> O{"검토 액션"}
    O -->|"PATCH /documents/id"| O1[섹션 내용 수정<br/>pending/rejected만 가능]
    O -->|"POST /documents/id/approve"| O2["Builder 승인 색인 API 호출<br/>status=approved, version+1"]
    O -->|"POST /documents/id/reject"| O3["status=rejected + 사유"]
    O -->|"POST /documents/id/reopen"| O4["rejected→pending 재검토"]

    O2 --> P["POST /spaces/id/chat/messages<br/>질문 등록"]
    P --> Q{"Space 내 승인된<br/>Document 존재?"}
    Q -->|없음| Q1["안내 메시지 반환<br/>(Assistant 호출 없음)"]
    Q -->|있음| Q2["Assistant 서비스 호출<br/>(question+history 전달)"]
    Q2 --> Q3["답변 + 근거 문서(source_document_ids)<br/>ChatMessage 저장"]
```

### 파일 분석 상세 시퀀스 (Builder 연동, SSE)

```mermaid
sequenceDiagram
    participant C as Client
    participant BP as backend-proxy
    participant DB as DB (File/WikiMd/Document)
    participant BD as Builder 서비스(외부)

    C->>BP: POST /files/{id}/analyze
    BP->>DB: status=analyzing, step_index=0
    BP->>BD: POST /builderapi/v1/ingest (파일 스트림)
    activate BD
    loop SSE 이벤트 스트림
        BD-->>BP: event=start (step명)
        BP->>DB: step_message 갱신
        BD-->>BP: event=finish (완료 step)
        BP->>DB: step_index 증가
    end
    BD-->>BP: event=result (doc_ids[])
    deactivate BD

    loop doc_ids 만큼
        BP->>BD: GET /builderapi/v1/documents/{doc_id}
        BD-->>BP: 문서 payload
        BP->>DB: WikiMd upsert
    end

    BP->>BP: _finalize_analysis
    alt 15% 랜덤 실패 or WikiMd 없음
        BP->>DB: File.status=analysis_failed
    else 성공
        BP->>DB: WikiMd별 Document 생성<br/>(관련 문서 relations 매핑)
        BP->>DB: File.status=done
    end
    BP-->>C: {file_id, status}
```

**핵심 포인트**

- **인증**: 실제 JWT가 아니라 `demo.<user_id>` 형태의 데모 토큰(`app/deps.py`).
- **분석은 동기 호출**: `/files/{id}/analyze`가 Builder 스트리밍 응답을 끝까지 기다린 후 응답하며(`app/routers/files.py`), 진행률은 SSE 이벤트마다 DB에 즉시 반영되어 폴링으로 확인 가능.
- **의도적 실패 주입**: `FAILURE_RATE=0.15`로 분석 완료 후에도 15% 확률로 실패 처리(`app/routers/files.py`) — 데모/테스트용 흔들기.
- **문서 승인 시 Builder에 재통보**: `approve`가 Builder의 `/documents/{wiki_doc_id}/approve`를 호출해 색인 상태를 동기화(`app/routers/documents.py`).
- **챗봇은 승인된 문서만 참조**: 승인 문서가 하나도 없으면 Assistant를 호출하지 않고 고정 안내 문구를 반환(`app/routers/chat.py`).


