"""期末對帳閘門（CR-0166 R4 / WBS 3.2.1 / ADR-017）。

品牌側 per-job 佣金明細（品牌庫 settlements＝資料源）vs 技師平台跨品牌彙總
（技師庫 technician_commission_projection＝事件消費投影）——期末 reconcile 對平。

C4 hash mismatch = 0（27_Roadmap 階段閘條件 3）：任一 settlement 在投影缺漏或金額
不符 → 標記，mismatch>0 阻結算完成（供 ops 對帳閘門呼叫）。

最終一致性容忍（ADR-017 §59）：事件有延遲，reconcile 於期末跑（非即時）；
Kafka 未啟用（無投影）時回 skipped（不誤報 mismatch）。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.event_reconcile")


def _amount_eq(a, b, *, tol: float = 0.005) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


async def reconcile_commission(*, tenant_id: str) -> dict:
    """對平品牌 settlements vs 技師佣金投影。

    回 {checked, matched, mismatched:[...], missing:[...], skipped, gate_pass}。
    gate_pass=False 時 mismatch>0 或 missing>0（C4 mismatch≠0），應阻結算。
    """
    from core.event_bus import enabled as _kafka_enabled

    if not _kafka_enabled():
        # 2026-07-31（TC-EXC-06）：原本這裡回 gate_pass=True，註解稱「fail-open by
        # design，單庫/無事件不誤擋」。但**無法驗證不等於驗證通過** —— 一旦租戶明示
        # 打開 reconcile_gate_enforce（＝要求對帳把關），Kafka 沒開反而靜默放行，
        # 閘門形同虛設。skipped 仍為 True，呼叫端可分辨「沒跑」與「跑了不過」。
        #
        # 爆炸半徑：`reconcile_gate_enforce` 預設 off（config namespace
        # settlement_policy），未開啟的租戶結算路徑完全不受影響。
        return {"checked": 0, "matched": 0, "mismatched": [], "missing": [],
                "skipped": True, "gate_pass": False,
                "reason": "KAFKA_BOOTSTRAP 未設，投影未啟用——對帳無法執行，"
                          "故不判定為通過（如需結算請關閉 reconcile_gate_enforce 或啟用事件投影）"}

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 品牌側 settlements（資料源）——JOIN reconciliations→technicians 取租戶
    cur = await db_module._conn.execute(
        "SELECT s.id, s.technician_id, s.amount "
        "FROM settlements s "
        "JOIN reconciliations r ON s.reconciliation_id = r.id "
        "JOIN technicians t ON s.technician_id = t.id "
        "WHERE t.tenant_id = %s::uuid",
        (tenant_id,),
    )
    brand_rows = await cur.fetchall()

    # 技師側投影（消費 commission.accrued）
    tconn = await db_module.require_tech_conn()
    pcur = await tconn.execute(
        "SELECT settlement_id, amount FROM technician_commission_projection "
        "WHERE tenant_id = %s::uuid",
        (tenant_id,),
    )
    proj = {str(r[0]): r[1] for r in await pcur.fetchall()}

    matched = 0
    mismatched: list[dict] = []
    missing: list[str] = []
    for sid, tech_id, amount in brand_rows:
        key = str(sid)
        if key not in proj:
            missing.append(key)
        elif _amount_eq(proj[key], amount):
            matched += 1
        else:
            mismatched.append({"settlement_id": key,
                               "brand_amount": float(amount),
                               "projection_amount": float(proj[key])})

    gate_pass = not mismatched and not missing
    result = {
        "checked": len(brand_rows), "matched": matched,
        "mismatched": mismatched, "missing": missing,
        "skipped": False, "gate_pass": gate_pass,
    }
    if not gate_pass:
        logger.warning("對帳閘門 mismatch tenant=%s mismatched=%d missing=%d",
                       tenant_id, len(mismatched), len(missing))
    return result
