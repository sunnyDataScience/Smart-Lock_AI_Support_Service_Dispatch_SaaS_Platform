"""CR-0060 技師品牌授權測試（BR-M07-01；skill matrix + brand auth 資料模型）。"""
from __future__ import annotations
import pytest
import core.db as db_module
from services import dispatch_service as ds

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_brand_authorized_ids_and_expiry():
    assert await db_module._ensure_conn()
    auth = await ds._brand_authorized_ids("Yale")
    assert auth is not None and len(auth) >= 1   # seed 授權 active 技師
    # 2026-07-31（TC-DISPATCH-06 fail-closed 修正）：本行原本斷言未知品牌回 None
    # 「保守不過濾」——那正是被整合測試計畫判為不合規的 fail-open。改為回空集合
    # ＝誰都不符 ＝ 下游自然 fail-closed。None 現在只保留給「根本沒有 brand 可判」。
    assert await ds._brand_authorized_ids("NoSuchBrand_zzz999") == set()
    # 認證過期 → 該技師排除
    tid = next(iter(auth))
    await db_module._conn.execute(
        "UPDATE technician_brand_authorization SET cert_expires_at=CURRENT_DATE - 1 "
        "WHERE technician_id=%s::uuid AND brand='Yale'", (tid,))
    try:
        auth2 = await ds._brand_authorized_ids("Yale")
        assert tid not in (auth2 or set())       # 過期認證不算授權
    finally:
        await db_module._conn.execute(
            "UPDATE technician_brand_authorization SET cert_expires_at=NULL "
            "WHERE technician_id=%s::uuid AND brand='Yale'", (tid,))


@pytest.mark.asyncio
async def test_skill_matrix_seeded():
    assert await db_module._ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT count(*) FROM technician_skill WHERE skill_code='electronic_lock'")
    assert (await cur.fetchone())[0] >= 1
