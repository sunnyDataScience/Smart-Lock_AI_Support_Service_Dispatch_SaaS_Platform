"""多模態訊息處理模組 — passthrough 架構。

流程: LINE 媒體下載 → 本地存檔 → 回傳檔案路徑與 metadata
由 app.py startup 呼叫 init()，媒體訊息呼叫 download_and_store_media()。
Agent 直接接收原始媒體（圖片/音訊/影片）進行多模態推理。
"""

import asyncio

from harness.media_storage import get_media_storage, BaseMediaStorage

from core.logging_config import get_logger

log = get_logger(__name__)

# LINE 經常回傳 application/octet-stream，直接根據訊息類型硬編碼 MIME type
_MIME_BY_MEDIA_TYPE = {
    "image": "image/jpeg",
    "audio": "audio/m4a",
    "video": "video/mp4",
}

# 模組層級狀態（由 init() 初始化）
_config: dict = {}
_line_access_token: str | None = None
_media_storage: BaseMediaStorage | None = None


async def init(config: dict, line_access_token: str):
    """初始化多模態處理模組。由 app.py startup 呼叫。"""
    global _config, _line_access_token, _media_storage
    _config = config

    if not config.get("enabled", False):
        log.info("multimodal_disabled")
        return

    _line_access_token = line_access_token

    # 初始化媒體存儲
    storage_config = config.get("storage", {"type": "local"})
    _media_storage = await get_media_storage(storage_config)

    log.info("multimodal_enabled", mode="passthrough")


def is_enabled() -> bool:
    """檢查多模態處理是否啟用。"""
    return _config.get("enabled", False) and _line_access_token is not None


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


async def download_and_store_media(
    message_id: str, media_type: str, user_id: str
) -> dict:
    """下載媒體、存檔、回傳 metadata（不做內容描述）。

    Returns:
        {"type": "media", "file_path": str, "mime_type": str, "label": str}

    Raises:
        Exception: 下載或存檔失敗時拋出。
    """
    media_label = {"image": "圖片", "audio": "音檔", "video": "影片"}.get(
        media_type, "媒體"
    )

    # 1. 下載媒體
    media_bytes, raw_content_type = await download_media(message_id)
    # LINE 常回傳 application/octet-stream，直接用 media_type 決定 MIME
    content_type = _MIME_BY_MEDIA_TYPE.get(media_type, raw_content_type)
    log.info(
        "multimodal_downloaded",
        media_type=media_type,
        bytes=len(media_bytes),
        mime=content_type,
    )

    # 2. 檢查檔案大小
    max_size = _config.get("max_file_size_mb", 10) * 1024 * 1024
    if len(media_bytes) > max_size:
        max_mb = _config.get("max_file_size_mb", 10)
        raise ValueError(
            f"檔案過大 ({len(media_bytes)} bytes > {max_mb}MB)，無法處理"
        )

    # 3. 存檔
    file_path = ""
    if _media_storage:
        file_path = await _media_storage.save(
            user_id, message_id, media_type, media_bytes, content_type
        )
        log.info("multimodal_stored", file_path=file_path)

    return {
        "type": "media",
        "file_path": file_path,
        "mime_type": content_type,
        "media_bytes": media_bytes,
        "label": media_label,
    }


async def close():
    """清理資源。由 app.py shutdown 呼叫。"""
    if _media_storage:
        await _media_storage.close()
