"""Technician 工廠 — 對齊 SQL/seeds/technicians.sql。

Schema：tenant_id, user_id, name, phone, email, capabilities (jsonb),
        service_regions (jsonb), rating, completed_orders, status
"""

from __future__ import annotations

import uuid

import factory

from .tenant import DEFAULT_TENANT_ID

TECHNICIAN_BRANDS = ["Yale", "Chatlock", "美樂", "Dormakaba", "Philips"]
TAIWAN_REGIONS = [
    "台北市信義區", "台北市大安區", "新北市板橋區", "新北市新店區",
    "桃園市中壢區", "台中市西屯區", "高雄市三民區",
]


class TechnicianFactory(factory.DictFactory):
    """輸出 technician dict — capabilities / service_regions 為 list（測試端轉 json 入庫）。"""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    tenant_id = DEFAULT_TENANT_ID
    user_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Faker("name", locale="zh_TW")
    phone = factory.Sequence(lambda n: f"09{n % 100:02d}{n:06d}")
    email = factory.LazyAttribute(lambda o: f"tech-{o.id[:8]}@example.com")
    capabilities = factory.Faker(
        "random_elements", elements=TECHNICIAN_BRANDS, length=3, unique=True
    )
    service_regions = factory.Faker(
        "random_elements", elements=TAIWAN_REGIONS, length=2, unique=True
    )
    rating = factory.Faker("pyfloat", min_value=3.5, max_value=5.0, right_digits=1)
    completed_orders = factory.Faker("pyint", min_value=0, max_value=200)
    status = "active"
