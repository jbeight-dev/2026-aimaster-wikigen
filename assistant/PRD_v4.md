# AI Wiki Assistant PRD

Version: 2.0

---

# 1. 문서 목적

## 1.1 목적

AI Wiki Assistant는 사용자의 자연어 질문에 대해 승인된 Wiki를 기반으로 답변을 생성하는 RAG(Retrieval-Augmented Generation) 서비스이다.

Builder가 생성한 Wiki와 Vector Index를 활용하여 관련 문서를 검색하고, 검색된 Chunk만을 근거(Context)로 사용하여 정확하고 신뢰성 있는 답변을 생성한다.

본 문서는 Assistant의 검색 구조, LangGraph Workflow, Retrieval 전략 및 주요 컴포넌트의 역할을 정의한다.

---

## 1.2 범위

본 문서는 다음 범위를 포함한다.

- Assistant Architecture
- LangGraph Workflow
- Retrieval Flow
- Vector Search Strategy
- Context Generation
- LLM Answer Generation

Builder의 Wiki 생성 과정은 본 문서의 범위에 포함하지 않는다.

---

# 2. 시스템 개요

AI Wiki 시스템은 크게 두 개의 서비스로 구성된다.

| 서비스 | 역할 |
|---------|------|
| Builder | 문서를 Wiki로 변환하고 Vector Index 생성 |
| Assistant | 생성된 Wiki를 검색하여 답변 생성 |

Builder는 승인된 Wiki를 기반으로 Summary와 Chunk Collection을 생성한다.

Assistant는 해당 Collection을 읽기 전용으로 사용한다.

---

# 3. 전체 아키텍처

```
                User

                  │

             Frontend

                  │

          Backend Proxy

                  │

          Assistant Service

                  │

        ┌────────────────────┐
        │                    │
        │     Vector DB       │
        │                    │
        │   wiki_summary      │
        │   wiki_chunk        │
        │                    │
        └────────────────────┘
```

Builder는 Wiki 승인 시 두 Collection을 생성한다.

Assistant는 Retrieval만 수행하며 Vector를 수정하지 않는다.

---

# 4. Assistant 처리 흐름

사용자의 질문은 다음 순서로 처리된다.

```
Question

↓

Embedding

↓

Summary Retrieval

↓

Chunk Retrieval

↓

Chunk Rerank

↓

Context Builder

↓

LLM Answer

↓

Response
```

Summary Collection은 검색 범위를 줄이는 역할을 수행한다.

Chunk Collection은 실제 답변에 사용할 Context를 검색한다.

---

# 5. LangGraph Workflow

Assistant는 LangGraph 기반으로 Workflow를 구성한다.

```
START

↓

Question Analyzer

↓

Query Optimizer

↓

Summary Retriever

↓

Chunk Retriever

↓

Chunk Reranker

↓

Context Builder

↓

Answer Generator

↓

END
```

각 Node는 독립적인 역할을 수행한다.

---

# 6. Node 역할

## 6.1 Question Analyzer

사용자의 질문을 분석한다.

입력

- User Question

출력

- Original Question
- Search Question

주요 역할

- 공백 제거
- 불필요한 표현 제거
- 검색에 적합한 Query 생성
- Multi-turn History 반영

---

## 6.2 Query Optimizer

검색 정확도를 높이기 위해 Query를 최적화한다.

예시

사용자 질문

```
쿼리 빨라지는 방법 알려줘
```

최적화 Query

```
StarRocks Query Performance Optimization
```

가능한 경우

- 제품명
- 기능명
- 기술 용어

등을 명확하게 만든다.

---

## 6.3 Summary Retriever

Summary Collection을 검색한다.

목적은

"어떤 Wiki가 관련 있는가"

를 찾는 것이다.

검색 대상

```
wiki_summary
```

검색 결과

```
Wiki A

Wiki B

Wiki C
```

Summary는

- title
- summary
- keywords
- parent_id

정보를 가진다.

Assistant는 Top K Summary를 선택한다.

---

## 6.4 Chunk Retriever

Summary 검색 결과를 기반으로 Chunk를 검색한다.

검색 대상

```
wiki_chunk
```

검색 조건

```
parent_id IN
(
Wiki A,
Wiki B,
Wiki C
)
```

검색 결과

```
Chunk 1

Chunk 2

Chunk 3

...
```

Chunk에는 다음 정보가 저장된다.

- chunk_id
- parent_id
- heading
- section_path
- content
- embedding

---

## 6.5 Chunk Reranker

Vector Similarity만으로는 정확도가 부족할 수 있다.

검색된 Chunk를 다시 정렬한다.

입력

- Question
- Retrieved Chunk

출력

Top N Chunk

평가 요소

- Semantic Similarity
- Heading Match
- Keyword Match
- Metadata Match

향후에는 Cross Encoder 기반 Reranker를 적용할 수 있다.

---

## 6.6 Context Builder

Rerank된 Chunk만 Context로 구성한다.

예시

```
## Cost Based Optimizer

...

## Query Cache

...

## Runtime Filter

...
```

문서 전체를 사용하는 것이 아니라

질문과 관련된 Chunk만 선택하여 Context를 생성한다.

이를 통해

- Token 사용량 감소
- Hallucination 감소
- Retrieval Precision 향상을 기대할 수 있다.

---

## 6.7 Answer Generator

최종적으로 LLM이 답변을 생성한다.

입력

- System Prompt
- User Question
- Retrieved Context

출력

- Answer

LLM은 반드시 Context에 포함된 정보만 근거로 답변한다.

Context에 없는 내용은 추측하지 않는다.

---

# 7. Retrieval Architecture

Assistant는 Hierarchical Retrieval 방식을 사용한다.

```
Question

↓

Summary Retrieval

↓

Top Wiki

↓

Chunk Retrieval

↓

Top Chunk

↓

Rerank

↓

Context

↓

Answer
```

이 방식은 전체 Chunk Collection을 검색하는 방식보다 검색 범위를 크게 줄일 수 있다.

또한 관련성이 높은 Wiki 내부에서만 Chunk를 검색하므로 정확도를 향상시킬 수 있다.

---

# 8. Summary Retrieval

Summary Collection은 문서 단위 검색을 수행한다.

Collection

```
wiki_summary
```

검색 결과

```
Top 5 Wiki
```

예시

| Score | Wiki |
|--------|------|
|0.93|Query Optimization|
|0.91|CBO|
|0.88|Runtime Filter|

Summary Retrieval의 목적은

관련 Wiki를 빠르게 선택하는 것이다.

Summary는 답변 Context로 사용하지 않는다.

---

# 9. Chunk Retrieval

Summary Retrieval 결과를 이용하여 Chunk를 검색한다.

검색 범위는

```
parent_id
```

가 일치하는 Wiki 내부로 제한된다.

예시

```
Summary

Wiki A

Wiki B
```

↓

```
Chunk Search

Wiki A

Wiki B
```

↓

```
Top 10 Chunk
```

이 방식은 전체 Collection 검색보다 효율적이다.

# 10. Vector Collection

Assistant는 Builder가 생성한 두 개의 Vector Collection을 사용한다.

## 10.1 wiki_summary

문서 단위 검색을 위한 Collection이다.

검색 범위를 줄이는 것이 목적이다.

### 저장 데이터

| Field | Description |
|--------|-------------|
| parent_id | Wiki ID |
| title | Wiki 제목 |
| summary | Wiki 요약 |
| keywords | 주요 키워드 |
| tags | 문서 태그 |
| embedding | Summary Embedding |

---

### 특징

- 문서 하나당 하나의 Vector
- 빠른 Retrieval
- 검색 범위 축소
- Chunk 검색 대상 결정

---

## 10.2 wiki_chunk

실제 답변 생성을 위한 Collection이다.

### 저장 데이터

| Field | Description |
|--------|-------------|
| chunk_id | Chunk ID |
| parent_id | Wiki ID |
| heading | Section 제목 |
| section_path | Heading Path |
| content | Chunk 내용 |
| keywords | Chunk Keyword |
| embedding | Chunk Embedding |

---

### 특징

- 하나의 Wiki는 여러 개의 Chunk를 가진다.
- 실제 Context는 Chunk에서 생성된다.
- Summary는 Context에 포함되지 않는다.

---

# 11. Retrieval 상세 Flow

Assistant는 다음 순서로 검색을 수행한다.

```
User Question

↓

Embedding

↓

Summary Search

↓

Top K Wiki

↓

Chunk Search

↓

Top N Chunk

↓

Rerank

↓

Top M Chunk

↓

Context

↓

LLM
```

---

## Step 1

Question Embedding

질문을 Embedding Model로 변환한다.

Embedding은 Retrieval 과정 동안 재사용한다.

---

## Step 2

Summary Search

wiki_summary Collection을 검색한다.

목적

관련 Wiki를 선택한다.

출력

```
Top 5 Wiki
```

---

## Step 3

Chunk Search

Summary Retrieval 결과의 parent_id를 사용하여

wiki_chunk Collection을 검색한다.

검색 조건

```
parent_id IN (...)

```

출력

```
Top 20 Chunk
```

---

## Step 4

Chunk Rerank

검색된 Chunk를 다시 정렬한다.

평가 기준

- Semantic Similarity
- Heading Match
- Keyword Match
- Metadata Match

출력

```
Top 5 Chunk
```

---

## Step 5

Context 생성

Top Chunk를 순서대로 연결한다.

예시

```
## Cost Based Optimizer

...

## Runtime Filter

...

## Query Cache

...
```

Chunk 간에는 구분자를 추가하여 LLM이 문맥을 이해하기 쉽게 한다.

---

## Step 6

Answer Generation

LLM은

- System Prompt
- User Question
- Context

를 입력받아 답변을 생성한다.

답변은 반드시 Context를 근거로 생성해야 한다.

---

# 12. API

## POST /assistant/v1/chat

Request

```json
{
  "space_id": "space001",
  "question": "Query Cache가 무엇인가요?",
  "history": []
}
```

---

Response

```json
{
  "answer": "...",
  "sources":[
    {
      "parent_id":"wiki001",
      "heading":"Query Cache"
    }
  ]
}
```

---

# 13. LangGraph State

AssistantState는 Workflow 전체에서 공유된다.

```python
question

optimized_query

embedding

summary_hits

chunk_hits

reranked_chunks

context

answer

sources

history
```

---

## State 설명

question

사용자의 원본 질문

---

optimized_query

검색에 사용할 Query

---

summary_hits

Summary 검색 결과

---

chunk_hits

Chunk 검색 결과

---

reranked_chunks

Rerank 이후 Chunk

---

context

LLM 입력 Context

---

answer

최종 답변

---

sources

답변 출처

---

history

대화 이력

---

# 14. Prompt

## Retrieval Prompt

Question Analyzer는 검색 정확도를 높이는 Query를 생성한다.

예시

입력

```
쿼리 빨라지는 방법 알려줘
```

출력

```
StarRocks Query Performance Optimization
```

---

## Answer Prompt

System Prompt

```
You are Assistant Agent.

Answer only using the retrieved Wiki Context.

Do not invent information.

If the answer is not contained in the Context, clearly state that the information could not be found.
```

---

# 15. Configuration

| Parameter | Description |
|------------|-------------|
| TOP_K_SUMMARY | Summary 검색 개수 |
| TOP_K_CHUNK | Chunk 검색 개수 |
| TOP_K_RERANK | Rerank 결과 개수 |
| EMBEDDING_MODEL | Embedding 모델 |
| CHAT_MODEL | Chat Model |
| VECTOR_COLLECTION_SUMMARY | wiki_summary |
| VECTOR_COLLECTION_CHUNK | wiki_chunk |

---

# 16. Sequence Diagram

```
User

│

Question

│

Assistant

│

Embedding

│

Summary Search

│

Vector DB

│

Top Wiki

│

Chunk Search

│

Top Chunk

│

Chunk Rerank

│

Context Builder

│

LLM

│

Answer

│

User
```

---

# 17. Error Handling

| 상황 | 처리 |
|--------|------|
| Summary 검색 실패 | 검색 결과 없음 반환 |
| Chunk 검색 실패 | Context 생성 중단 |
| Vector DB 장애 | 오류 반환 |
| LLM 장애 | 재시도 후 실패 반환 |
| Context 없음 | 관련 Wiki를 찾을 수 없음을 안내 |

---

# 18. 향후 개선 사항

## Hybrid Retrieval

Vector Search와 Keyword Search를 함께 수행한다.

---

## Metadata Filtering

다음 조건으로 Retrieval 범위를 제한한다.

- Space
- Tag
- Product
- Version
- Category

---

## Cross Encoder Reranker

Vector Similarity 대신 Cross Encoder를 사용하여 정확도를 향상시킨다.

---

## Query Expansion

동의어 및 관련 용어를 확장하여 검색 Recall을 향상시킨다.

---

## Multi Query Retrieval

하나의 질문을 여러 개의 검색 Query로 분리하여 Retrieval을 수행한다.

---

## Confidence Evaluation

답변 생성 후 Confidence를 계산하여 일정 기준 이하인 경우

사용자에게

"관련 Wiki에서 충분한 근거를 찾지 못했습니다."

를 반환하도록 개선한다.

---

# 19. 설계 원칙

Assistant는 다음 원칙을 따른다.

1. Summary는 검색 범위를 줄이기 위한 용도로만 사용한다.

2. Chunk만 Context로 사용한다.

3. 문서 전체를 LLM에 전달하지 않는다.

4. Retrieval과 Generation을 분리한다.

5. Context 기반으로만 답변한다.

6. Builder는 Index를 생성하고 Assistant는 Index를 조회한다.

7. Retrieval 정확도를 우선하며, 필요한 경우 Rerank를 수행한다.

8. 모든 답변은 Wiki를 근거로 생성한다.