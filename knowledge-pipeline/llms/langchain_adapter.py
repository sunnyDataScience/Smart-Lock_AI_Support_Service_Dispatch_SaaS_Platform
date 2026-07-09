"""LangChain ChatModel → generate_json closure 轉接器。

將任何 LangChain ChatModel 包裝成與 vertexai.py 相同的
``generate_json(prompt, system_prompt, schema) -> dict`` 介面，
讓 pipeline 呼叫端零改動。
"""

import json
import re
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage


def build_langchain_llm(chat_model) -> Callable:
    """將 LangChain ChatModel 包裝成 generate_json closure。

    Parameters
    ----------
    chat_model : BaseChatModel
        任何 LangChain ChatModel 實例（ChatOpenAI, ChatAnthropic, ChatOllama 等）。

    Returns
    -------
    Callable
        ``generate_json(prompt, system_prompt, schema) -> dict``
    """

    def generate_json(prompt: str, system_prompt: str, schema: dict) -> dict:
        # 將 schema 描述嵌入 system prompt，引導 LLM 輸出正確的 JSON
        schema_hint = json.dumps(schema, ensure_ascii=False, indent=2)
        full_system = (
            f"{system_prompt}\n\n"
            f"你必須只輸出合法的 JSON，格式嚴格遵循以下 schema：\n"
            f"```json\n{schema_hint}\n```\n"
            f"不要輸出任何 JSON 以外的內容。"
        )

        response = chat_model.invoke([
            SystemMessage(content=full_system),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()

        # 清除 code fence
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        return json.loads(raw)

    return generate_json
