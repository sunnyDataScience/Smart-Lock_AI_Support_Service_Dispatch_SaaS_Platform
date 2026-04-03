"""Token budget calculator and cost tracker for context assembly.

GAP #4 — Token cost control.
Phase 0-1: approximate counting via character-based heuristic.
Phase 2: tiktoken (OpenAI) or model-specific tokenizer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("harness.context.budget")

# Approximate tokens-per-character ratios by language
_CHARS_PER_TOKEN_ZH = 1.5  # Chinese: ~1.5 chars per token
_CHARS_PER_TOKEN_EN = 4.0  # English: ~4 chars per token
_ZH_RANGE = range(0x4E00, 0x9FFF + 1)  # CJK Unified Ideographs


@dataclass
class TokenUsage:
    """Track token consumption for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on model pricing (approximate)."""
        rates = _MODEL_PRICING.get(self.model, _MODEL_PRICING["default"])
        return (
            self.input_tokens * rates["input"] / 1_000_000
            + self.output_tokens * rates["output"] / 1_000_000
        )


# Pricing per 1M tokens (USD), approximate as of 2026-Q1
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "default": {"input": 1.00, "output": 4.00},
}


@dataclass
class SessionBudget:
    """Accumulated token usage for a conversation session."""

    session_id: str = ""
    usages: list[TokenUsage] = field(default_factory=list)
    max_budget_tokens: int = 0

    @property
    def total_input(self) -> int:
        return sum(u.input_tokens for u in self.usages)

    @property
    def total_output(self) -> int:
        return sum(u.output_tokens for u in self.usages)

    @property
    def total_tokens(self) -> int:
        return self.total_input + self.total_output

    @property
    def total_cost_usd(self) -> float:
        return sum(u.estimated_cost_usd for u in self.usages)

    @property
    def remaining_budget(self) -> int:
        if self.max_budget_tokens <= 0:
            return 0
        return max(0, self.max_budget_tokens - self.total_tokens)

    @property
    def budget_utilization(self) -> float:
        if self.max_budget_tokens <= 0:
            return 0.0
        return min(1.0, self.total_tokens / self.max_budget_tokens)

    def record(self, usage: TokenUsage) -> None:
        self.usages.append(usage)
        if self.budget_utilization > 0.9:
            logger.warning(
                "Token budget >90%% utilized: %d/%d (session=%s)",
                self.total_tokens,
                self.max_budget_tokens,
                self.session_id,
            )


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using character-based heuristic.

    Mixed Chinese/English text is split by character type and counted
    with language-appropriate ratios.
    """
    if not text:
        return 0
    zh_chars = sum(1 for ch in text if ord(ch) in _ZH_RANGE)
    en_chars = len(text) - zh_chars
    return int(zh_chars / _CHARS_PER_TOKEN_ZH + en_chars / _CHARS_PER_TOKEN_EN)


def calculate_budget(system_prompt_tokens: int, max_budget: int = 4096) -> int:
    """Return remaining token budget after system prompt allocation."""
    return max(0, max_budget - system_prompt_tokens)


def calculate_context_budget(
    system_prompt: str,
    knowledge_context: str = "",
    conversation_history: str = "",
    max_budget: int = 4096,
) -> dict:
    """Calculate token allocation for context assembly.

    Returns a breakdown of token usage and remaining budget for the
    LLM response.
    """
    sys_tokens = estimate_tokens(system_prompt)
    kb_tokens = estimate_tokens(knowledge_context)
    hist_tokens = estimate_tokens(conversation_history)
    used = sys_tokens + kb_tokens + hist_tokens
    remaining = max(0, max_budget - used)

    return {
        "system_prompt_tokens": sys_tokens,
        "knowledge_tokens": kb_tokens,
        "history_tokens": hist_tokens,
        "total_used": used,
        "remaining": remaining,
        "max_budget": max_budget,
        "utilization": min(1.0, used / max_budget) if max_budget > 0 else 0.0,
    }
