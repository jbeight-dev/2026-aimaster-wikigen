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
        "아래 사용자 질문으로 사내 위키를 검색했지만 관련 문서를 충분히 찾지 못했다. "
        "검색이 더 잘 되도록 질문을 더 구체적인 검색어 한 문장으로 재작성하라. "
        "모호한 표현은 구체화하고, 플랫폼/도메인 용어가 있다면 명확히 하라. "
        "질문이 위키 도메인과 무관하면(잡담, 날씨 등) 원문을 그대로 반환하라.\n\n"
        f"원본 질문: {original_question}\n"
        f"직전 검색어: {previous_query}\n\n"
        "재작성된 검색어만 출력하라(따옴표나 설명 없이)."
    )
    response = _client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
