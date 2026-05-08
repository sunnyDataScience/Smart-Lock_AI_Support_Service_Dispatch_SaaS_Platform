"""Channel-agnostic notification primitives + adapter ABC.

Three immutable dataclasses + one abstract base class — keeps the V1.0 surface
tiny while making V1.5+ provider plug-in a single ``register_channel`` call.

Design notes
------------

- ``Notification`` and ``DeliveryResult`` are ``frozen=True`` so callers can not
  mutate them after construction (CLAUDE.md coding-style §不可變性).
- ``metadata`` carries channel-specific payload (e.g. LINE Flex template id,
  SMS sender id, Email subject overrides) — the abstraction stays stable while
  vendors evolve.
- ``ChannelAdapter`` is intentionally minimal: only ``send`` + ``is_available``.
  Vendor-specific concerns (rate-limit accounting, idempotency keys) live
  inside concrete adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelType(str, Enum):
    """Supported notification channel identifiers.

    String-valued enum so ``config.toml`` can store the lower-case name
    (``"line"``) and we can round-trip via ``ChannelType("line")``.

    V1.0 only ``LINE`` has a working adapter; the rest are stubs that log
    "provider not configured" and return a failed ``DeliveryResult`` so the
    router can fall back transparently once V1.5 lights up real vendors.
    """

    LINE = "line"
    SMS = "sms"
    EMAIL = "email"
    FCM = "fcm"
    WEB_PUSH = "web_push"  # 預留 Cloud Run 站內推播 (V2.0+)


@dataclass(frozen=True)
class Notification:
    """Channel-agnostic notification payload.

    Fields
    ------
    user_id:
        Recipient identifier. For LINE this is the LINE user id; for SMS/Email
        adapters it is the platform-side user id which the adapter resolves to
        a phone/email via ``ProfileManager``.
    title / body:
        Display text. Adapters decide how to render: LINE concatenates with
        newline, Email maps to subject/body, SMS uses ``body`` only.
    channel:
        Hint for which channel the caller wants. ``NotificationRouter`` may
        override based on user preferences or availability.
    metadata:
        Channel-specific extras (LINE: ``flex_template_id``, ``quick_reply``;
        Email: ``cc``, ``bcc``, ``html``; SMS: ``sender_id``).
    deep_link:
        Optional URL/URI for click-through (work order detail, refund status).
    priority:
        ``urgent`` / ``normal`` / ``low``. Routing may pick fallback channels
        for ``urgent`` even when primary succeeds.
    """

    user_id: str
    title: str
    body: str
    channel: ChannelType
    metadata: dict[str, Any] = field(default_factory=dict)
    deep_link: str | None = None
    priority: str = "normal"


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of a single ``ChannelAdapter.send`` call.

    ``fallback_used`` is set by the router when the primary channel failed and
    a chain entry succeeded — useful for audit log and SLA reporting.
    """

    success: bool
    channel: ChannelType
    provider_msg_id: str | None = None
    error: str | None = None
    fallback_used: bool = False


class ChannelAdapter(ABC):
    """Interface for channel providers.

    Concrete subclasses set the class attribute :attr:`channel_type` and
    implement :meth:`send` + :meth:`is_available`. They MUST be safe to
    instantiate cheaply (the registry calls the builder per request).
    """

    channel_type: ChannelType  # subclass must set

    @abstractmethod
    async def send(self, notification: Notification) -> DeliveryResult:
        """Send a notification, returning a structured ``DeliveryResult``.

        Implementations MUST NOT raise on ordinary delivery failures —
        translate vendor exceptions into ``DeliveryResult(success=False, ...)``
        so the router can fall back without try/except scaffolding everywhere.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Provider readiness probe.

        Returns ``True`` when the adapter has all credentials/quota it needs to
        attempt a send. The router skips adapters that report ``False`` and
        moves to the next fallback in chain.
        """
