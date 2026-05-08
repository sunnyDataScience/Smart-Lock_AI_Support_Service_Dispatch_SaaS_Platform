"""Register all default channel adapters at app startup.

Called once from ``agent/app.py`` during the FastAPI ``startup`` event so the
registry is populated before any harness layer attempts to route a
notification.

Adding a new provider in V1.5+ is a one-line change here (replace stub
builder with the real adapter), no caller refactor required.
"""
from __future__ import annotations

from core.logging_config import get_logger
from notifications.adapters.email import EmailStubAdapter
from notifications.adapters.fcm import FcmStubAdapter
from notifications.adapters.line import LineChannelAdapter
from notifications.adapters.sms import SmsStubAdapter
from notifications.base import ChannelType
from notifications.registry import register_channel

log = get_logger(__name__)


def register_default_channels() -> None:
    """Register the V1.0 default channel adapters.

    Idempotent — re-registering replaces existing entries (this is the
    deliberate hook V1.5 will use to swap stub adapters for real ones).
    """
    register_channel(ChannelType.LINE, lambda: LineChannelAdapter())
    register_channel(ChannelType.SMS, lambda: SmsStubAdapter())
    register_channel(ChannelType.EMAIL, lambda: EmailStubAdapter())
    register_channel(ChannelType.FCM, lambda: FcmStubAdapter())
    log.info(
        "notification_channels_registered",
        channels=[c.value for c in ChannelType if c != ChannelType.WEB_PUSH],
    )
