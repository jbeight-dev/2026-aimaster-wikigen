# AI Master Wikigen

사내/팀에 흩어진 문서(기획서, 스펙, DB 스키마 등)를 업로드하면 AI가 위키 형태로 구조화하고, 사람이 검토·승인한 문서만 신뢰 가능한 지식베이스(Knowledge Space)로 축적하는 프로토타입입니다. 축적된 위키는 자연어 질의응답(Q&A)으로 탐색할 수 있습니다.

자세한 배경/요구사항은 [docs/prd.md](docs/prd.md), Assistant 관련 요구사항은 [docs/prd-assistant.md](docs/prd-assistant.md) 참고.

## 구조

3개의 독립 서비스로 구성됩니다.

| 서비스 | 경로 | 포트 | 역할 |
|---|---|---|---|
| Frontend | [frontend/](frontend/) | 3000 | 사용자 화면 (React + TS + Vite) |
| Backend Proxy | [backend-proxy/](backend-proxy/) | 8000 | Frontend의 단일 진입점. 인증, Knowledge Space/문서 관리, Builder 연계 (FastAPI + SQLAlchemy + PostgreSQL) |
| Assistant | [assistant/](assistant/) | 8001 | 위키 질의응답 서비스 (FastAPI + LangGraph + Qdrant) |

Frontend는 항상 Backend Proxy만 호출하며, Builder/Assistant 같은 내부 서비스는 직접 호출하지 않습니다. 전체 아키텍처와 요청 흐름은 [docs/01_architecture.md](docs/01_architecture.md) 참고.

```
User → Frontend(:3000) → Backend Proxy(:8000) → Builder / Assistant(:8001)
```

## 실행 방법

저장소 루트에 Python 가상환경(`.venv`)이 있고, `backend-proxy`/`assistant`가 이를 공유합니다.

### 1. Backend Proxy (localhost:8000)

```bash
source .venv/bin/activate
cd backend-proxy
pip install -r requirements.txt
# .env 작성 (DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<db>)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

서버 시작 시 테이블 자동 생성 및 데모 사용자(`usr_hong`, `usr_lee`) 시딩이 수행됩니다. 자세히: [backend-proxy/readme.md](backend-proxy/readme.md)

### 2. Assistant (localhost:8001)

```bash
source .venv/bin/activate
cd assistant
pip install -r requirements.txt
# .env 작성 (assistant/.env.example 참고, DATABASE_URL은 backend-proxy와 동일 값 공유)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

`QDRANT_URL`/`OPENAI_API_KEY` 등이 비어 있으면 `/assistant/v1/answer`가 에러를 반환합니다. 자세히: [assistant/readme.md](assistant/readme.md)

### 3. Frontend (localhost:3000)

```bash
cd frontend
npm install
npm run dev
```

각 서비스는 `/docs` (Swagger UI, http://localhost:8000/docs, http://localhost:8001/docs)로 API를 확인할 수 있습니다.

## 문서

- [docs/prd.md](docs/prd.md) — 서비스 목적 / 기능 요구사항
- [docs/prd-assistant.md](docs/prd-assistant.md) — Assistant(Q&A) 요구사항
- [docs/01_architecture.md](docs/01_architecture.md) — 전체 아키텍처
- [docs/02_user-scenarios.md](docs/02_user-scenarios.md) — 사용자 시나리오
- [docs/03_api-spec.md](docs/03_api-spec.md) — Backend API 명세
- [docs/21_design-spec.md](docs/21_design-spec.md) — 화면별 디자인 명세
- [docs/22_frontend-conventions.md](docs/22_frontend-conventions.md) — Frontend 개발 규칙
- [docs/tech-stack-frontend.md](docs/tech-stack-frontend.md), [docs/tech-stack-backendproxy.md](docs/tech-stack-backendproxy.md) — 기술 스택
- [docs/vectordb.md](docs/vectordb.md) — Vector DB(Qdrant) 구성
- [docs/test-cases.md](docs/test-cases.md) — 테스트 케이스
- [docs/todo.md](docs/todo.md) — 남은 작업
