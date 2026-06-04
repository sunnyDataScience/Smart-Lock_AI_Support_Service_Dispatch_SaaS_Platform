"""LLM provider abstraction module.

[lock-cs-agent] 供應商層已瘦身為單一 LiteLLMProvider(多供應商,靠 model 字串路由)。
nanobot 原本的各家 provider 實作(anthropic/openai_compat/azure/bedrock/github_copilot/
openai_codex)已移除。
"""

from __future__ import annotations

from lockcore.providers.base import LLMProvider, LLMResponse
from lockcore.providers.litellm_provider import LiteLLMProvider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LiteLLMProvider",
]
