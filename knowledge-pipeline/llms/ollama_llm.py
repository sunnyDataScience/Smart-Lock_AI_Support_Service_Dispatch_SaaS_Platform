"""Ollama LLM provider（透過 LangChain）。"""

import os
from typing import Callable

from llms.langchain_adapter import build_langchain_llm


def get_ollama_llm(model_name: str, **kwargs) -> Callable:
    """Return a generate_json closure backed by Ollama.

    可選環境變數 ``OLLAMA_BASE_URL``（預設 http://localhost:11434）。
    安裝：``pip install langchain-ollama``
    """
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ImportError(
            "使用 Ollama provider 需要安裝 langchain-ollama：\n"
            "  pip install langchain-ollama"
        )

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    chat = ChatOllama(
        model=model_name,
        temperature=kwargs.get("temperature", 0.3),
        base_url=base_url,
    )
    return build_langchain_llm(chat)
