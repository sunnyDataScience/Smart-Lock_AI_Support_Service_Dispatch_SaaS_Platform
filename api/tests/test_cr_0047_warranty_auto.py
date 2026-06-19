"""CR-0047 保固期動態計算測試（派工單 PDF §四 優化；接 warranty_service 引擎）。

- 純函式：_auto_warranty（序號/購買日 → 保固到期 + 保內/保外；錨點 fallback；無錨點不算）
- component（需 migration 057）：update_wo_fields 設購買日 → 自動回填 warranty_status + 到期日；
  手動 warranty_status 優先不被覆蓋。
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

import core.db as db_module
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


# ── 純函式 ──────────────────────────────────────────────────────────────────
def test_auto_warranty_out_of_warranty():
    """2010 購買 + 24 月 → 2012 到期 → 早已過保。"""
    end, status = svc._auto_warranty(None, "2010-01-01", None)
    assert status == "out_warranty"
    assert end == date(2012, 1, 1)


def test_auto_warranty_in_warranty_today():
    """今日購買 + 24 月 → 到期在未來 → 保內（不綁特定年份）。"""
    today = date.today()
    end, status = svc._auto_warranty(None, today.isoformat(), None)
    assert status == "in_warranty"
    assert end > today


def test_auto_warranty_install_fallback():
    """無 purchase_date → 退回 install_date 當錨點。"""
    end, status = svc._auto_warranty(None, None, "2010-01-01")
    assert status == "out_warranty"
    assert end == date(2012, 1, 1)


def test_auto_warranty_no_anchor():
    """無任何日期 → 不自動算。"""
    assert svc._auto_warranty(None, None, None) == (None, None)


# ── component ───────────────────────────────────────────────────────────────
pytest_component = pytest.mark.component


async def _seed_confirmed_pc() -> tuple[str, str]:
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, '測試客', '0912000000', '台北市信義區1號', 'line_user')",
        (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')", (cid, uid, "sess-" + pid[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDM-4109', '維修', 'normal', 'confirmed')", (pid, cid))
    return pid, uid


async def _cleanup(user_id: str, pc_id: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pc_id,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest_component
@pytest.mark.asyncio
async def test_update_fields_auto_fills_warranty():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        out = await svc.update_wo_fields(
            tenant_id=TID, wo_id=wo["id"],
            fields={"serial_number": "SN-1", "purchase_date": "2010-01-01"},
        )
        assert out["warranty_status"] == "out_warranty"      # 自動回填
        # seed PC brand=Yale → brand override 36 月（非預設 24）→ 2010-01-01 + 36mo = 2013-01-01
        assert out["warranty_expiry_date"] == "2013-01-01"   # 證 brand override 端到端生效
    finally:
        await _cleanup(uid, pid)


@pytest_component
@pytest.mark.asyncio
async def test_manual_warranty_status_not_overridden():
    """手動指定 warranty_status 時，自動計算不覆蓋（manual 優先）。"""
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        out = await svc.update_wo_fields(
            tenant_id=TID, wo_id=wo["id"],
            fields={"purchase_date": "2010-01-01", "warranty_status": "not_applicable"},
        )
        assert out["warranty_status"] == "not_applicable"    # 手動優先
    finally:
        await _cleanup(uid, pid)
