"""LLM 呼叫度量輔助模組（取代 Opik 的 token + latency 紀錄角色）。

提供：
- extract_usage(message): 從 LangChain AIMessage 抽取 usage_metadata
- extract_usage_from_messages(messages): 掃 ainvoke 結果中所有 AIMessage 的 usage
- log_llm_call_async(...): 包裝 asyncio.create_task 呼叫 storage.log_llm_call，
  確保任何錯誤都被吞掉、不影響呼叫端關鍵路徑

呼叫端責任：
- 計時用 time.monotonic() 自行包在 ainvoke 前後
- 失敗時手動傳 success=False, error_type=type(e).__name__
"""
from __future__ import annotations

import asyncio
from typing import Any, Iterable

from core.logging_config import get_logger
import psycopg

log = get_logger(__name__)

# 模組層級 storage 單例，由 app.py 啟動時注入；harness 各模組共用
_storage = None


def set_storage(storage) -> None:
    """由 app.py 啟動時呼叫，注入 audit_storage 實例供所有 harness 模組共用。"""
    global _storage
    _storage = storage


def get_storage():
    return _storage


def extract_usage(message: Any) -> dict | None:
    """從單一 LangChain message 取出 usage_metadata。

    AIMessage.usage_metadata 形如：
        {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168}

    某些 LiteLLM provider 可能不會帶 usage_metadata，回傳 None；
    若部分欄位缺失則保留 None（呼叫端用 .get() 容錯）。
    """
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return None


def extract_usage_from_messages(messages: Iterable[Any]) -> list[dict]:
    """掃 ainvoke 結果的 messages，取出所有 AIMessage 的 usage（含 step_index）。

    回傳 list[dict]，每筆含：
        {"step_index": int, "usage": dict | None, "message": <ref>}
    """
    out: list[dict] = []
    step_index = 0
    for msg in messages or []:
        msg_type = getattr(msg, "type", None)
        if msg_type == "ai":
            out.append({
                "step_index": step_index,
                "usage": extract_usage(msg),
                "message": msg,
            })
            step_index += 1
    return out


def log_simple(
    user_id: str,
    call_site: str,
    model: str,
    response: Any = None,
    latency_ms: int | None = None,
    success: bool = True,
    error_type: str | None = None,
    metadata: dict | None = None,
    turn_id: str | None = None,
    user_question: str | None = None,
    ai_reply: str | None = None,
) -> None:
    """便利包裝：從 response 抽 usage，背景寫入 llm_usage_log。

    user_question / ai_reply 由呼叫端傳入；若 ai_reply 為 None 但 response 有 .content
    且 success=True，會自動取 response.content 當 ai_reply（避免每個呼叫端都要重複拿）。

    呼叫端只需：
        t0 = time.monotonic()
        try:
            resp = await llm.ainvoke([...])
            log_simple(user_id, "memory_compression", model, resp,
                       int((time.monotonic()-t0)*1000),
                       user_question=dialogue_text)
        except (psycopg.Error, OSError, RuntimeError) as e:
            log_simple(user_id, "memory_compression", model,
                       latency_ms=int((time.monotonic()-t0)*1000),
                       success=False, error_type=type(e).__name__,
                       user_question=dialogue_text)
            raise
    """
    storage = _storage
    if storage is None:
        return
    usage = extract_usage(response) if response is not None else {}
    usage = usage or {}
    # 若呼叫端沒傳 ai_reply 但 response 有內容，自動帶入
    if ai_reply is None and response is not None and success:
        content = getattr(response, "content", None)
        if isinstance(content, str):
            ai_reply = content
        elif isinstance(content, list):
            ai_reply = "".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            ) or None
    schedule_log(
        storage,
        user_id=user_id,
        call_site=call_site,
        model=model,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        turn_id=turn_id,
        user_question=user_question,
        ai_reply=ai_reply,
        metadata=metadata,
    )


def schedule_log(storage, **kwargs) -> None:
    """背景 asyncio.create_task 寫入 llm_usage_log；任何錯誤吞掉不傳出。

    storage: PostgresAuditStorage 或 SqliteAuditStorage 實例（None 則直接略過）
    kwargs: log_llm_call() 接受的所有參數
    """
    if storage is None:
        return

    async def _runner():
        try:
            await storage.log_llm_call(**kwargs)
        except (psycopg.Error, OSError, RuntimeError) as e:
            log.warning("llm_metrics_log_failed", error=str(e), exc_info=True)

    try:
        asyncio.create_task(_runner())
    except RuntimeError:
        # 沒有 running loop（例如 sync 上下文）— 改用同步 fire-and-forget
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_runner())
        except (psycopg.Error, OSError, RuntimeError) as e:
            log.warning("llm_metrics_schedule_failed", error=str(e), exc_info=True)
