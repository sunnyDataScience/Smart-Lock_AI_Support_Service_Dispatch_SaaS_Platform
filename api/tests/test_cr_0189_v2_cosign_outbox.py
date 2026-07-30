"""CR-0189 §8a（業主 2026-07-30 裁決）：v2 co-sign 也走 outbox 發 commission.accrued。

背景與範圍：
  業主裁決只說「v2 補發事件」，但實作時發現 v2 的問題比缺事件更嚴重——CR-0189 在
  legacy `approve_reconciliation` 修掉的兩個缺陷 v2 一個都沒修：非原子、無列鎖、
  且 `saas.settlement` 沒有 UNIQUE(reconciliation_id)。

  outbox 模式的全部意義是「事件與 settlement 同生共死」，掛在非交易路徑上等於沒有
  保證。所以修原子性是加事件的**前置條件**，不是額外範圍。

本檔守四條線：
  1. co-sign 成功後 outbox 有一筆 pending/sent 的 commission.accrued。
  2. settlement 與 outbox 在**同一交易**——交易失敗兩者都不留。
  3. 並發／重送 co-sign 不產生第二筆 settlement（DB UNIQUE 兜底）。
  4. 事件 payload 帶 source 標記，讓消費端與稽核分得出 legacy／v2。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import reconciliation_v2_service as svc

TENANT = "00000000-0000-0000-0000-000000000001"


async def _ensure() -> bool:
    from core.db import _ensure_conn
    return await _ensure_conn()


@pytest.fixture
async def recon():
    """建一張 in_review 的 v2 對帳單（含必要的技師），收尾全清。"""
    if not await _ensure():
        pytest.skip("DB unavailable")

    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE tenant_id = %s::uuid LIMIT 1", (TENANT,))
    trow = await cur.fetchone()
    if not trow:
        pytest.skip("no technician in tenant")
    tech_id = str(trow[0])

    rid = str(uuid.uuid4())
    reviewer = str(uuid.uuid4())
    # 欄位對齊實際 schema：期間是 period_start/period_end 兩欄，沒有 `period`
    #（初版寫 period 導致 fixture 靜默 skip，4 支測試假綠）
    await db_module._conn.execute(
        "INSERT INTO saas.reconciliation "
        "  (id, tenant_id, technician_id, period_start, period_end, status, "
        "   reviewed_by, reviewed_at, technician_payout, total_orders, total_revenue) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::timestamptz, %s::timestamptz, "
        "        'in_review', %s::uuid, NOW(), %s, %s, %s)",
        (rid, TENANT, tech_id, "2026-07-01T00:00:00+00", "2026-07-31T23:59:59+00",
         reviewer, 1234.56, 3, 5000.00),
    )

    yield {"id": rid, "technician_id": tech_id, "reviewer": reviewer}

    await db_module._conn.execute(
        "DELETE FROM commission_event_outbox WHERE reconciliation_id = %s::uuid", (rid,))
    await db_module._conn.execute(
        "DELETE FROM saas.settlement WHERE reconciliation_id = %s::uuid", (rid,))
    await db_module._conn.execute(
        "DELETE FROM saas.reconciliation WHERE id = %s::uuid", (rid,))


async def _outbox_rows(rid: str) -> list[tuple]:
    cur = await db_module._conn.execute(
        "SELECT topic, status, payload, settlement_id FROM commission_event_outbox "
        "WHERE reconciliation_id = %s::uuid", (rid,))
    return await cur.fetchall()


# ── 1 + 4：事件落 outbox 且帶 source ────────────────────────────────────────


async def test_cosign_writes_commission_outbox_row(recon):
    result = await svc.co_sign_reconciliation(
        tenant_id=TENANT, recon_id=recon["id"], co_signer_id=str(uuid.uuid4()),
    )
    rows = await _outbox_rows(recon["id"])
    assert len(rows) == 1, "co-sign 後 outbox 必須恰有一筆（此前 v2 完全不發事件）"
    topic, status, payload, settlement_id = rows[0]
    assert topic == "commission.accrued"
    assert status in ("pending", "sent")
    assert str(settlement_id) == result["settlement"]["id"], \
        "outbox 的 settlement_id 必須指向本次建立的 settlement"
    p = payload if isinstance(payload, dict) else {}
    assert p.get("source") == "reconciliation_v2_co_sign", \
        "payload 要標來源，否則消費端分不出 legacy／v2（兩表分裂未收斂）"
    assert p.get("reconciliation_id") == recon["id"]


# ── 2：同交易（失敗兩者都不留）───────────────────────────────────────────────


async def test_settlement_and_outbox_share_one_transaction(recon, monkeypatch):
    """outbox INSERT 失敗時，settlement 也不可留下。

    這條是 outbox 模式的核心保證。若兩者不同交易，會出現「有 settlement 但沒事件」
    ——技師平台永遠收不到這筆佣金，而帳面上錢已經要付出去。
    """
    real = db_module._conn.execute

    async def boom(sql, params=None, *a, **kw):
        if "INSERT INTO commission_event_outbox" in str(sql):
            raise RuntimeError("injected outbox failure")
        return await real(sql, params, *a, **kw)

    monkeypatch.setattr(db_module._conn, "execute", boom)
    with pytest.raises(RuntimeError):
        await svc.co_sign_reconciliation(
            tenant_id=TENANT, recon_id=recon["id"], co_signer_id=str(uuid.uuid4()),
        )
    monkeypatch.undo()

    cur = await db_module._conn.execute(
        "SELECT count(*) FROM saas.settlement WHERE reconciliation_id = %s::uuid",
        (recon["id"],))
    assert (await cur.fetchone())[0] == 0, "outbox 失敗時 settlement 必須一起 rollback"
    cur = await db_module._conn.execute(
        "SELECT status FROM saas.reconciliation WHERE id = %s::uuid", (recon["id"],))
    assert (await cur.fetchone())[0] == "in_review", "status 也必須 rollback"


# ── 3：重送不重複出款 ────────────────────────────────────────────────────────


async def test_second_cosign_does_not_create_second_settlement(recon):
    """第二次 co-sign 應被狀態機擋（409），且不得出現第二筆 settlement。"""
    await svc.co_sign_reconciliation(
        tenant_id=TENANT, recon_id=recon["id"], co_signer_id=str(uuid.uuid4()),
    )
    with pytest.raises(ApiError) as ei:
        await svc.co_sign_reconciliation(
            tenant_id=TENANT, recon_id=recon["id"], co_signer_id=str(uuid.uuid4()),
        )
    assert ei.value.status_code == 409

    cur = await db_module._conn.execute(
        "SELECT count(*) FROM saas.settlement WHERE reconciliation_id = %s::uuid",
        (recon["id"],))
    assert (await cur.fetchone())[0] == 1, "一張對帳單只能有一筆 settlement"


async def test_db_unique_constraint_is_the_last_resort(recon):
    """DB 端 UNIQUE 必須存在——狀態機擋不到的真並發要靠它（migration 124）。

    只靠應用層狀態機是不夠的：兩個並發交易可能都在 FOR UPDATE 之前讀到 in_review
    （若日後有人移掉 FOR UPDATE），此時唯一鍵是最後一道。
    """
    cur = await db_module._conn.execute(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conname = 'uniq_saas_settlement_reconciliation'")
    assert (await cur.fetchone())[0] == 1, \
        "saas.settlement 缺 UNIQUE(reconciliation_id) → 並發 co-sign 會重複出款"


async def test_cosign_uses_row_lock():
    """靜態守線：co_sign 必須在交易內且對 reconciliation 取 FOR UPDATE。"""
    import inspect
    src = inspect.getsource(svc.co_sign_reconciliation)
    assert "transaction()" in src, "co_sign 必須包在交易內（原子性）"
    assert "FOR UPDATE" in src, "必須對 reconciliation 列加鎖（防並發雙簽）"
    # publish 必須在交易之後——放交易內會在 rollback 時發出對應不存在 settlement 的事件
    assert src.index("transaction()") < src.index("publish_event"), \
        "publish 必須在 commit 之後"
