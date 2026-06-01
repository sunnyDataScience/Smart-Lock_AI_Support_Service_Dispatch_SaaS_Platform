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


_GEMINI3_REASONING_LEVELS = {"minimal", "low", "medium", "high"}


def build_litellm(config: dict):
    """依據 config 建立 ChatLiteLLM 實例。

    Args:
        config: 從 config.toml [llm] 讀取的設定 dict
            - model: LiteLLM 格式模型名（如 "vertex_ai/gemini-2.5-pro"、"vertex_ai/gemini-3-flash-preview"）
            - temperature: 生成溫度（預設 0.3）
            - thinking_budget: Gemini 2.5 thinking token 上限（預設 None = 無上限）
            - reasoning_effort: Gemini 3+ 思考等級，minimal | low | medium | high
              （Gemini 3 模型不再支援 thinking_budget，改走此參數）
            - vertex_location: 覆寫 Vertex AI 區域（如 "global"，preview 模型常需要）；
              未設定則由 LiteLLM 讀環境變數 VERTEX_LOCATION
    """
    model = config.get("model", "vertex_ai/gemini-2.5-pro")
    temperature = config.get("temperature", 0.3)
    thinking_budget = config.get("thinking_budget")
    reasoning_effort = config.get("reasoning_effort")
    vertex_location = config.get("vertex_location")

    if model.startswith("vertex_ai/"):
        _ensure_vertex_credentials()

    # ChatLiteLLM 把非標準參數（reasoning_effort / thinking）透過 model_kwargs 傳給 LiteLLM
    extra_kwargs: dict = {}

    is_gemini3 = "gemini-3" in model
    if is_gemini3 and reasoning_effort:
        level = str(reasoning_effort).lower()
        if level not in _GEMINI3_REASONING_LEVELS:
            raise ValueError(
                f"reasoning_effort 必須是 {sorted(_GEMINI3_REASONING_LEVELS)} 之一，收到：{reasoning_effort}"
            )
        extra_kwargs["reasoning_effort"] = level
    elif not is_gemini3 and thinking_budget is not None:
        extra_kwargs["thinking"] = {"type": "enabled", "budget_tokens": int(thinking_budget)}

    if vertex_location:
        extra_kwargs["vertex_location"] = vertex_location

    # BR-A01-02/AC-V11-11：生成期 token 上限。
    # LiteLLM max_tokens → Gemini maxOutputTokens（精確 token 計數，免費，無需
    # tiktoken/sentencepiece）。未設定或為 None 時維持原有行為（無上限）。
    max_output_tokens = config.get("max_output_tokens")

    init_kwargs: dict = {"model": model, "temperature": temperature}
    if max_output_tokens is not None:
        init_kwargs["max_tokens"] = int(max_output_tokens)
    if extra_kwargs:
        init_kwargs["model_kwargs"] = extra_kwargs

    return ChatLiteLLM(**init_kwargs)
