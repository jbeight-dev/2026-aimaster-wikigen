import json

from openai import AzureOpenAI

from .. import config

_client = AzureOpenAI(
    azure_endpoint=config.OPENAI_BASE_URL,
    api_key=config.OPENAI_API_KEY or "unset",
    api_version=config.OPENAI_API_VERSION,
)

SYSTEM_PROMPT = (
    "너는 사내 위키 문서를 근거로 답하는 어시스턴트다. "
    "아래에 주어진 컨텍스트에 있는 내용만 근거로 답하고, "
    "컨텍스트에 없는 내용은 추측하지 말고 모른다고 답해라."
)


def embed_text(text: str) -> list[float]:
    response = _client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def generate_answer(context: str, question: str, history: list[dict]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        role = "assistant" if turn["role"] == "assistant" else "user"
        messages.append({"role": role, "content": turn["text"]})
    messages.append(
        {
            "role": "user",
            "content": f"컨텍스트:\n{context}\n\n질문: {question}",
        }
    )

    response = _client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


def evaluate_context(question: str, context: str) -> dict:
    """RAGAS 스타일 reference-free 평가: LLM이 검색 컨텍스트 품질을 심사한다."""
    prompt = (
        "너는 검색 품질 평가자다. 아래 질문과 검색된 컨텍스트를 보고 "
        "두 지표를 0.0~1.0 사이 값으로 평가해 JSON으로만 답하라.\n"
        "- context_precision: 컨텍스트 중 질문과 실제 관련 있는 내용의 비율\n"
        "- context_recall: 질문에 답하기 위해 필요한 정보가 컨텍스트에 충분히 포함된 정도\n\n"
        f"질문: {question}\n\n컨텍스트:\n{context}\n\n"
        '형식: {"context_precision": 0.0, "context_recall": 0.0}'
    )
    response = _client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return {
        "context_precision": max(0.0, min(1.0, float(data.get("context_precision", 0.0)))),
        "context_recall": max(0.0, min(1.0, float(data.get("context_recall", 0.0)))),
    }


def rewrite_query(original_question: str, previous_query: str) -> str:
    prompt = (
        "너는 위키 검색을 위한 검색어 재작성기다. "
        "이전 검색에서 관련 문서를 충분히 찾지 못했으므로 새로운 검색어를 생성해야 한다.\n\n"
        "다음 규칙을 따른다.\n"
        "1. 원본 질문의 핵심 의도와 검색 범위를 유지한다.\n"
        "2. 직전 검색어를 그대로 반복하지 않는다.\n"
        "3. 핵심 용어의 동의어, 유사 표현, 일반적으로 사용되는 기술 용어를 활용한다.\n"
        "4. 원본 질문이나 대화 맥락에 없는 제품명, 기술, 기능, 조건을 임의로 추가하지 않는다.\n"
        "5. 모호한 표현은 주어진 정보로 확인할 수 있는 경우에만 구체화한다.\n"
        "6. 질문에 포함된 테이블명, 컬럼명, SQL, API명, 오류 메시지, 식별자는 가능한 한 유지한다.\n"
        "7. 위키 검색에 적합한 간결한 검색어 한 문장으로 작성한다.\n"
        "8. 질문이 위키 도메인과 무관하면 원본 질문을 그대로 반환한다.\n\n"
        f"원본 질문: {original_question}\n"
        f"직전 검색어: {previous_query}\n\n"
        "재작성된 검색어만 출력하라. 설명이나 따옴표를 추가하지 마라."
    )

    response = _client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
