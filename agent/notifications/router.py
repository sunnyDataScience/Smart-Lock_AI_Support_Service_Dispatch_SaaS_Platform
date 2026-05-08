"""Notification router — selects channel based on user prefs + availability.

Algorithm
---------
1. Pick a primary channel:
   - If ``user_prefs["preferred_channel"]`` is a valid ``ChannelType`` → use it
   - Else use ``notification.channel`` (caller hint)
   - Else fall back to ``self._default`` (config'd default, V1.0 = LINE)
2. Try sending. If success → return as-is.
3. Walk ``fallback_chain`` (skipping the primary). First success wins; mark
   ``fallback_used=True`` on the result so audit can flag SLA degradation.
4. If everything fails → return the **last** ``DeliveryResult`` (with
   ``success=False`` and the most-recent error). Caller decides escalation.

The router never raises — it always returns a ``DeliveryResult``. Vendor
exceptions are caught at the adapter boundary; only programmer errors (e.g.
missing registry entry, bad config) propagate as ``ValueError``.
"""
from __future__ import annotations

from dataclasses import replace

from core.logging_config import get_logger
from notifications.base import (
    ChannelType,
    DeliveryResult,
    Notification,
)
from notifications.registry import get_adapter

log = get_logger(__name__)


class NotificationRouter:
    """Routes notifications to the right adapter with fallback support.

    Stateless apart from the configured default channel. Safe to construct
    once at startup and share across the app.
    """

    def __init__(self, default_channel: ChannelType = ChannelType.LINE) -> None:
        self._default = default_channel

    async def route(
        self,
        notification: Notification,
        *,
        user_prefs: dict | None = None,
        fallback_chain: list[ChannelType] | None = None,
    ) -> DeliveryResult:
        """Route to the user's preferred channel, fall back on failure."""
        primary = self._select_primary(notification, user_prefs)
        primary_notif = (
            notification
            if notification.channel == primary
            else replace(notification, channel=primary)
        )
        result = await self._try_send(primary_notif, primary)
        if result.success:
            return result

        last_result = result
        for fb in fallback_chain or []:
            if fb == primary:
                continue
            fb_notif = replace(notification, channel=fb)
            fb_result = await self._try_send(fb_notif, fb)
            if fb_result.success:
                return replace(fb_result, fallback_used=True)
            last_result = fb_result

        log.warning(
            "notification_all_channels_failed",
            user_id=notification.user_id,
            primary=primary.value,
            fallback_chain=[c.value for c in (fallback_chain or [])],
            last_error=last_result.error,
        )
        return last_result

    def _select_primary(
        self, n: Notification, prefs: dict | None
    ) -> ChannelType:
        """Pick primary channel: user pref > notification hint > default."""
        if prefs and "preferred_channel" in prefs:
            try:
                return ChannelType(prefs["preferred_channel"])
            except ValueError:
                log.warning(
                    "invalid_preferred_channel",
                    value=prefs["preferred_channel"],
                    user_id=n.user_id,
                )
        if n.channel:
            return n.channel
        return self._default

    async def _try_send(
        self, n: Notification, ct: ChannelType
    ) -> DeliveryResult:
        """Attempt delivery; converts adapter lookup/runtime errors to result.

        Catches ``ValueError`` (no adapter registered), ``RuntimeError`` (vendor
        SDK level) and ``ConnectionError`` (network). Genuine programmer
        errors (TypeError, AttributeError) still propagate so we surface them
        in tests / CI rather than silently swallow.
        """
        try:
            adapter = get_adapter(ct)
        except ValueError as e:
            return DeliveryResult(success=False, channel=ct, error=str(e))

        if not adapter.is_available():
            return DeliveryResult(
                success=False,
                channel=ct,
                error=f"adapter unavailable: {ct.value}",
            )

        try:
            return await adapter.send(n)
        except (RuntimeError, ConnectionError, TimeoutError) as e:
            log.warning(
                "channel_send_failed",
                channel=ct.value,
                error=str(e),
                user_id=n.user_id,
            )
            return DeliveryResult(success=False, channel=ct, error=str(e))
