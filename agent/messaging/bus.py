"""In-memory Agent Message Bus — Phase 0 implementation.

Provides structured message logging between agents for audit trail.
Phase 0: in-memory only. Phase 1: PostgreSQL persistence.
"""

from __future__ import annotations

from messaging import AgentMessage, MessageType, MessagePriority, create_message


class AgentMessageBus:
    """In-memory message bus for inter-agent communication."""

    def __init__(self):
        self._message_log: list[AgentMessage] = []

    def send(self, msg: AgentMessage) -> None:
        """Add a message to the log."""
        self._message_log.append(msg)

    def get_messages(self, agent_name: str) -> list[AgentMessage]:
        """Get all messages sent to a specific agent."""
        return [
            m for m in self._message_log
            if m.to_agent == agent_name or m.to_agent == "*"
        ]

    def get_sent_by(self, agent_name: str) -> list[AgentMessage]:
        """Get all messages sent by a specific agent."""
        return [m for m in self._message_log if m.from_agent == agent_name]

    def get_conversation(self, correlation_id: str) -> list[AgentMessage]:
        """Get the full message chain for a correlation_id."""
        return [
            m for m in self._message_log
            if m.correlation_id == correlation_id
        ]

    def get_all(self) -> list[AgentMessage]:
        """Get all messages in the log."""
        return list(self._message_log)

    def serialize(self) -> list[dict]:
        """Serialize all messages for GraphState storage."""
        return [m.to_dict() for m in self._message_log]

    def clear(self) -> None:
        """Clear message log (call at session start)."""
        self._message_log.clear()

    @property
    def count(self) -> int:
        return len(self._message_log)


# Module-level singleton (one bus per process)
_bus: AgentMessageBus | None = None


def get_message_bus() -> AgentMessageBus:
    """Get or create the singleton message bus."""
    global _bus
    if _bus is None:
        _bus = AgentMessageBus()
    return _bus


def reset_message_bus() -> None:
    """Reset the bus (for testing)."""
    global _bus
    if _bus:
        _bus.clear()
    _bus = None
