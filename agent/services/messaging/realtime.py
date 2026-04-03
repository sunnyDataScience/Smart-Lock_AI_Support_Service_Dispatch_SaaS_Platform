"""Real-time messaging service for admin-technician communication (GAP #7).

Architecture: FastAPI WebSocket + Redis pub/sub.
Each work order has a dedicated channel for real-time communication.

Phase 0: In-memory channel registry, in-memory message buffer.
Phase 1: PostgreSQL persistence for chat_messages table.
Phase 2: Redis pub/sub for horizontal scaling across multiple instances.
"""

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

logger = logging.getLogger("services.messaging.realtime")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ChatMessageType(str, Enum):
    """Supported message types for work-order chat channels."""

    TEXT = "text"
    IMAGE = "image"
    LOCATION = "location"
    SYSTEM = "system_notification"


class ChannelStatus(str, Enum):
    """Lifecycle status of a chat channel bound to a work order."""

    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class ChatMessage:
    """Single chat message within a work-order channel.

    ``content`` is a plain string for TEXT, or a JSON-encoded string for
    IMAGE ({"url", "thumbnail_url", "caption"}),
    LOCATION ({"lat", "lng", "address"}), and
    SYSTEM ({"event", "old_status", "new_status", "detail"}).
    """

    work_order_id: str
    sender_id: str
    sender_role: str  # "admin" | "technician" | "system"
    msg_type: ChatMessageType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON transport."""
        data = asdict(self)
        # Enum -> str for JSON compatibility
        data["msg_type"] = self.msg_type.value
        return data

    def to_json(self) -> str:
        """Serialise to a JSON string for WebSocket frames."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        """Reconstruct a ChatMessage from a plain dict."""
        data = dict(data)  # shallow copy to avoid mutating caller's dict
        raw_type = data.get("msg_type", "text")
        data["msg_type"] = ChatMessageType(raw_type)
        return cls(**data)


# ---------------------------------------------------------------------------
# Participant tracking
# ---------------------------------------------------------------------------

@dataclass
class _ChannelParticipant:
    """Internal record for a WebSocket subscriber."""

    websocket: Any  # fastapi.WebSocket -- kept as Any to avoid hard dep
    user_id: str
    role: str
    connected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Channel manager (Phase 0: in-memory)
# ---------------------------------------------------------------------------

class RealtimeChannelManager:
    """Manages WebSocket channels for work order communication.

    Phase 0: In-memory channel registry and message buffer.
    Phase 2: Redis pub/sub for multi-instance horizontal scaling.
    """

    # Max messages kept in the in-memory buffer per channel.
    _BUFFER_LIMIT: int = 200

    def __init__(self) -> None:
        # work_order_id -> list of _ChannelParticipant
        self._channels: dict[str, list[_ChannelParticipant]] = defaultdict(list)
        # work_order_id -> recent ChatMessage objects (ring buffer)
        self._message_buffer: dict[str, list[ChatMessage]] = defaultdict(list)
        # work_order_id -> ChannelStatus
        self._channel_status: dict[str, ChannelStatus] = {}

    # -- subscription ---------------------------------------------------------

    async def subscribe(
        self,
        work_order_id: str,
        websocket: Any,
        user_id: str,
        role: str,
    ) -> None:
        """Subscribe a WebSocket connection to a work order channel.

        Adds the connection to the in-memory registry and broadcasts a
        system notification informing other participants.

        Raises ValueError if the channel is archived.
        """
        status = self._channel_status.get(work_order_id, ChannelStatus.ACTIVE)
        if status == ChannelStatus.ARCHIVED:
            raise ValueError(
                f"Channel for work_order {work_order_id} is archived (read-only)"
            )

        participant = _ChannelParticipant(
            websocket=websocket,
            user_id=user_id,
            role=role,
        )
        self._channels[work_order_id].append(participant)
        self._channel_status.setdefault(work_order_id, ChannelStatus.ACTIVE)

        logger.info(
            "user %s (%s) subscribed to channel %s",
            user_id, role, work_order_id,
        )

        # Notify existing participants
        await self.send_system_notification(
            work_order_id,
            json.dumps({
                "event": "participant_joined",
                "user_id": user_id,
                "role": role,
            }, ensure_ascii=False),
        )

    async def unsubscribe(self, work_order_id: str, websocket: Any) -> None:
        """Remove a WebSocket connection from a channel.

        Broadcasts a system notification when the participant leaves.
        """
        participants = self._channels.get(work_order_id, [])
        removed: _ChannelParticipant | None = None

        for p in participants:
            if p.websocket is websocket:
                removed = p
                break

        if removed is None:
            logger.warning(
                "unsubscribe called but websocket not found in channel %s",
                work_order_id,
            )
            return

        participants.remove(removed)
        logger.info(
            "user %s (%s) unsubscribed from channel %s",
            removed.user_id, removed.role, work_order_id,
        )

        # Clean up empty channel list (keep status for archival tracking)
        if not participants:
            del self._channels[work_order_id]

        await self.send_system_notification(
            work_order_id,
            json.dumps({
                "event": "participant_left",
                "user_id": removed.user_id,
                "role": removed.role,
            }, ensure_ascii=False),
        )

    # -- messaging ------------------------------------------------------------

    async def broadcast(self, message: ChatMessage) -> None:
        """Send message to all subscribers of the work order channel.

        The message is appended to the in-memory buffer and sent to every
        connected WebSocket.  Delivery failures (broken pipe, etc.) are
        logged but do not prevent delivery to other participants.

        TODO Phase 1: persist to PostgreSQL before broadcast.
        TODO Phase 2: publish to Redis channel for cross-instance delivery.
        """
        work_order_id = message.work_order_id

        # Buffer the message (ring buffer, trim oldest when over limit)
        buf = self._message_buffer[work_order_id]
        buf.append(message)
        if len(buf) > self._BUFFER_LIMIT:
            self._message_buffer[work_order_id] = buf[-self._BUFFER_LIMIT :]

        # Deliver to all connected participants
        payload = message.to_json()
        participants = self._channels.get(work_order_id, [])

        for p in list(participants):  # iterate over copy for safe removal
            try:
                await p.websocket.send_text(payload)
            except Exception:
                logger.exception(
                    "failed to deliver message to user %s in channel %s; "
                    "removing broken connection",
                    p.user_id, work_order_id,
                )
                # Remove broken connection
                participants.remove(p)

    async def send_system_notification(
        self, work_order_id: str, content: str
    ) -> None:
        """Send a system notification to all participants of a channel.

        Convenience wrapper that constructs a SYSTEM-type ChatMessage and
        broadcasts it.
        """
        message = ChatMessage(
            work_order_id=work_order_id,
            sender_id="system",
            sender_role="system",
            msg_type=ChatMessageType.SYSTEM,
            content=content,
        )
        await self.broadcast(message)

    # -- queries --------------------------------------------------------------

    def get_channel_participants(self, work_order_id: str) -> list[dict[str, str]]:
        """List current participants in a channel.

        Returns a list of dicts with ``user_id``, ``role``, and
        ``connected_at`` for each active WebSocket subscriber.
        """
        participants = self._channels.get(work_order_id, [])
        return [
            {
                "user_id": p.user_id,
                "role": p.role,
                "connected_at": p.connected_at,
            }
            for p in participants
        ]

    async def get_message_history(
        self, work_order_id: str, limit: int = 50
    ) -> list[ChatMessage]:
        """Get recent messages for a work order from the in-memory buffer.

        Returns up to ``limit`` most-recent messages, ordered oldest-first.

        TODO Phase 1: fall through to RealtimeMessagePersistence.get_history
             when the buffer is insufficient.
        """
        buf = self._message_buffer.get(work_order_id, [])
        # Return the tail of the buffer
        return list(buf[-limit:])

    # -- lifecycle ------------------------------------------------------------

    def archive_channel(self, work_order_id: str) -> None:
        """Mark a channel as archived (read-only).

        Called when the associated work order is completed or cancelled.
        Existing connections are not forcibly closed; they simply cannot
        send new messages.
        """
        self._channel_status[work_order_id] = ChannelStatus.ARCHIVED
        logger.info("channel %s archived", work_order_id)

    def is_active(self, work_order_id: str) -> bool:
        """Return True if the channel is active (writable)."""
        return (
            self._channel_status.get(work_order_id, ChannelStatus.ACTIVE)
            == ChannelStatus.ACTIVE
        )


# ---------------------------------------------------------------------------
# Message persistence (Phase 0: in-memory stub, Phase 1: PostgreSQL)
# ---------------------------------------------------------------------------

class RealtimeMessagePersistence:
    """Persist chat messages to PostgreSQL for offline delivery and audit.

    Phase 0 implementation uses an in-memory store keyed by work_order_id.
    Each method documents the expected PostgreSQL behaviour for Phase 1.
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri_env = db_uri_env
        # Phase 0: in-memory storage
        # work_order_id -> list[ChatMessage]
        self._store: dict[str, list[ChatMessage]] = defaultdict(list)
        # Track delivery status: (user_id, msg_id) -> bool
        self._delivered: dict[tuple[str, str], bool] = {}

    async def save_message(self, message: ChatMessage) -> None:
        """Save a chat message to the database.

        Phase 0: appends to in-memory list.
        Phase 1 SQL:
            INSERT INTO chat_messages
                (id, work_order_id, sender_id, sender_role, msg_type,
                 content, metadata, delivered, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8)
        """
        self._store[message.work_order_id].append(message)
        logger.debug(
            "persisted message %s to work_order %s",
            message.msg_id, message.work_order_id,
        )

    async def mark_delivered(self, user_id: str, msg_id: str) -> None:
        """Mark a message as delivered to a specific user.

        Phase 1 SQL:
            UPDATE chat_messages SET delivered = TRUE
            WHERE id = $1
        """
        self._delivered[(user_id, msg_id)] = True

    async def get_undelivered(
        self, user_id: str, work_order_id: str, since: str
    ) -> list[ChatMessage]:
        """Get messages the user hasn't seen since their last disconnect.

        Returns messages in the channel that were created after ``since``
        (ISO-8601) and not yet delivered to ``user_id``.

        Phase 1 SQL:
            SELECT * FROM chat_messages
            WHERE work_order_id = $1
              AND sender_id != $2
              AND created_at > $3
              AND delivered = FALSE
            ORDER BY created_at ASC
        """
        messages = self._store.get(work_order_id, [])
        result: list[ChatMessage] = []

        for msg in messages:
            # Skip messages sent by the requesting user
            if msg.sender_id == user_id:
                continue
            # Skip messages before the since timestamp
            if msg.timestamp <= since:
                continue
            # Skip already-delivered messages
            if self._delivered.get((user_id, msg.msg_id), False):
                continue
            result.append(msg)

        return result

    async def get_history(
        self,
        work_order_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[ChatMessage]:
        """Get paginated message history for a work order.

        Returns up to ``limit`` messages ordered oldest-first.  When
        ``before`` is provided (ISO-8601 timestamp), only messages created
        before that timestamp are returned (cursor-based pagination).

        Phase 1 SQL:
            SELECT * FROM chat_messages
            WHERE work_order_id = $1
              AND ($2::timestamptz IS NULL OR created_at < $2)
            ORDER BY created_at DESC
            LIMIT $3
        Then reverse the result to return oldest-first order.
        """
        messages = self._store.get(work_order_id, [])

        if before is not None:
            messages = [m for m in messages if m.timestamp < before]

        # Take the last `limit` messages (most recent), then return oldest-first
        page = messages[-limit:]
        return list(page)


# ---------------------------------------------------------------------------
# Rate limiter (per-user, sliding window)
# ---------------------------------------------------------------------------

class _SlidingWindowRateLimiter:
    """Simple in-memory sliding-window rate limiter.

    Tracks timestamps of recent actions per key and rejects when the
    count within the window exceeds the limit.
    """

    def __init__(self, max_actions: int, window_seconds: int) -> None:
        self._max_actions = max_actions
        self._window_seconds = window_seconds
        # key -> list of timestamps (float, UTC epoch)
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        """Return True if the action is allowed, False if rate-limited."""
        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - self._window_seconds

        bucket = self._buckets[key]
        # Prune expired entries
        self._buckets[key] = [t for t in bucket if t > cutoff]
        bucket = self._buckets[key]

        if len(bucket) >= self._max_actions:
            return False

        bucket.append(now)
        return True


# ---------------------------------------------------------------------------
# Facade: ties channel manager, persistence, and rate limiting together
# ---------------------------------------------------------------------------

class RealtimeMessagingService:
    """Top-level facade for the real-time messaging subsystem.

    Coordinates channel management, message persistence, and rate limiting
    into a single entry point consumed by the WebSocket endpoint handler.

    Usage (in a FastAPI WebSocket route)::

        service = RealtimeMessagingService()

        @app.websocket("/ws/chat/{work_order_id}")
        async def ws_chat(websocket: WebSocket, work_order_id: str):
            user = authenticate(websocket)
            await service.handle_connect(work_order_id, websocket, user.id, user.role)
            try:
                while True:
                    raw = await websocket.receive_text()
                    await service.handle_message(work_order_id, user.id, user.role, raw)
            except WebSocketDisconnect:
                await service.handle_disconnect(work_order_id, websocket)
    """

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
    ) -> None:
        self.channels = RealtimeChannelManager()
        self.persistence = RealtimeMessagePersistence()
        self._rate_limiter = _SlidingWindowRateLimiter(
            max_actions=rate_limit_per_minute, window_seconds=60
        )

    async def handle_connect(
        self,
        work_order_id: str,
        websocket: Any,
        user_id: str,
        role: str,
    ) -> None:
        """Handle a new WebSocket connection.

        Subscribes the user to the channel and delivers any undelivered
        messages from the persistence layer.
        """
        await self.channels.subscribe(work_order_id, websocket, user_id, role)

        # Deliver undelivered messages from persistence
        # Use epoch-zero as fallback "since" to get all pending messages
        undelivered = await self.persistence.get_undelivered(
            user_id, work_order_id, since="1970-01-01T00:00:00+00:00"
        )
        for msg in undelivered:
            try:
                await websocket.send_text(msg.to_json())
                await self.persistence.mark_delivered(user_id, msg.msg_id)
            except Exception:
                logger.exception(
                    "failed to deliver offline message %s to user %s",
                    msg.msg_id, user_id,
                )
                break

    async def handle_message(
        self,
        work_order_id: str,
        user_id: str,
        role: str,
        raw_payload: str,
    ) -> ChatMessage | None:
        """Handle an incoming WebSocket message from a client.

        Validates the payload, applies rate limiting, persists, and
        broadcasts.  Returns the constructed ChatMessage on success, or
        None if the message was rejected.
        """
        # Rate limit check
        if not self._rate_limiter.allow(user_id):
            logger.warning("rate limit exceeded for user %s", user_id)
            return None

        # Parse payload
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("invalid JSON from user %s: %s", user_id, raw_payload[:200])
            return None

        raw_type = data.get("msg_type", "")
        content = data.get("content", "")

        # Validate msg_type
        try:
            msg_type = ChatMessageType(raw_type)
        except ValueError:
            logger.warning("invalid msg_type '%s' from user %s", raw_type, user_id)
            return None

        # Users cannot send system notifications
        if msg_type == ChatMessageType.SYSTEM:
            logger.warning("user %s attempted to send system_notification", user_id)
            return None

        # Validate content length
        max_len = 1024 if msg_type in (ChatMessageType.IMAGE, ChatMessageType.LOCATION) else 4096
        if len(content) > max_len:
            logger.warning(
                "content too long (%d chars) from user %s", len(content), user_id
            )
            return None

        # Channel must be active
        if not self.channels.is_active(work_order_id):
            logger.warning(
                "user %s tried to send to archived channel %s",
                user_id, work_order_id,
            )
            return None

        # Build message
        message = ChatMessage(
            work_order_id=work_order_id,
            sender_id=user_id,
            sender_role=role,
            msg_type=msg_type,
            content=content,
            metadata=data.get("metadata", {}),
        )

        # Persist then broadcast
        await self.persistence.save_message(message)
        await self.channels.broadcast(message)

        # TODO Phase 2: trigger LINE push notification for offline participants

        return message

    async def handle_disconnect(
        self, work_order_id: str, websocket: Any
    ) -> None:
        """Handle a WebSocket disconnection."""
        await self.channels.unsubscribe(work_order_id, websocket)
