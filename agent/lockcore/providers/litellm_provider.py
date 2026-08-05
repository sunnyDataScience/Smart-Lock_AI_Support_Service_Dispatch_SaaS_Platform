"""統一的 LLM 供應商層 — 以 LiteLLM 支援多家供應商(Anthropic/OpenAI/Azure/Bedrock…)。

[lock-cs-agent] 取代 nanobot 的各家 provider 實作:只要一個 adapter,靠 model 字串路由
(litellm 慣例:`claude-3-5-sonnet-...`、`gpt-4o`、`bedrock/...`、`azure/...`、`openrouter/...`)。
只需實作 base 的 `chat` 與 `get_default_model`;串流由 base.chat_stream 預設 fallback 處理。
"""

from __future__ import annotations

import json
import os
from typing import Any

import litellm
from loguru import logger

from lockcore.providers.base import LLMProvider, LLMResponse, ToolCallRequest

# CR-0156/ADR-007:OPIK LLM 追蹤只掛一次(process 級 litellm callback)
_OPIK_WIRED = False


def _maybe_enable_opik() -> None:
    """OPIK_API_KEY 設定時掛 OPIK LLM call 追蹤(CR-0156/ADR-007);未設=零行為變化。

    接法採 litellm 字串 callback(`litellm.callbacks += ["opik"]`)——OPIK 官方
    litellm 整合文件列的常見用法之一(另一種是實例化 OpikLogger 塞進 callbacks;
    此處選字串法,由 litellm 內建 OpikLogger 讀 OPIK_API_KEY / OPIK_* env 上報,
    不確定 opik SDK 版本細節時最穩)。opik 套件缺=安靜略過 + WARNING;
    任何失敗=降級略過,絕不癱瘓 LLM 供應商層。
    """
    global _OPIK_WIRED
    if _OPIK_WIRED:
        return
    _OPIK_WIRED = True
    if not os.environ.get("OPIK_API_KEY", "").strip():
        return  # opt-in:未設=零行為變化
    try:
        import opik  # noqa: F401 — ADR-007:agent 接 OPIK SDK;確認套件在才掛 callback
    except ImportError:
        logger.warning(
            "observability: OPIK_API_KEY 已設但 opik 套件未安裝"
            "(pip install '.[otel]')→ 略過 LLM 追蹤"
        )
        return
    try:
        existing = list(litellm.callbacks or [])
        if "opik" not in existing:
            litellm.callbacks = existing + ["opik"]  # 不可變式:建新 list 再賦值
        logger.info("observability: OPIK LLM 追蹤已啟用(litellm callback)")
    except Exception:  # noqa: BLE001 — 可觀測性失敗不可癱瘓 LLM 呼叫
        logger.exception("observability: OPIK 掛載失敗 → 降級略過")


class LiteLLMProvider(LLMProvider):
    """以 litellm 為後端的多供應商 provider。"""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "claude-sonnet-4-5",
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
    ):
        super().__init__(api_key=api_key, api_base=api_base)
        self._default_model = default_model
        self._extra_headers = extra_headers
        self._extra_body = extra_body or {}
        _maybe_enable_opik()  # CR-0156/ADR-007:opt-in,未設 OPIK_API_KEY=零行為變化

    def get_default_model(self) -> str:
        return self._default_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        model = model or self._default_model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        kwargs.update(self._extra_body)

        try:
            resp = await litellm.acompletion(**kwargs)
        except Exception as e:  # noqa: BLE001 — 映射成可被 retry policy 判讀的 error 回應
            return self._error_response(e)
        return self._to_llm_response(resp)

    # ── 錯誤映射 ────────────────────────────────────────────────────────
    #
    # ⚠️ 這裡填的欄位直接決定 base._is_transient_response 要不要重試。
    #    原本無論什麼例外都寫死 error_kind="connection",而 "connection" 落在
    #    base._TRANSIENT_ERROR_KINDS 裡 → **每一種錯誤都被判成暫時性、一律重試**:
    #      · 401/403 認證或帳務封鎖 → 重試到死(絕無可能成功)
    #      · 429 配額耗盡        → 重試(base 本來備了 _NON_RETRYABLE_429_ERROR_TOKENS
    #                              要擋這種,但沒有 status_code/code 就走不到那條分支)
    #      · 400 參數錯誤        → 重試
    #    症狀是「LLM 一有問題,客人就要等完整個重試預算才收到罐頭回覆」。
    #
    #    修法是把 litellm 例外本身帶的結構化欄位取出來填好,讓 base 的既有判定
    #    邏輯真的能用上——base 那套分級本來就寫對了,只是拿不到資料。

    # 真正屬於「重試有機會成功」的例外類名片段(litellm 例外多沿用 openai 命名)
    _CONNECTION_ERROR_HINTS = ("timeout", "connection", "apiconnection", "internalserver")

    @classmethod
    def _error_response(cls, exc: Exception) -> LLMResponse:
        """把 litellm 例外映射成帶結構化 metadata 的 error LLMResponse。

        litellm 的例外沿用 openai SDK 的形狀,常見帶 status_code / code / type;
        缺哪個就留 None,由 base 自行往下一層(kind → 文字 marker)判定。
        """
        status = cls._coerce_status(getattr(exc, "status_code", None))
        code = cls._coerce_token(getattr(exc, "code", None))
        # openai 系例外的 .type 常是 "insufficient_quota" 這類語意 token,
        # 比類名精確;沒有才退回類名(維持原行為,不讓既有文字判定失效)。
        etype = cls._coerce_token(getattr(exc, "type", None)) or type(exc).__name__

        name = type(exc).__name__.lower()
        is_conn = any(h in name for h in cls._CONNECTION_ERROR_HINTS)

        return LLMResponse(
            content=f"[litellm error] {exc}",
            finish_reason="error",
            # 只有真的是連線/逾時類才給 "connection";其餘留 None,避免把
            # 認證/配額/參數錯誤一併灌成暫時性錯誤。
            error_kind="connection" if is_conn else None,
            error_type=etype,
            error_status_code=status,
            error_code=code,
        )

    @staticmethod
    def _coerce_status(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_token(value: Any) -> str | None:
        if value is None:
            return None
        token = str(value).strip()
        return token or None

    @staticmethod
    def _to_llm_response(resp: Any) -> LLMResponse:
        choice = resp.choices[0]
        msg = choice.message
        tool_calls: list[ToolCallRequest] = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCallRequest(id=tc.id, name=tc.function.name, arguments=args))

        usage: dict[str, int] = {}
        u = getattr(resp, "usage", None)
        if u is not None:
            usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                "total_tokens": getattr(u, "total_tokens", 0) or 0,
            }

        return LLMResponse(
            content=getattr(msg, "content", None),
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=getattr(msg, "reasoning_content", None),
        )
