"""LLM 薄層 — litellm + JSON schema 強制（CR-0139 D5）。

knowledge-pipeline 的 llms/provider.py 為 package=false 不可 import，
比照 rag/ 自帶 embedding.py 的自足模式，此處自帶最小 wrapper。
模型走 REFINERY_LLM_MODEL（預設 vertex_ai/gemini-2.5-flash），測試注入 fake callable。
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Callable

# generate_json(prompt, system_prompt, schema) -> dict
GenerateJson = Callable[[str, str, dict], dict]

_DEFAULT_MODEL = "vertex_ai/gemini-2.5-flash"


def _ensure_credentials() -> None:
    """本機 .env / credentials.json 便利載入（雲端走 ADC，缺檔安靜跳過）。"""
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[2]
        load_dotenv(root / ".env")
        cred = root / "credentials.json"
        if cred.exists() and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred)
    except ImportError:
        pass


def _strip_code_fence(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


def generate_json(prompt: str, system_prompt: str, schema: dict) -> dict:
    """呼叫 LLM 產 JSON；vertex 走原生 response_schema，其他家 schema 嵌 system prompt。"""
    import litellm

    _ensure_credentials()
    model = os.getenv("REFINERY_LLM_MODEL", _DEFAULT_MODEL)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": float(os.getenv("REFINERY_LLM_TEMPERATURE", "0.2")),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    if model.startswith("vertex_ai/"):
        kwargs["response_format"] = {"type": "json_object", "response_schema": schema}
    else:
        kwargs["messages"][0]["content"] += (
            "\n\n輸出必須是符合以下 JSON Schema 的單一 JSON 物件，不得有其他文字：\n"
            + json.dumps(schema, ensure_ascii=False)
        )
    resp = litellm.completion(**kwargs)
    return json.loads(_strip_code_fence(resp.choices[0].message.content))
