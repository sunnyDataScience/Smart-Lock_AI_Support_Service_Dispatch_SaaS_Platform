"""Notification channel abstraction layer.

V1.0 一律走 LINE（PM 拍板 Q8=A，see
``docs/02-design/specs/notification-channel-strategy.md``）。
本模組為 V1.5+ 多 channel（SMS / Email / FCM）做架構準備：

- channel-agnostic ``Notification`` dataclass
- ``ChannelAdapter`` ABC interface
- registry-based provider lookup（與 ``memory`` / ``storage`` 一致 pattern）
- ``NotificationRouter`` 依 user preference / channel availability 路由

V1.5 補真實 provider 時，只需新增 adapter（如 ``TwilioSMSAdapter``）並 register
到 registry，**不需動 caller code**。

Layering: 屬 ``agent/`` 子套件，可 import ``core`` / ``notifications``，禁止
import ``harness`` / ``app`` / ``agent`` 模組，避免循環依賴（與
``agent/memory``、``agent/storage`` 一致的分層守則）。
"""
from __future__ import annotations

from notifications.base import (
    ChannelAdapter,
    ChannelType,
    DeliveryResult,
    Notification,
)
from notifications.bootstrap import register_default_channels
from notifications.registry import (
    CHANNEL_REGISTRY,
    get_adapter,
    register_channel,
)
from notifications.router import NotificationRouter

__all__ = [
    "ChannelAdapter",
    "ChannelType",
    "DeliveryResult",
    "Notification",
    "NotificationRouter",
    "CHANNEL_REGISTRY",
    "get_adapter",
    "register_channel",
    "register_default_channels",
]
