"""In-memory message bus for inter-agent communication.

GAP #3 / Contract M5 -- Inter-Agent Messaging Protocol.
Phase 0: in-memory list; Phase 2 target: PostgreSQL / Redis Streams.
"""

from __future__ import annotations

import logging
from collections import Counter

from .protocol import (
    AgentMessage,
    MessageType,
    MessagePriority,
    create_message,
    validate_message,
)

logger = logging.getLogger(__name__)

# Maximum times a single agent may appear as sender in one correlation chain
# before we flag it as circular routing.
_MAX_AGENT_APPEARANCES = 2


class AgentMessageBus:
    """Lightweight inter-agent message bus.

    Phase 0 implementation: pure in-memory ``list[AgentMessage]``.
    Thread-safe guarantees are *not* provided in Phase 0 -- LangGraph
    executes nodes sequentially within a single thread per invocation.

    Parameters
    ----------
    registered_agents:
        List of valid agent names.  ``send()`` rejects messages to
        unknown agents (except broadcast ``to_agent="*"``).
    """

    def __init__(self, registered_agents: list[str]) -> None:
        if not registered_agents:
            raise ValueError("registered_agents must contain at least one agent name")
        self._registered: set[str] = set(registered_agents)
        self._message_log: list[AgentMessage] = []
        logger.info(
            "AgentMessageBus initialised with %d agents: %s",
            len(self._registered),
            sorted(self._registered),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, message: AgentMessage) -> None:
        """Validate and append *message* to the log.

        Raises
        ------
        ValueError
            If the message fails validation or the target agent is unknown.
        RuntimeError
            If circular routing is detected within the correlation chain.
        """
        validate_message(message)

        # Broadcast skips target-agent check
        if message.to_agent != "*" and message.to_agent not in self._registered:
            raise ValueError(
                f"Target agent '{message.to_agent}' is not registered. "
                f"Known agents: {sorted(self._registered)}"
            )

        if self._detect_circular_routing(message):
            raise RuntimeError(
                f"Circular routing detected: agent '{message.from_agent}' appeared "
                f"more than {_MAX_AGENT_APPEARANCES} times in correlation chain "
                f"'{message.correlation_id}'"
            )

        self._message_log.append(message)
        logger.info(
            "MSG [%s] %s -> %s  type=%s  corr=%s  prio=%s",
            message.msg_id[:8],
            message.from_agent,
            message.to_agent,
            message.msg_type.value,
            message.correlation_id[:8],
            message.priority.name,
        )

    def broadcast(
        self,
        from_agent: str,
        payload: dict,
        *,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: dict | None = None,
    ) -> None:
        """Send a BROADCAST message to all registered agents.

        Internally creates a single ``AgentMessage`` with ``to_agent="*"``
        and appends it to the log.
        """
        msg = create_message(
            from_agent=from_agent,
            to_agent="*",
            msg_type=MessageType.BROADCAST,
            payload=payload,
            priority=priority,
            metadata=metadata,
        )
        self.send(msg)

    def get_messages(
        self,
        agent_name: str,
        *,
        since: str | None = None,
    ) -> list[AgentMessage]:
        """Return messages addressed to *agent_name* (or broadcast).

        Parameters
        ----------
        agent_name:
            The receiving agent whose inbox to query.
        since:
            Optional ISO-8601 timestamp.  Only messages with
            ``timestamp >= since`` are returned.
        """
        results: list[AgentMessage] = []
        for msg in self._message_log:
            if msg.to_agent not in (agent_name, "*"):
                continue
            if since is not None and msg.timestamp < since:
                continue
            results.append(msg)
        return results

    def get_conversation(self, correlation_id: str) -> list[AgentMessage]:
        """Return all messages sharing *correlation_id*, ordered by timestamp."""
        chain = [m for m in self._message_log if m.correlation_id == correlation_id]
        chain.sort(key=lambda m: m.timestamp)
        return chain

    @property
    def message_count(self) -> int:
        """Total number of messages in the log."""
        return len(self._message_log)

    @property
    def registered_agents(self) -> frozenset[str]:
        """Read-only view of registered agent names."""
        return frozenset(self._registered)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_circular_routing(self, message: AgentMessage) -> bool:
        """Return True if appending *message* would create a circular route.

        A circular route is defined as the same ``from_agent`` appearing
        more than ``_MAX_AGENT_APPEARANCES`` times within a single
        correlation chain.
        """
        counts: Counter[str] = Counter()
        for existing in self._message_log:
            if existing.correlation_id == message.correlation_id:
                counts[existing.from_agent] += 1

        # Include the message about to be sent
        counts[message.from_agent] += 1

        return counts[message.from_agent] > _MAX_AGENT_APPEARANCES
