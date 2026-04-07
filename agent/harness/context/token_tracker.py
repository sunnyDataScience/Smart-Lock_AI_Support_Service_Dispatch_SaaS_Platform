"""Token cost circuit breaker — LLM proxy with usage tracking.

Wraps any LangChain LLM to transparently track token usage per session.
When the session budget is exceeded, raises TokenBudgetExceeded.

Usage:
    from harness.context.token_tracker import TokenTrackingLLM
    from harness.context.budget import SessionBudget

    budget = SessionBudget(max_budget_tokens=50000)
    tracked_llm = TokenTrackingLLM(llm, budget, model_name="gemini-2.5-flash")
    # All ainvoke() calls now tracked; budget shared across all wrappers
"""

from __future__ import annotations

from harness.context.budget import SessionBudget, TokenUsage


class TokenBudgetExceeded(Exception):
    """Raised when session token budget is exhausted."""
    pass


class TokenTrackingLLM:
    """Proxy that wraps a LangChain LLM to track token usage."""

    def __init__(
        self,
        llm,
        session_budget: SessionBudget,
        model_name: str = "",
        warn_threshold: float = 0.8,
    ):
        self._llm = llm
        self._budget = session_budget
        self._model_name = model_name
        self._warn_threshold = warn_threshold

    @property
    def session_budget(self) -> SessionBudget:
        return self._budget

    async def ainvoke(self, messages, **kwargs):
        """Invoke LLM with token tracking and budget enforcement."""
        # Pre-check: budget exceeded
        if (
            self._budget.max_budget_tokens > 0
            and self._budget.remaining_budget <= 0
        ):
            raise TokenBudgetExceeded(
                f"Token 預算已用盡: {self._budget.total_tokens}/{self._budget.max_budget_tokens}"
            )

        response = await self._llm.ainvoke(messages, **kwargs)

        # Extract and record token usage
        usage = self._extract_usage(response)
        if usage:
            self._budget.record(usage)
            # Warn if approaching limit
            if (
                self._budget.max_budget_tokens > 0
                and self._budget.budget_utilization >= self._warn_threshold
                and self._budget.budget_utilization < 1.0
            ):
                print(
                    f"  [TokenTracker] ⚠ 預算使用 {self._budget.budget_utilization:.0%} "
                    f"({self._budget.total_tokens}/{self._budget.max_budget_tokens})"
                )

        return response

    def _extract_usage(self, response) -> TokenUsage | None:
        """Extract token usage from LLM response metadata."""
        meta = getattr(response, "response_metadata", {})
        if not meta:
            return None

        # Google Gemini / Vertex AI format
        usage_meta = meta.get("usage_metadata", {})
        if usage_meta:
            return TokenUsage(
                input_tokens=usage_meta.get("input_tokens", 0)
                or usage_meta.get("prompt_token_count", 0),
                output_tokens=usage_meta.get("output_tokens", 0)
                or usage_meta.get("candidates_token_count", 0),
                model=self._model_name,
            )

        # OpenAI / generic format
        usage = meta.get("usage", {})
        if usage:
            return TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=self._model_name,
            )

        return None

    def bind_tools(self, *args, **kwargs):
        """Wrap bound LLM so tool calls are also tracked."""
        bound = self._llm.bind_tools(*args, **kwargs)
        return TokenTrackingLLM(
            bound, self._budget, self._model_name, self._warn_threshold
        )

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped LLM."""
        return getattr(self._llm, name)
