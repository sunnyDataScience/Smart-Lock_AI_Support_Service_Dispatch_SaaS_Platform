"""LINE channel adapter.

Wraps the existing ``agent.core.line_bot`` module so callers go through the
``ChannelAdapter`` interface instead of importing ``line_bot`` directly.

Two delivery modes:

- **Reply** (``metadata["reply_token"]`` present): uses
  ``line_bot.send_response`` which itself falls back to push internally if
  the reply token has expired. This is the path used inside webhook
  handlers (Phase Q3 follow-up will migrate orchestrator to here).
- **Push** (no reply token): direct ``PushMessageRequest`` via the LINE
  SDK using the configuration object that ``line_bot.init`` already
  populated at startup. This is the path used by background dispatch /
  status updates / red alerts.

Availability is determined by whether ``line_bot.init`` has been called
(``_configuration`` is non-None). The adapter is cheap to construct.
"""
from __future__ import annotations

from typing import cast

from linebot.v3.messaging import (
    ApiException,
    AsyncApiClient,
    AsyncMessagingApi,
    PushMessageRequest,
    TextMessage,
)

from core import line_bot
from core.logging_config import get_logger
from notifications.base import (
    ChannelAdapter,
    ChannelType,
    DeliveryResult,
    Notification,
)

log = get_logger(__name__)


def _format_text(notification: Notification) -> str:
    """Render notification.title + body into LINE plain text.

    Title is optional — if empty we just emit the body to avoid leading
    newlines in the user's chat.
    """
    if notification.title:
        return f"{notification.title}\n{notification.body}"
    return notification.body


class LineChannelAdapter(ChannelAdapter):
    """Real LINE adapter — uses Reply API if reply_token present, else Push."""

    channel_type = ChannelType.LINE

    def is_available(self) -> bool:
        # ``line_bot.init`` sets ``_configuration``; before init it is None and
        # any send attempt would hit a NoneType inside the SDK.
        return getattr(line_bot, "_configuration", None) is not None

    async def send(self, notification: Notification) -> DeliveryResult:
        if not self.is_available():
            return DeliveryResult(
                success=False,
                channel=ChannelType.LINE,
                error="line_bot not initialized (call line_bot.init at startup)",
            )

        text = _format_text(notification)
        max_len = int(
            getattr(line_bot, "_config", {}).get("max_reply_length", 5000)
        )
        text = text[:max_len]

        reply_token = (notification.metadata or {}).get("reply_token")

        # Reply path: delegate to existing helper which already handles
        # reply→push fallback, max length truncation, and Flex template hand-off.
        if reply_token:
            try:
                await line_bot.send_response(
                    user_id=notification.user_id,
                    reply_token=cast(str, reply_token),
                    message_text=text,
                    max_len=max_len,
                )
                return DeliveryResult(
                    success=True,
                    channel=ChannelType.LINE,
                    provider_msg_id=None,  # LINE Reply API does not return id
                )
            except ApiException as e:
                return DeliveryResult(
                    success=False,
                    channel=ChannelType.LINE,
                    error=f"line_reply_failed: {e}",
                )

        # Push path: direct SDK call using line_bot's already-init'd config.
        return await self._push(notification.user_id, text)

    async def _push(self, user_id: str, text: str) -> DeliveryResult:
        configuration = getattr(line_bot, "_configuration", None)
        if configuration is None:
            return DeliveryResult(
                success=False,
                channel=ChannelType.LINE,
                error="line_bot not initialized",
            )

        async with AsyncApiClient(configuration) as api_client:
            api = AsyncMessagingApi(api_client)
            try:
                await api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=text)],
                    )
                )
                return DeliveryResult(
                    success=True,
                    channel=ChannelType.LINE,
                    provider_msg_id=None,
                )
            except ApiException as e:
                log.warning(
                    "line_push_failed",
                    user_id=user_id,
                    status=getattr(e, "status", None),
                    error=str(e)[:200],
                )
                return DeliveryResult(
                    success=False,
                    channel=ChannelType.LINE,
                    error=f"line_push_failed: {e}",
                )
