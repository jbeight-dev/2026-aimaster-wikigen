import json
import time

from openai import AzureOpenAI

from .. import config, observability

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


def _chat(tag: str, **kwargs):
    """OpenAI Chat Completions 호출을 감싸 응답시간/토큰 사용량을 기록한다 (PRD 25장)."""
    start = time.perf_counter()
    response = _client.chat.completions.create(**kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    usage = None
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    observability.record_llm_call(tag, elapsed_ms, usage)
    return response


def _embed(tag: str, **kwargs):
    start = time.perf_counter()
    response = _client.embeddings.create(**kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    usage = None
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    observability.record_llm_call(tag, elapsed_ms, usage)
    return response


def embed_text(text: str) -> list[float]:
    response = _embed("embed_text", model=config.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def generate_answer(
    context: str, question: str, history: list[dict], conversation_summary: str = ""
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_summary:
        messages.append(
            {
                "role": "system",
                "content": f"이전 대화 요약:\n{conversation_summary}",
            }
        )
    for turn in history:
        role = "assistant" if turn["role"] == "assistant" else "user"
        messages.append({"role": role, "content": turn["text"]})
    messages.append(
        {
            "role": "user",
            "content": f"컨텍스트:\n{context}\n\n질문: {question}",
        }
    )

    response = _chat("generate_answer", model=config.CHAT_MODEL, messages=messages)
    return response.choices[0].message.content


def analyze_question(question: str, history: list[dict]) -> str:
    """Question Analyzer: 멀티턴 대화 맥락을 반영해 독립적인 검색 질문으로 재구성한다."""
    transcript = "\n".join(
        f"{'assistant' if turn['role'] == 'assistant' else 'user'}: {turn['text']}"
        for turn in history[-6:]
    )
    prompt = (
        "너는 대화형 검색 질의 분석기다. 아래 대화 이력을 참고해 사용자의 마지막 질문을 "
        "이전 맥락 없이도 이해할 수 있는 독립적인 검색 질문으로 바꿔라.\n\n"
        "규칙:\n"
        "1. 지시어(이거/그거/저거 등)나 생략된 주어·목적어를 대화 이력에서 찾아 명시한다.\n"
        "2. 질문의 핵심 의도와 범위는 바꾸지 않는다.\n"
        "3. 대화 이력에 없는 내용을 임의로 추가하지 않는다.\n"
        "4. 불필요한 인사말이나 수식어는 제거한다.\n"
        "5. 결과는 검색에 적합한 간결한 한 문장으로 작성한다.\n\n"
        f"대화 이력:\n{transcript}\n\n마지막 질문: {question}\n\n"
        "독립적인 검색 질문만 출력하라. 설명이나 따옴표를 추가하지 마라."
    )

    response = _chat(
        "analyze_question", model=config.CHAT_MODEL, messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def optimize_query(question: str) -> str:
    """Query Optimizer: 제품명/기능명/기술 용어를 명확히 해 검색 정확도를 높인다."""
    prompt = (
        "너는 위키 검색 질의 최적화기다. 아래 질문을 검색 정확도가 높은 질의로 다듬어라.\n\n"
        "규칙:\n"
        "1. 제품명, 기능명, 기술 용어가 모호하면 문서에서 흔히 쓰이는 정식 명칭으로 명확히 한다.\n"
        "2. 질문에 없는 제품/기능/조건을 임의로 추가하지 않는다.\n"
        "3. 인사말, 존댓말, 불필요한 수식어는 제거한다.\n"
        "4. 테이블명, 컬럼명, SQL, API명, 오류 메시지, 식별자는 원문 그대로 유지한다.\n"
        "5. 결과는 검색에 적합한 간결한 한 문장으로 작성한다.\n\n"
        f"질문: {question}\n\n"
        "최적화된 검색어만 출력하라. 설명이나 따옴표를 추가하지 마라."
    )

    response = _chat(
        "optimize_query", model=config.CHAT_MODEL, messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def summarize_history(history: list[dict]) -> str:
    """오래된 대화 턴들을 답변 생성에 참고할 핵심 요약으로 압축한다."""
    if not history:
        return ""

    transcript = "\n".join(
        f"{'assistant' if turn['role'] == 'assistant' else 'user'}: {turn['text']}"
        for turn in history
    )
    prompt = (
        "너는 대화 요약기다. 아래는 사용자와 어시스턴트 사이의 이전 대화 기록이다. "
        "이후 답변 생성에 참고할 수 있도록 핵심 주제, 사용자의 의도, 이미 확인된 정보를 "
        "중심으로 간결하게 요약하라. 불필요한 인사말이나 잡담은 생략한다.\n\n"
        f"대화 기록:\n{transcript}\n\n요약:"
    )

    response = _chat(
        "summarize_history", model=config.CHAT_MODEL, messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


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
    response = _chat(
        "evaluate_context",
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

    response = _chat(
        "rewrite_query", model=config.CHAT_MODEL, messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
