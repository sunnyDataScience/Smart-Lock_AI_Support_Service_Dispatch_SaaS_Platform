"""factory_boy 工廠 — 替代 hardcoded fixture，讓 schema migration 自動跟著走。

對應 docs/02-design/E7x--test-plan-and-readiness.md §6.2 "Factories over fixtures"。

設計原則：
- 工廠輸出 dict（不直寫 DB）；測試自行決定要 INSERT 還是當作 in-memory 資料
- 對齊 SQL/seeds/*.sql 種子資料形狀，PK / FK / enum 值與 prod schema 一致
- 不依賴 LLM / 外部服務生成 fake 資料；用 deterministic Faker.seed()

公開 API：

    from tests.factories import (
        TenantFactory, TechnicianFactory,
        ProblemCardFactory, WorkOrderFactory,
    )

    # 單筆
    wo = WorkOrderFactory()
    # 批次
    techs = TechnicianFactory.create_batch(5)
    # 客製欄位
    wo = WorkOrderFactory(status="in_progress", priority="high")
"""

from __future__ import annotations

from .problemcard import ProblemCardFactory
from .technician import TechnicianFactory
from .tenant import TenantFactory
from .workorder import WorkOrderFactory

__all__ = [
    "ProblemCardFactory",
    "TechnicianFactory",
    "TenantFactory",
    "WorkOrderFactory",
]
