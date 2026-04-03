"""AgentMessage schema, enums, and factory helpers.

GAP #3 / Contract M5 -- Inter-Agent Messaging Protocol.
Phase 0: in-memory only; no external dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    """Discriminator for inter-agent message semantics."""

    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    ESCALATION = "escalation"
    HANDOFF = "handoff"


class MessagePriority(int, Enum):
    """Numeric priority levels -- higher value = more urgent."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------

_DEFAULT_TTL = 300  # seconds


@dataclass(frozen=True, slots=True)
class AgentMessage:
    """Single inter-agent message.

    Immutable after creation.  Serialize with ``to_dict()`` for state storage.
    """

    from_agent: str
    to_agent: str
    msg_type: MessageType
    payload: dict
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    priority: MessagePriority = MessagePriority.NORMAL
    ttl_seconds: int = _DEFAULT_TTL
    metadata: dict = field(default_factory=dict)

    # -- serialisation helpers ------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain dict suitable for JSON / state storage."""
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
    def from_dict(cls, data: dict) -> AgentMessage:
        """Reconstruct an AgentMessage from a plain dict."""
        return cls(
            msg_id=data["msg_id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            msg_type=MessageType(data["msg_type"]),
            payload=data.get("payload", {}),
            correlation_id=data["correlation_id"],
            timestamp=data["timestamp"],
            priority=MessagePriority(data.get("priority", MessagePriority.NORMAL)),
            ttl_seconds=data.get("ttl_seconds", _DEFAULT_TTL),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_message(
    *,
    from_agent: str,
    to_agent: str,
    msg_type: MessageType,
    payload: dict,
    correlation_id: str | None = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    ttl_seconds: int = _DEFAULT_TTL,
    metadata: dict | None = None,
) -> AgentMessage:
    """Build a new ``AgentMessage`` with sensible defaults.

    If *correlation_id* is ``None`` a fresh UUID is generated.
    """
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        msg_type=msg_type,
        payload=payload,
        correlation_id=correlation_id or uuid.uuid4().hex,
        priority=priority,
        ttl_seconds=ttl_seconds,
        metadata=metadata or {},
    )


def create_response(
    request: AgentMessage,
    *,
    from_agent: str,
    payload: dict,
    priority: MessagePriority | None = None,
    metadata: dict | None = None,
) -> AgentMessage:
    """Build a RESPONSE that inherits *correlation_id* from *request*."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent=request.from_agent,
        msg_type=MessageType.RESPONSE,
        payload=payload,
        correlation_id=request.correlation_id,
        priority=priority or request.priority,
        metadata=metadata or {},
    )


def create_escalation(
    request: AgentMessage,
    *,
    from_agent: str,
    to_agent: str,
    reason: str,
    partial_result: dict | None = None,
    priority: MessagePriority = MessagePriority.HIGH,
    metadata: dict | None = None,
) -> AgentMessage:
    """Build an ESCALATION that carries context from the original request."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        msg_type=MessageType.ESCALATION,
        payload={
            "reason": reason,
            "original_payload": request.payload,
            "partial_result": partial_result or {},
        },
        correlation_id=request.correlation_id,
        priority=priority,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_message(message: AgentMessage) -> list[str]:
    """Return a list of validation error strings.  Empty list = valid.

    Raises ``ValueError`` if critical fields are missing or malformed.
    """
    errors: list[str] = []

    if not message.from_agent or not message.from_agent.strip():
        errors.append("from_agent must be a non-empty string")

    if not message.to_agent or not message.to_agent.strip():
        errors.append("to_agent must be a non-empty string")

    if not isinstance(message.msg_type, MessageType):
        errors.append(f"msg_type must be a MessageType enum, got {type(message.msg_type)}")

    if not isinstance(message.payload, dict):
        errors.append(f"payload must be a dict, got {type(message.payload)}")

    if message.ttl_seconds < 0:
        errors.append(f"ttl_seconds must be >= 0, got {message.ttl_seconds}")

    if not isinstance(message.priority, MessagePriority):
        errors.append(f"priority must be a MessagePriority enum, got {type(message.priority)}")

    if errors:
        raise ValueError(f"AgentMessage validation failed: {'; '.join(errors)}")

    return errors
