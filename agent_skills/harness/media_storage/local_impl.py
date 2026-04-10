"""本地檔案系統媒體存儲實作。

目錄結構: {local_path}/{user_id}/{YYYY-MM-DD}/{message_id}.{ext}
"""

import os
from datetime import datetime

import aiofiles

from .base import BaseMediaStorage

# MIME type → 副檔名對照
_MIME_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "audio/aac": "aac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "video/mp4": "mp4",
    "video/mpeg": "mpeg",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
    "video/3gpp": "3gp",
}


def _content_type_to_ext(content_type: str) -> str:
    """從 MIME type 推斷副檔名，未知類型回傳 'bin'。"""
    base = content_type.split(";")[0].strip().lower()
    return _MIME_EXT_MAP.get(base, "bin")


class LocalMediaStorage(BaseMediaStorage):
    """將媒體檔案存儲到本地檔案系統。"""

    def __init__(self, config: dict):
        self._base_path = config.get("local_path", "./data/media")

    async def init(self):
        os.makedirs(self._base_path, exist_ok=True)
        print(f"[MediaStorage] 本地存儲已初始化: {self._base_path}")

    async def save(
        self,
        user_id: str,
        message_id: str,
        media_type: str,
        data: bytes,
        content_type: str,
    ) -> str:
        date_dir = datetime.now().strftime("%Y-%m-%d")
        user_dir = os.path.join(self._base_path, user_id, date_dir)
        os.makedirs(user_dir, exist_ok=True)

        ext = _content_type_to_ext(content_type)
        file_path = os.path.join(user_dir, f"{message_id}.{ext}")

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)

        return file_path
