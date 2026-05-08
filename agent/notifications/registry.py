"""Channel adapter registry — config-driven lookup.

Mirrors the dict-registry pattern used by ``agent.memory`` and
``agent.storage``: a module-level dict mapping ``ChannelType`` →
zero-arg builder callable. Bootstrap registers the default builders once at
startup; tests / V1.5 vendor swaps replace entries by re-registering.

The registry intentionally has no global lock — registration happens on the
single startup task, and ``get_adapter`` is read-only after that.
"""
from __future__ import annotations

from typing import Callable

from notifications.base import ChannelAdapter, ChannelType

# Type alias — keep signatures readable at call sites.
AdapterBuilder = Callable[[], ChannelAdapter]

CHANNEL_REGISTRY: dict[ChannelType, AdapterBuilder] = {}


def register_channel(ct: ChannelType, builder: AdapterBuilder) -> None:
    """Register an adapter builder for ``ct``.

    Idempotent: re-registering the same channel replaces the previous entry
    (V1.5 will use this to swap stub → real vendor without touching callers).
    """
    CHANNEL_REGISTRY[ct] = builder


def get_adapter(ct: ChannelType) -> ChannelAdapter:
    """Look up an adapter for ``ct``. Raises ``ValueError`` if unregistered.

    Builder is invoked per call — adapters are expected to be cheap to
    construct and either stateless or carry their own internal singletons
    (e.g. LINE adapter delegates to module-level state in
    ``agent.core.line_bot``).
    """
    builder = CHANNEL_REGISTRY.get(ct)
    if builder is None:
        raise ValueError(
            f"No adapter registered for channel: {ct.value} "
            f"(available: {[c.value for c in CHANNEL_REGISTRY]})"
        )
    return builder()
