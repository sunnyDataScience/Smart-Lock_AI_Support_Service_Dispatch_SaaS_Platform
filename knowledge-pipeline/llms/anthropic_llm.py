"""Anthropic LLM provider（透過 LangChain）。"""

from typing import Callable

from llms.langchain_adapter import build_langchain_llm


def get_anthropic_llm(model_name: str, **kwargs) -> Callable:
    """Return a generate_json closure backed by Anthropic.

    需要環境變數 ``ANTHROPIC_API_KEY``。
    安裝：``pip install langchain-anthropic``
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "使用 Anthropic provider 需要安裝 langchain-anthropic：\n"
            "  pip install langchain-anthropic"
        )

    chat = ChatAnthropic(
        model=model_name,
        temperature=kwargs.get("temperature", 0.3),
    )
    return build_langchain_llm(chat)
