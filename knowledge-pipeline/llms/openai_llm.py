"""OpenAI LLM provider（透過 LangChain）。"""

from typing import Callable

from llms.langchain_adapter import build_langchain_llm


def get_openai_llm(model_name: str, **kwargs) -> Callable:
    """Return a generate_json closure backed by OpenAI.

    需要環境變數 ``OPENAI_API_KEY``。
    安裝：``pip install langchain-openai``
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "使用 OpenAI provider 需要安裝 langchain-openai：\n"
            "  pip install langchain-openai"
        )

    chat = ChatOpenAI(
        model=model_name,
        temperature=kwargs.get("temperature", 0.3),
    )
    return build_langchain_llm(chat)
