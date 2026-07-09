"""LLM 介面 — 統一走 LiteLLM（見 provider.py）。

2026-07-09 重構：移除 per-provider registry 與 langchain 適配器，
與 agent 的 LiteLLMProvider 同哲學（model 字串路由多家）。
公開介面不變：get_llm / get_vision_llm。
"""

from llms.provider import get_llm, get_vision_llm, resolve_model

__all__ = ["get_llm", "get_vision_llm", "resolve_model"]
