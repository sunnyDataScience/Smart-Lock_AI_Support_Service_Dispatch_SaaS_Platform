"""CR-0114 R4:品牌讀共用師傅庫(標示授權 + mirror-on-demand)。

單庫 fallback 模式(pytest 現況):tech conn = 主連線,mirror 為 no-op。
驗證:
  - ensure_technician_projection 單庫下 no-op、不炸。
  - _authorized_brands_map 回鎖品牌授權(用 seed Yale 授權資料)。
  - technician_service.list 附 authorized_brands 欄位。
  - auto_match 維持只選已授權(裁決 7:_brand_authorized_ids 語義)。
標示語義(list_dispatch_candidates 過濾→標示)的端到端由 compose Playwright
候選卡 badge 覆蓋。
"""

from __future__ import annotations

import pytest

import core.db as db_module
from core.tech_mirror import ensure_technician_projection
from services import dispatch_service as ds
from services import technician_service as ts

pytestmark = pytest.mark.component

TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_ensure_projection_noop_single_db():
    """單庫 fallback:ensure_technician_projection 對任意 id 均 no-op、不 raise。"""
    assert not db_module.tech_db_enabled()  # pytest 未設 TECH_POSTGRES_URI
    await ensure_technician_projection("00000000-0000-0000-0000-000000000abc")


@pytest.mark.asyncio
async def test_authorized_brands_map_returns_lock_brands():
    """_authorized_brands_map 回已授權且未過期的鎖品牌(seed Yale 授權)。"""
    conn = await db_module.require_tech_conn()
    auth = await ds._brand_authorized_ids("Yale")
    assert auth, "seed 應有 Yale 授權技師"
    tid = next(iter(auth))
    brand_map = await ts._authorized_brands_map(conn, [tid])
    assert "Yale" in brand_map.get(tid, []), "已授權技師的 authorized_brands 應含 Yale"


@pytest.mark.asyncio
async def test_list_technicians_service_includes_authorized_brands():
    """service 層 list_technicians 每筆附 authorized_brands 陣列(裁決 6)。

    註:GET /tenants/{tid}/technicians 端點以 Technician schema 序列化,會濾掉此
    附加欄位 —— 端點層曝露(供前端 chips)屬後續前端輪範疇;此處驗證後端運算
    正確(dispatch 候選 badge 走 dispatch_service raw dict,不受此 schema 影響)。
    """
    res = await ts.list_technicians(tenant_id=TENANT, cursor=None, limit=5)
    items = res["items"]
    assert items, "seed 應有技師"
    for it in items:
        assert "authorized_brands" in it
        assert isinstance(it["authorized_brands"], list)


@pytest.mark.asyncio
async def test_auto_match_still_filters_unauthorized():
    """裁決 7:auto_match 只選已授權 —— _brand_authorized_ids 有值時為過濾集合。"""
    auth = await ds._brand_authorized_ids("Yale")
    assert auth is not None and len(auth) >= 1
    # CR-0197 D1(c)：無授權資料的行為由 M18 開關 dispatch_policy.brand_auth_enforce
    # 決定；本行釘預設（off）＝ None ＝ 沿用 CR-0114 R4 語意。開啟後的 fail-closed
    # 由 test_sc13_19_findings.py 驗。
    assert await ds._brand_authorized_ids("NoSuchBrand_zzz") is None
