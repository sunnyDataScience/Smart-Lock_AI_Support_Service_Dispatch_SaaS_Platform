"""LLM provider registry and factory."""

from typing import Callable

from llms.vertexai import get_vertexai_llm, get_vertexai_vision_llm
from llms.openai_llm import get_openai_llm
from llms.anthropic_llm import get_anthropic_llm
from llms.ollama_llm import get_ollama_llm

LLM_REGISTRY: dict[str, Callable] = {
    "vertexai": get_vertexai_llm,
    "openai": get_openai_llm,
    "anthropic": get_anthropic_llm,
    "ollama": get_ollama_llm,
}

VISION_REGISTRY: dict[str, Callable] = {
    "vertexai": get_vertexai_vision_llm,
}


def get_llm(provider: str, model: str, **kwargs) -> Callable:
    """Build and return an LLM callable for the given provider.

    Returns a ``generate_json(prompt, system_prompt, schema) -> dict`` closure.
    """
    builder = LLM_REGISTRY.get(provider)
    if builder is None:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {', '.join(LLM_REGISTRY)}"
        )
    return builder(model, **kwargs)


def get_vision_llm(provider: str, model: str, **kwargs) -> Callable:
    """Build and return a vision LLM callable.

    Returns a ``generate_from_video(video_path, system_prompt) -> str`` closure.
    """
    builder = VISION_REGISTRY.get(provider)
    if builder is None:
        raise ValueError(
            f"Unknown vision LLM provider '{provider}'. "
            f"Available: {', '.join(VISION_REGISTRY)}"
        )
    return builder(model, **kwargs)
