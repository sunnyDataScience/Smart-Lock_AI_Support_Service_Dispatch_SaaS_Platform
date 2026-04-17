"""媒體存儲 Registry。

透過 config.toml [multimodal.storage] type 切換實作：
  - "local": 本地檔案系統
  - "gcs": Google Cloud Storage
"""

from .base import BaseMediaStorage
from .local_impl import LocalMediaStorage
from .gcs_impl import GCSMediaStorage

MEDIA_STORAGE_REGISTRY: dict[str, type[BaseMediaStorage]] = {
    "local": LocalMediaStorage,
    "gcs": GCSMediaStorage,
}


async def get_media_storage(config: dict) -> BaseMediaStorage:
    """根據設定建立媒體存儲實例。"""
    storage_type = config.get("type", "local")
    print(f"[*] 初始化媒體存儲模組: 使用 {storage_type} 機制...")

    cls = MEDIA_STORAGE_REGISTRY.get(storage_type)
    if not cls:
        raise ValueError(
            f"不支援的媒體存儲類型: {storage_type}，可用: {', '.join(MEDIA_STORAGE_REGISTRY)}"
        )
    instance = cls(config)
    await instance.init()
    return instance
