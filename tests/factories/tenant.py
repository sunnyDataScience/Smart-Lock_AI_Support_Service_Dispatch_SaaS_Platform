"""Tenant 工廠 — 對齊 SQL/seeds/_admin_user.sql 的 default tenant。

實際 dev DB 只有一個 tenant：00000000-0000-0000-0000-000000000001
故 factory 預設輸出該 ID；要建多 tenant 場景才覆寫。
"""

from __future__ import annotations

import uuid
from typing import Any

import factory

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class TenantFactory(factory.DictFactory):
    """輸出 tenant dict（不直寫 DB；測試用 INSERT 自管）。"""

    id = DEFAULT_TENANT_ID
    name = factory.Faker("company", locale="zh_TW")
    region = factory.Faker("random_element", elements=["北部", "中部", "南部", "東部"])
    status = "active"

    @classmethod
    def random_id(cls, **kwargs: Any) -> dict[str, Any]:
        """產出新 tenant_id（多 tenant 測試用）。"""
        return cls(id=str(uuid.uuid4()), **kwargs)
