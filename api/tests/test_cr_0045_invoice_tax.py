"""CR-0045 發票稅 de-hardcode 測試（esales Q-07，業主預設台灣 5% 含稅）。

invoice tax 原 hardcode mock 0 → 讀 tax_policy config（migration 055，inclusive 5%）。
含稅語意：客戶含稅總價（amount/total）不變，僅拆出內含稅額（tax，帳務用）。
"""

from __future__ import annotations

import pytest

import core.db as db_module
from services import invoice_service

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_resolve_tax_inclusive_5pct():
    """含稅 5%：gross 800 → amount/total 維持 800（對外不變），tax=800×5/105=38.10。"""
    assert await db_module._ensure_conn()
    amount, tax, total = await invoice_service._resolve_tax(800.0)
    assert amount == 800.0   # 客戶含稅總價不變（API 只露此值）
    assert total == 800.0
    assert tax == 38.10      # 內含稅額（DB-only 帳務）


@pytest.mark.asyncio
async def test_resolve_tax_zero():
    assert await db_module._ensure_conn()
    assert await invoice_service._resolve_tax(0.0) == (0.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_resolve_tax_another_amount():
    """gross 2100 → tax=2100×5/105=100.00。"""
    assert await db_module._ensure_conn()
    amount, tax, total = await invoice_service._resolve_tax(2100.0)
    assert amount == 2100.0
    assert tax == 100.00
