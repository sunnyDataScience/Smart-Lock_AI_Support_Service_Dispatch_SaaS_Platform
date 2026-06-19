"""CR-0046 Q-11/Q-12 假資料測試（業主「先生成假資料，確認後再替換」）。

component（需 migration 056）：
- Q-11：報價核准門檻讀 discount_policy config（de-hardcode）。
- Q-12：company_profile config 含公司抬頭/電話/保固/取消/追加價條款（範例待業主確認）。
"""

from __future__ import annotations

import pytest

import core.db as db_module
from services import config_m18_service, quote_engine_service

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_approval_threshold_from_config():
    """Q-11：核准門檻讀 discount_policy（mock 10000）。"""
    assert await db_module._ensure_conn()
    assert await quote_engine_service._approval_threshold() == 10000.0


@pytest.mark.asyncio
async def test_company_profile_config_seeded():
    """Q-12：公司文案 config 齊全且標 mock（範例待業主確認）。"""
    assert await db_module._ensure_conn()
    c = await config_m18_service.read_global_value(namespace="company_profile")
    assert c is not None
    assert c["is_mock"] is True
    assert "範例" in c["company_name"]          # 明確標記範例，便於業主辨識替換
    assert c["customer_service_phone"]
    assert c["warranty_text"]
    assert c["cancellation_clause"]
    assert c["surcharge_clause"]


@pytest.mark.asyncio
async def test_discount_policy_config_seeded():
    """Q-11：折扣權限 config 含客服折扣上限。"""
    assert await db_module._ensure_conn()
    d = await config_m18_service.read_global_value(namespace="discount_policy")
    assert d is not None
    assert d["approval_threshold"] == 10000
    assert d["cs_max_discount_pct"] == 10
    assert d["is_mock"] is True
