# Part 3. Advanced Design

---

# 20. Question Analysis

## 목적

사용자의 질문을 검색에 적합한 형태로 변환하여 Retrieval 정확도를 높인다.

Question Analyzer는 LLM을 사용하여 질문을 분석하고 검색에 필요한 정보를 추출한다.

---

## 입력

- User Question
- Conversation History

---

## 출력

| 항목 | 설명 |
|------|------|
| original_question | 원본 질문 |
| optimized_query | 검색 Query |
| intent | 질문 의도 |
| entities | 제품명, 기능명 |
| keywords | 검색 키워드 |

---

## 예시

사용자 질문

```
쿼리 빨라지게 하는 기능 뭐 있어?
```

↓

분석 결과

```json
{
  "intent":"feature_search",
  "optimized_query":"StarRocks Query Performance Optimization",
  "entities":[
      "StarRocks"
  ],
  "keywords":[
      "Query",
      "Optimization",
      "Performance"
  ]
}
```

---

# 21. Conversation Memory

Assistant는 Multi-turn 대화를 지원한다.

Conversation History는 검색 이전에 Question Analyzer로 전달된다.

예시

```
User

CBO가 뭐야?

↓

Assistant

...

↓

User

설정 방법은?

```

Question Analyzer는

```
설정 방법은?
```

을

```
Cost Based Optimizer 설정 방법
```

으로 재작성한다.

---

최근 대화는 그대로 전달하고

오래된 대화는 Summary 형태로 압축하여 사용한다.

---

# 22. Source Citation

모든 답변에는 출처를 포함한다.

예시

```
Cost Based Optimizer는 ...

출처

StarRocks Query Optimization

> Cost Based Optimizer
```

Source에는 다음 정보를 포함한다.

- Wiki 제목

- Heading

- Section Path

---

# 23. Confidence Evaluation

Assistant는 Retrieval 결과의 신뢰도를 평가한다.

평가 대상

- Summary Score

- Chunk Similarity

- Rerank Score

- Retrieval Count

필요 시 LLM 기반 Context Validation을 수행한다.

---

Confidence가 일정 기준 이하인 경우

다음과 같이 응답한다.

```
관련 Wiki에서 충분한 근거를 찾지 못했습니다.
```

---

향후에는

RAGAS 기반 평가를 적용할 수 있다.

---

# 24. Streaming Response

답변 생성은 Streaming 방식으로 수행한다.

```
Question

↓

Retrieval

↓

LLM

↓

Streaming

↓

User
```

장점

- 빠른 응답 체감

- 긴 답변 처리

- 사용자 경험 향상

Streaming은 SSE(Server Sent Events)를 사용한다.

---

# 25. Logging

Assistant는 LangGraph Workflow 전체를 기록한다.

기록 대상

- User Question

- Optimized Query

- Summary Retrieval

- Chunk Retrieval

- Rerank Result

- Context Length

- LLM Response Time

- Token Usage

- Confidence Score

---

로그는

- Debug

- Monitoring

- Retrieval 개선

목적으로 활용한다.

---

# 26. Monitoring

다음 KPI를 수집한다.

| KPI | 설명 |
|------|------|
| Retrieval Time | 검색 시간 |
| LLM Time | 답변 생성 시간 |
| Total Response Time | 전체 응답 시간 |
| Retrieval Hit Rate | 검색 성공률 |
| Average Chunk Count | 평균 Chunk 수 |
| Average Context Size | 평균 Context 길이 |
| Confidence Score | 평균 신뢰도 |
| User Feedback | 사용자 평가 |

---

# 27. Security

Assistant는 승인된 Wiki만 검색한다.
검색 시 다음 조건을 적용한다.

- Space Filter
- Approval Status


---

# 28. 향후 확장

## Hybrid Search

BM25와 Vector Search를 함께 사용한다.

---

## Metadata Search

다음 조건을 검색에 활용한다.

- Product

- Version

- Tag

- Category

- Author

---

## Query Expansion

질문을 동의어 기반으로 확장한다.

예시

```
CBO

↓

Cost Based Optimizer

↓

Optimizer
```

---

## Cross Encoder Reranker

Vector Similarity 이후

Cross Encoder를 적용하여 정확도를 높인다.

---

## Agent Workflow

향후에는 단일 Retrieval 대신

Multi-Agent 구조를 적용할 수 있다.

예시

```
Question

↓

Intent Agent

↓

Retrieval Agent

↓

Validation Agent

↓

Answer Agent
```

---

# 29. 설계 원칙

Assistant는 다음 원칙을 따른다.

1. 승인된 Wiki만 검색한다.

2. Summary는 검색 범위를 줄이는 용도로만 사용한다.

3. Chunk만 Context에 포함한다.

4. Retrieval과 Generation을 분리한다.

5. 검색 결과를 그대로 신뢰하지 않고 Rerank를 수행한다.

6. 답변은 반드시 Context를 근거로 생성한다.

7. 출처를 항상 함께 제공한다.

8. 장기적으로 Hybrid Retrieval 구조를 지향한다.

9. Builder와 Assistant는 명확하게 역할을 분리한다.

10. Retrieval 품질을 지속적으로 측정하고 개선한다.