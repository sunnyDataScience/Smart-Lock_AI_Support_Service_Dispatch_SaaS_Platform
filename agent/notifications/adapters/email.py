"""Email channel stub adapter (V1.5+).

Always reports unavailable — replace ``send`` body with vendor SDK call once
Email provider is procured (candidates: AWS SES, SendGrid). The
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


class EmailStubAdapter(ChannelAdapter):
    """Placeholder Email adapter — V1.5+ swap target."""

    channel_type = ChannelType.EMAIL

    def is_available(self) -> bool:
        return False

    async def send(self, notification: Notification) -> DeliveryResult:
        log.warning(
            "email_provider_not_configured",
            user_id=notification.user_id,
            reason="V1.5+: pending vendor procurement (AWS SES / SendGrid)",
        )
        return DeliveryResult(
            success=False,
            channel=ChannelType.EMAIL,
            error="Email provider not configured (V1.5+)",
        )
