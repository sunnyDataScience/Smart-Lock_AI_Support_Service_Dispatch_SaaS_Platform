"""LiteLLM 統一 LLM 接口。

支援所有 LiteLLM 支援的 provider（vertex_ai, openai, anthropic, ollama 等），
只需在 config.toml 的 [llm].model 填入 LiteLLM 格式的模型名稱即可。

Vertex AI 範例：model = "vertex_ai/gemini-2.5-pro"
OpenAI 範例：  model = "gpt-4o"
Ollama 範例：  model = "ollama/gemma3:4b"
"""

import os
from pathlib import Path

from langchain_litellm import ChatLiteLLM


def _ensure_vertex_credentials():
    """若 credentials.json 存在，設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數。"""
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    sa_file = Path(__file__).resolve().parents[2] / "credentials.json"
    if sa_file.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_file)


def build_litellm(config: dict):
    """依據 config 建立 ChatLiteLLM 實例。

    Args:
        config: 從 config.toml [llm] 讀取的設定 dict
            - model: LiteLLM 格式模型名（如 "vertex_ai/gemini-2.5-pro"）
            - temperature: 生成溫度（預設 0.3）
    """
    model = config.get("model", "vertex_ai/gemini-2.5-pro")
    temperature = config.get("temperature", 0.3)

    # Vertex AI 需要 credentials
    if model.startswith("vertex_ai/"):
        _ensure_vertex_credentials()

    return ChatLiteLLM(
        model=model,
        temperature=temperature,
    )
