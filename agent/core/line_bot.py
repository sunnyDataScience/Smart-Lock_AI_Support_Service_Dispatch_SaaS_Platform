"""LINE Messaging API 封裝（LINE Bot SDK v3）。

由 app.py startup 呼叫 init()，提供 show_loading / send_response。
"""

from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ShowLoadingAnimationRequest,
    ApiException,
)

# 模組層級狀態（由 init() 初始化）
_configuration = None
_config: dict = {}


def init(access_token: str, config: dict):
    """初始化 LINE Messaging API 設定，由 app.py startup 呼叫。

    Args:
        access_token: LINE Channel Access Token
        config: 包含 loading_seconds, push_fallback_prefix 等設定
    """
    global _configuration, _config
    _configuration = Configuration(access_token=access_token)
    _config = config


async def show_loading(user_id: str):
    """顯示 LINE Loading 動畫。"""
    loading_time = _config.get("loading_seconds", 20)
    async with AsyncApiClient(_configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        try:
            await line_bot_api.show_loading_animation(
                ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=loading_time)
            )
        except Exception as e:
            print(f"[Warning] 顯示 Loading 動畫失敗: {e}")


async def send_response(
    user_id: str, reply_token: str, message_text: str,
    max_len: int = 5000, message_objects: list | None = None,
):
    """嘗試 Reply API，失敗則降級 Push API。

    若有 message_objects（LINE Message 物件列表）則優先使用，否則降級為純文字。
    """
    messages = message_objects if message_objects else [TextMessage(text=message_text[:max_len])]

    async with AsyncApiClient(_configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        try:
            await line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages,
                )
            )
        except ApiException:
            fallback_prefix = _config.get("push_fallback_prefix", "")
            push_messages = []
            for msg in messages:
                if isinstance(msg, TextMessage):
                    push_messages.append(TextMessage(text=fallback_prefix + msg.text))
                else:
                    push_messages.append(msg)
            try:
                await line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=push_messages,
                    )
                )
            except ApiException as e2:
                # Flex Message 也失敗 → 降級為純文字
                print(f"[LINE] Flex Message push 失敗，降級純文字: {e2}")
                await line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=fallback_prefix + message_text[:max_len])],
                    )
                )
