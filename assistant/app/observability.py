"""PRD_v4_part3 25장(Logging) 구현: LangGraph Workflow 전체를 구조화 로그로 기록한다.

- record_llm_call(): llm.py의 각 OpenAI 호출이 응답시간/토큰 사용량을 요청 단위로 누적한다
  (contextvars 기반이라 동시 요청 간 값이 섞이지 않는다).
- log_event(): Debug/Monitoring/Retrieval 개선에 쓰이는 구조화(JSON) 로그 한 줄을 남긴다.
"""

import contextvars
import json
import logging
import uuid

events_logger = logging.getLogger("assistant.events")

_metrics_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "assistant_metrics", default=None
)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level.upper(),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    else:
        root.setLevel(level.upper())


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def start_request_metrics() -> dict:
    metrics = {
        "llm_calls": [],
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "llm_time_ms": 0.0,
    }
    _metrics_var.set(metrics)
    return metrics


def record_llm_call(tag: str, elapsed_ms: float, usage: dict | None) -> None:
    metrics = _metrics_var.get()
    if metrics is None:
        return
    metrics["llm_calls"].append(
        {"tag": tag, "elapsed_ms": round(elapsed_ms, 1), **(usage or {})}
    )
    metrics["llm_time_ms"] += elapsed_ms
    if usage:
        metrics["prompt_tokens"] += usage.get("prompt_tokens", 0)
        metrics["completion_tokens"] += usage.get("completion_tokens", 0)
        metrics["total_tokens"] += usage.get("total_tokens", 0)


def get_request_metrics() -> dict:
    return _metrics_var.get() or {}


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    events_logger.log(
        level, json.dumps({"event": event, **fields}, ensure_ascii=False, default=str)
    )
