"""audit ADR-009：build_provider 的多供應商 failover 接線。

補洞前 LINE live path（app_config.build_provider）只建單一 LiteLLMProvider，
FallbackProvider 只在上游 factory.make_provider 有接。此測試鎖定：
  - fallback_models 空 → 回單一 LiteLLMProvider（行為不變）
  - fallback_models 非空 → 包進 FallbackProvider（failover 生效）
純建構、不打網路。
"""

from __future__ import annotations

from lockcore.app_config import AppConfig, build_provider
from lockcore.providers.fallback_provider import FallbackProvider
from lockcore.providers.litellm_provider import LiteLLMProvider


def _cfg(**kw) -> AppConfig:
    base = dict(
        model="gemini/gemini-2.5-flash",
        temperature=0.7,
        max_tokens=4096,
        vertex_project=None,
        vertex_location=None,
        credentials_path=None,
        tenant="t",
        backend="sqlite",
        db_path=":memory:",
        postgres_uri_env="POSTGRES_URI",
        extractor="raw",
    )
    base.update(kw)
    return AppConfig(**base)


def test_build_provider_plain_without_fallback():
    p = build_provider(_cfg(fallback_models=()))
    assert isinstance(p, LiteLLMProvider)
    assert not isinstance(p, FallbackProvider)


def test_build_provider_wraps_fallback_when_configured():
    p = build_provider(_cfg(fallback_models=("gemini/gemini-2.5-flash-lite",)))
    assert isinstance(p, FallbackProvider)
    # 主 provider 仍是 LiteLLMProvider，且 default_model 對齊主模型
    assert p.get_default_model() == "gemini/gemini-2.5-flash"


def test_build_provider_multiple_fallbacks_preserved():
    p = build_provider(
        _cfg(fallback_models=("gemini/gemini-2.5-flash-lite", "ollama_chat/gemma3"))
    )
    assert isinstance(p, FallbackProvider)
    assert len(p._fallback_presets) == 2
