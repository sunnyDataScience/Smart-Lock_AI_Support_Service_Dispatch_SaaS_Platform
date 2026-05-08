"""SMS channel stub adapter (V1.5+).

Always reports unavailable — replace ``send`` body with vendor SDK call once
SMS provider is procured (candidates: Twilio, AWS SNS, 國內供應商). The
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


class SmsStubAdapter(ChannelAdapter):
    """Placeholder SMS adapter — V1.5+ swap target."""

    channel_type = ChannelType.SMS

    def is_available(self) -> bool:
        # No vendor wired up yet → never advertise as available.
        return False

    async def send(self, notification: Notification) -> DeliveryResult:
        log.warning(
            "sms_provider_not_configured",
            user_id=notification.user_id,
            reason="V1.5+: pending vendor procurement (Twilio / AWS SNS / 國內)",
        )
        return DeliveryResult(
            success=False,
            channel=ChannelType.SMS,
            error="SMS provider not configured (V1.5+)",
        )
