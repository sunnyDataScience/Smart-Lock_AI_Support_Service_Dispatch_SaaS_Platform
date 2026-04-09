"""多模態訊息前處理模組。

流程: LINE 媒體下載 → 本地存檔 → Gemini Flash-Lite 提取文字描述
由 app.py startup 呼叫 init()，非文字訊息呼叫 process_media_message()。
"""

import os
import asyncio

from core.media_storage import get_media_storage, BaseMediaStorage

# 模組層級狀態（由 init() 初始化）
_config: dict = {}
_genai_client = None
_line_access_token: str | None = None
_media_storage: BaseMediaStorage | None = None


async def init(config: dict, line_access_token: str):
    """初始化多模態處理模組。由 app.py startup 呼叫。"""
    global _config, _genai_client, _line_access_token, _media_storage
    _config = config

    if not config.get("enabled", False):
        print("[Multimodal] 多模態處理已停用 (enabled = false)")
        return

    _line_access_token = line_access_token

    # 初始化 Google GenAI Client
    from google import genai

    api_key = os.getenv(config.get("api_key_env", "GEMINI_API_KEY"))
    if not api_key:
        raise ValueError(
            f"缺少金鑰！請在 .env 檔案中設定 {config.get('api_key_env', 'GEMINI_API_KEY')}"
        )
    _genai_client = genai.Client(api_key=api_key)

    # 初始化媒體存儲
    storage_config = config.get("storage", {"type": "local"})
    _media_storage = await get_media_storage(storage_config)

    model_name = config.get("model_name", "gemini-2.5-flash-lite")
    print(f"[Multimodal] 已啟用，模型: {model_name}")


def is_enabled() -> bool:
    """檢查多模態處理是否啟用且已初始化。"""
    return _config.get("enabled", False) and _genai_client is not None


def get_sticker_reply() -> str:
    """取得貼圖的友善回覆文字。"""
    return _config.get(
        "sticker_reply", "收到您的貼圖了！請問有什麼關於電子鎖的問題我可以幫忙的嗎？"
    )


async def download_media(message_id: str) -> tuple[bytes, str]:
    """從 LINE 下載媒體內容。

    Returns:
        (二進位資料, content_type)
    """
    from linebot.v3.messaging import (
        AsyncApiClient,
        AsyncMessagingApiBlob,
        Configuration,
    )

    timeout = _config.get("download_timeout", 10)

    async with AsyncApiClient(
        Configuration(access_token=_line_access_token)
    ) as api_client:
        blob_api = AsyncMessagingApiBlob(api_client)
        response = await asyncio.wait_for(
            blob_api.get_message_content(message_id),
            timeout=timeout,
        )
        content_type = getattr(response, "content_type", None) or "application/octet-stream"
        if isinstance(response, bytes):
            data = response
        elif hasattr(response, "read"):
            data = await response.read() if asyncio.iscoroutinefunction(response.read) else response.read()
        else:
            data = bytes(response)

        return data, content_type


async def describe_media(
    media_bytes: bytes, content_type: str, media_type: str
) -> str:
    """呼叫 Gemini Flash-Lite 提取媒體的文字描述。"""
    from google.genai import types

    prompt_key = f"{media_type}_prompt"
    prompt = _config.get(prompt_key, f"請描述這個{media_type}的內容。用繁體中文簡潔描述。")
    timeout = _config.get("preprocessing_timeout", 30)

    response = await asyncio.wait_for(
        _genai_client.aio.models.generate_content(
            model=_config.get("model_name", "gemini-2.5-flash-lite"),
            contents=types.Content(
                parts=[
                    types.Part.from_bytes(data=media_bytes, mime_type=content_type),
                    types.Part.from_text(text=prompt),
                ]
            ),
            config=types.GenerateContentConfig(
                temperature=_config.get("temperature", 0.2),
            ),
        ),
        timeout=timeout,
    )
    return response.text


async def process_media_message(
    message_id: str, media_type: str, user_id: str
) -> str:
    """完整多模態處理 pipeline：下載 → 存檔 → 描述。

    失敗時回傳 fallback_text，不會拋出例外。
    """
    media_label = {"image": "圖片", "audio": "音檔", "video": "影片"}.get(
        media_type, "媒體"
    )
    try:
        # 1. 下載媒體
        media_bytes, content_type = await download_media(message_id)
        print(
            f"[Multimodal] 已下載 {media_type}: {len(media_bytes)} bytes, "
            f"type={content_type}"
        )

        # 2. 檢查檔案大小
        max_size = _config.get("max_file_size_mb", 20) * 1024 * 1024
        if len(media_bytes) > max_size:
            print(f"[Multimodal] 檔案過大 ({len(media_bytes)} bytes)，略過處理")
            return _config.get("fallback_text", "抱歉，我無法辨識您傳送的{media_type}。").format(
                media_type=media_label
            )

        # 3. 存檔（與描述並行）
        save_task = None
        if _media_storage:
            save_task = asyncio.create_task(
                _media_storage.save(
                    user_id, message_id, media_type, media_bytes, content_type
                )
            )

        # 4. Flash-Lite 描述
        description = await describe_media(media_bytes, content_type, media_type)

        # 5. 等待存檔完成
        if save_task:
            file_path = await save_task
            print(f"[Multimodal] 媒體已存儲: {file_path}")

        return description

    except Exception as e:
        print(f"[Multimodal Error] {media_type} 處理失敗 (user={user_id}): {e}")
        return _config.get("fallback_text", "抱歉，我無法辨識您傳送的{media_type}。").format(
            media_type=media_label
        )


async def close():
    """清理資源。由 app.py shutdown 呼叫。"""
    if _media_storage:
        await _media_storage.close()
