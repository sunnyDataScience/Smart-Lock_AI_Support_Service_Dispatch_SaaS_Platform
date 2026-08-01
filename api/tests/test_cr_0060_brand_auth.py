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
    # CR-0197 D1(c)（業主 2026-08-01 裁決）：無授權資料的行為現在**由 M18 開關決定**
    #   dispatch_policy.brand_auth_enforce = false（預設）→ None（不阻擋，即本行）
    #                                      = true         → set()（fail-closed）
    # 本檔釘「開關未啟用時的預設行為」；fail-closed 那一側由
    # test_sc13_19_findings.py 以 monkeypatch 開啟開關後驗證。
    assert await ds._brand_authorized_ids("NoSuchBrand_zzz999") is None
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
