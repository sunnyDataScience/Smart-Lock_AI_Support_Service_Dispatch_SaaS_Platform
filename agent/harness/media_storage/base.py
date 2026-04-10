"""媒體存儲抽象基底類別。

未來擴充雲端存儲（GCS / S3）時，只需繼承此類並實作 save()。
"""


class BaseMediaStorage:
    """媒體檔案存儲介面。"""

    async def init(self):
        """初始化存儲（建立目錄、驗證連線等）。"""
        pass

    async def save(
        self,
        user_id: str,
        message_id: str,
        media_type: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """存儲媒體檔案。

        Args:
            user_id: LINE 使用者 ID
            message_id: LINE 訊息 ID
            media_type: 媒體類型 ("image", "audio", "video")
            data: 二進位資料
            content_type: MIME type (e.g. "image/jpeg")

        Returns:
            存取路徑或 URI（本地路徑 / gs://... / s3://...）
        """
        raise NotImplementedError

    async def close(self):
        """清理資源。"""
        pass
