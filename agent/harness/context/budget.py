"""Token budget calculator for context assembly.

Stub -- Phase 4 implementation.
"""


def calculate_budget(system_prompt_tokens: int, max_budget: int = 4096) -> int:
    """Return remaining token budget after system prompt allocation."""
    return max(0, max_budget - system_prompt_tokens)
