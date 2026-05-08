"""FCM channel stub adapter (V2.0+).

Always reports unavailable — replace ``send`` body with Firebase Cloud
Messaging SDK call once 技師端 native app ships (V2.0 / 2027 Q1, see
``docs/02-design/specs/notification-channel-strategy.md`` §2). The
``ChannelAdapter`` contract guarantees zero refactor at call sites.
"""
from __future__ import annotations

from core.logging_config import get_logger
from notifications.base import (
    ChannelAdapter,
    ChannelType,
    DeliveryResult,
    Notification,
)

log = get_logger(__name__)


class FcmStubAdapter(ChannelAdapter):
    """Placeholder FCM adapter — V2.0+ swap target."""

    channel_type = ChannelType.FCM

    def is_available(self) -> bool:
        return False

    async def send(self, notification: Notification) -> DeliveryResult:
        log.warning(
            "fcm_provider_not_configured",
            user_id=notification.user_id,
            reason="V2.0+: pending native app + Firebase project",
        )
        return DeliveryResult(
            success=False,
            channel=ChannelType.FCM,
            error="FCM provider not configured (V2.0+)",
        )
