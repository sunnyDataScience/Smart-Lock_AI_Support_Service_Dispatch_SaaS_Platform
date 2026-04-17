"""Vertex AI (Gemini) LLM provider — 透過 LiteLLM 統一接口。"""

import json
import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
import litellm


def _ensure_credentials():
    """確保 Vertex AI 認證環境變數已設定。"""
    _root = Path(__file__).resolve().parents[1]
    load_dotenv(_root.parent / ".env")

    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        sa_file = _root.parent / "credentials.json"
        if sa_file.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_file)

    if not os.getenv("VERTEX_PROJECT") and os.getenv("VERTEX_PROJECT_ID"):
        os.environ["VERTEX_PROJECT"] = os.getenv("VERTEX_PROJECT_ID")


def get_vertexai_llm(model_name: str, **kwargs) -> Callable:
    """Return a generate_json closure backed by Vertex AI via LiteLLM.

    Parameters
    ----------
    model_name : str
        Model identifier, e.g. ``"gemini-2.5-flash"``.
    **kwargs
        Extra generation parameters (``temperature``, etc.).
    """
    _ensure_credentials()
    temperature = kwargs.get("temperature", 0.3)
    litellm_model = f"vertex_ai/{model_name}"

    def generate_json(prompt: str, system_prompt: str, schema: dict) -> dict:
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

    return generate_json


def get_vertexai_vision_llm(model_name: str, **kwargs) -> Callable:
    """Return a generate_from_video closure backed by Vertex AI via LiteLLM.

    Parameters
    ----------
    model_name : str
        Model identifier, e.g. ``"gemini-2.5-flash"``.
    **kwargs
        Extra generation parameters (``temperature``, etc.).

    Returns
    -------
    Callable
        ``generate_from_video(video_path, system_prompt) -> str``
    """
    _ensure_credentials()
    temperature = kwargs.get("temperature", 0.1)
    litellm_model = f"vertex_ai/{model_name}"

    def generate_from_video(video_path: str, system_prompt: str) -> str:
        import base64
        video_bytes = open(video_path, "rb").read()
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")

        response = litellm.completion(
            model=litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:video/mp4;base64,{video_b64}",
                        },
                    },
                ]},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content

    return generate_from_video
