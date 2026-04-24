"""Google Cloud Storage 媒體存儲實作。

目錄結構: gs://{bucket}/media/{user_id}/{YYYY-MM-DD}/{message_id}.{ext}
"""

import os
from datetime import datetime

from .base import BaseMediaStorage
from .local_impl import _content_type_to_ext

try:
    from google.cloud import storage as gcs_storage
except ImportError:
    gcs_storage = None


class GCSMediaStorage(BaseMediaStorage):
    """將媒體檔案存儲到 Google Cloud Storage。"""

    def __init__(self, config: dict):
        self._bucket_name = config.get("gcs_bucket", "")
        self._prefix = config.get("gcs_prefix", "media")
        self._client = None
        self._bucket = None

    async def init(self):
        if gcs_storage is None:
            raise ImportError(
                "google-cloud-storage 未安裝，請執行: pip install google-cloud-storage"
            )
        if not self._bucket_name:
            bucket_env = os.getenv("GCS_MEDIA_BUCKET", "")
            if not bucket_env:
                raise ValueError(
                    "GCS bucket 未設定：請在 config.toml 設定 gcs_bucket 或環境變數 GCS_MEDIA_BUCKET"
                )
            self._bucket_name = bucket_env

        self._client = gcs_storage.Client()
        self._bucket = self._client.bucket(self._bucket_name)
        print(f"[MediaStorage] GCS 存儲已初始化: gs://{self._bucket_name}/{self._prefix}/")

    async def save(
        self,
        user_id: str,
        message_id: str,
        media_type: str,
        data: bytes,
        content_type: str,
    ) -> str:
        date_dir = datetime.now().strftime("%Y-%m-%d")
        ext = _content_type_to_ext(content_type)
        blob_path = f"{self._prefix}/{user_id}/{date_dir}/{message_id}.{ext}"

        blob = self._bucket.blob(blob_path)
        blob.upload_from_string(data, content_type=content_type)

        uri = f"gs://{self._bucket_name}/{blob_path}"
        return uri

    async def close(self):
        if self._client:
            self._client.close()
            self._client = None
