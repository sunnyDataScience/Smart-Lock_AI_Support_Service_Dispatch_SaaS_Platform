"""LLM 統一接口 — 透過 LiteLLM 支援所有 provider。

Usage:
    from llms import get_llm
    model = get_llm(cfg.llm)  # cfg.llm = {"model": "vertex_ai/gemini-2.5-pro", "temperature": 0.3}
"""

from .litellm_model import build_litellm


def get_llm(llm_config: dict):
    """依 config.toml [llm] 設定建立 LLM 實例。"""
    model = llm_config.get("model", "vertex_ai/gemini-2.5-pro")
    print(f"[*] 初始化 LLM: {model}")
    return build_litellm(llm_config)
