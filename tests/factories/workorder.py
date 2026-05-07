"""WorkOrder 工廠 — 對齊 SQL/seeds/work_orders.sql。

Schema 重點欄位：id, problem_card_id, status, priority,
       customer_name, customer_phone, customer_address,
       scheduled_at, technician_id, completed_at,
       estimated_price, created_at, updated_at
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import factory

WO_STATUSES = ["created", "scheduled", "in_progress", "completed", "confirmed", "cancelled"]
WO_PRIORITIES = ["low", "normal", "high", "urgent"]
TAIWAN_LOCATIONS = [
    "台北市信義區忠孝東路100號", "新北市板橋區文化路150號",
    "桃園市中壢區中央路5號", "台中市西屯區市政路80號",
]


class WorkOrderFactory(factory.DictFactory):
    """輸出 work_order dict。"""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    problem_card_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    status = "created"
    priority = "normal"
    customer_name = factory.Faker("name", locale="zh_TW")
    customer_phone = factory.Sequence(lambda n: f"09{n % 100:02d}{n:06d}")
    customer_address = factory.Faker("random_element", elements=TAIWAN_LOCATIONS)
    scheduled_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(hours=2)
    )
    technician_id = None
    completed_at = None
    estimated_price = factory.Faker("pyfloat", min_value=500, max_value=5000, right_digits=0)
