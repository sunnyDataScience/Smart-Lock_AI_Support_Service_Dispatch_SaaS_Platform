"""Inter-Agent Messaging Protocol — Phase 0 (in-memory bus).

Structured messaging between agents for audit trail and correlation tracking.
Complements (does not replace) LangGraph state passing.

Spec: docs/system_design/specs/inter-agent-messaging-spec.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class MessageType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    BROADCAST = "BROADCAST"
    ESCALATION = "ESCALATION"
    HANDOFF = "HANDOFF"


class MessagePriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentMessage:
    """Structured message between agents."""

    from_agent: str
    to_agent: str                              # "*" for broadcast
    msg_type: MessageType
    payload: dict = field(default_factory=dict)

    # Auto-generated
    msg_id: str = field(default_factory=lambda: uuid4().hex[:12])
    correlation_id: str = ""                    # links request → response chains
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority: MessagePriority = MessagePriority.NORMAL
    ttl_seconds: int = 300                      # 5 minutes default
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.correlation_id:
            self.correlation_id = self.msg_id   # first message generates correlation_id

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "msg_type": self.msg_type.value,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentMessage:
        return cls(
            msg_id=d.get("msg_id", ""),
            from_agent=d.get("from_agent", ""),
            to_agent=d.get("to_agent", ""),
            msg_type=MessageType(d.get("msg_type", "REQUEST")),
            payload=d.get("payload", {}),
            correlation_id=d.get("correlation_id", ""),
            timestamp=d.get("timestamp", ""),
            priority=MessagePriority(d.get("priority", 1)),
            ttl_seconds=d.get("ttl_seconds", 300),
            metadata=d.get("metadata", {}),
        )


def create_message(
    from_agent: str,
    to_agent: str,
    msg_type: MessageType,
    payload: dict | None = None,
    correlation_id: str = "",
    priority: MessagePriority = MessagePriority.NORMAL,
) -> AgentMessage:
    """Convenience factory for creating messages."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        msg_type=msg_type,
        payload=payload or {},
        correlation_id=correlation_id,
        priority=priority,
    )
