"""LiteLLM 統一供應商 — knowledge-pipeline 唯一 LLM 介面。

2026-07-09 重構：原 langchain 適配器群（openai_llm / anthropic_llm /
ollama_llm / langchain_adapter）與 vertexai.py 收斂為本檔——與 agent 的
LiteLLMProvider 同哲學：**單一 litellm.completion 以 model 字串路由多家**，
不再依 provider 各掛 SDK。

介面與舊版完全相容（呼叫端零改動）：
  get_llm(provider, model, **kwargs)        -> generate_json(prompt, system_prompt, schema) -> dict
  get_vision_llm(provider, model, **kwargs) -> generate_from_video(video_path, system_prompt) -> str
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
import litellm

# provider 名 → litellm model 字串前綴（空字串 = model 名原樣即可路由）
_MODEL_PREFIX = {
    "vertexai": "vertex_ai/",
    "openai": "",           # gpt-4o 等原樣
    "anthropic": "",        # claude-* 原樣
    "ollama": "ollama_chat/",
}


def _ensure_credentials() -> None:
    """載入 .env 並確保 Vertex AI 認證環境變數（其餘家走各自 env key）。"""
    _root = Path(__file__).resolve().parents[1]
    load_dotenv(_root.parent / ".env")

    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        sa_file = _root.parent / "credentials.json"
        if sa_file.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_file)

    if not os.getenv("VERTEX_PROJECT") and os.getenv("VERTEX_PROJECT_ID"):
        os.environ["VERTEX_PROJECT"] = os.getenv("VERTEX_PROJECT_ID")


def resolve_model(provider: str, model: str) -> str:
    """(provider, model) → litellm model 字串。未知 provider 直接丟錯（fail-fast）。"""
    if provider not in _MODEL_PREFIX:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. Available: {', '.join(_MODEL_PREFIX)}"
        )
    if provider == "ollama" and os.getenv("OLLAMA_BASE_URL"):
        os.environ.setdefault("OLLAMA_API_BASE", os.environ["OLLAMA_BASE_URL"])
    return f"{_MODEL_PREFIX[provider]}{model}"


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw


def get_llm(provider: str, model: str, **kwargs) -> Callable:
    """回傳 generate_json closure（litellm 路由）。

    - vertexai：走原生 response_schema（生產已驗證的行為，保留）
    - 其他家：schema 嵌 system prompt + json_object + code fence 剝除
    """
    _ensure_credentials()
    litellm_model = resolve_model(provider, model)
    temperature = kwargs.get("temperature", 0.3)

    def generate_json(prompt: str, system_prompt: str, schema: dict) -> dict:
        if provider == "vertexai":
            response = litellm.completion(
                model=litellm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                response_format={
                    "type": "json_object",
                    "response_schema": schema,
                },
            )
            return json.loads(response.choices[0].message.content)

        schema_hint = json.dumps(schema, ensure_ascii=False, indent=2)
        full_system = (
            f"{system_prompt}\n\n"
            f"你必須只輸出合法的 JSON，格式嚴格遵循以下 schema：\n"
            f"```json\n{schema_hint}\n```\n"
            f"不要輸出任何 JSON 以外的內容。"
        )
        response = litellm.completion(
            model=litellm_model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return json.loads(_strip_fences(response.choices[0].message.content))

    return generate_json


def get_vision_llm(provider: str, model: str, **kwargs) -> Callable:
    """回傳 generate_from_video closure（現僅 vertexai 支援影片輸入）。"""
    if provider != "vertexai":
        raise ValueError(f"Vision LLM 目前僅支援 vertexai（got '{provider}'）")
    _ensure_credentials()
    litellm_model = resolve_model(provider, model)
    temperature = kwargs.get("temperature", 0.1)

    def generate_from_video(video_path: str, system_prompt: str) -> str:
        video_bytes = open(video_path, "rb").read()
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")
        response = litellm.completion(
            model=litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:video/mp4;base64,{video_b64}",
                            },
                        },
                    ],
                },
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content

    return generate_from_video
