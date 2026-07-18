"""Exception Approval Inbox Service — FR-0049 Phase II MVP 起手。

統一聚合所有 pending approval task 為單一 inbox：
  - scope_changes pending (Flow 3 範圍變更等客戶決定)
  - refund_requests pending / csm_approved (Flow 6 退款雙簽中)
  - saas.dispute filed / in_review (Flow 7 爭議等仲裁)
  - saas.reschedule_proposal pending (Flow 11 改約等客戶確認)
  - saas.reconciliation_exception detected / ops_review / fix_proposed
    (Flow 13 EX5 對帳異常等決議；CR-0018)

統一回 envelope：
  {type, id, target_id, summary, severity, created_at, days_overdue}

MVP 範圍（per FR-0049 §3 Phase II 啟動時需補）：
  - 不做 routing engine 規則（all approval 都顯示，由 admin 自行篩）
  - 不做 escalation matrix（提供 days_overdue 讓 UI 標示）
  - 不做 bulk operations（單筆 approve 走原有 endpoint）

實作不修改既有 schema、不破壞既有 endpoint — 純讀組合 + 統一回 envelope。
"""

from __future__ import annotations

import logging
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.approval_inbox_service")

# 嚴重度分級（給 UI sort 用；對齊業務優先順序）
_SEVERITY_BY_TYPE = {
    "dispute": "high",          # 爭議涉客訴升級，最優先
    "refund": "high",            # 退款涉錢
    "scope_change": "medium",    # 範圍變更涉客戶體驗
    "recon_exception": "medium",  # 對帳異常涉錢但通常 batch 處理
    "reschedule": "low",         # 改約一般情境
}


def _days_overdue(created_at, sla_days: int) -> int:
    """已建立但未決議的天數差 - sla_days；負數代表 SLA 內。"""
    from datetime import datetime, timezone
    if created_at is None:
        return 0
    now = datetime.now(timezone.utc)
    age_days = (now - created_at.replace(tzinfo=timezone.utc)).days
    return age_days - sla_days


# summary 內嵌狀態/異常種類的中文標籤（業主 UAT：機器碼不可直出到 UI 摘要）
_DISPUTE_STATUS_LABEL = {
    "filed": "待處理",
    "in_review": "審查中",
    "mediation": "調解中",
}
_EXCEPTION_KIND_LABEL = {
    "amount_mismatch": "金額不符",
    "orphan_settlement": "孤兒入帳",
    "missing_invoice": "缺發票",
}

# 各類 SLA（per FR-0049 對 escalation matrix 的代理；MVP 用統一預設）
_SLA_DAYS_BY_TYPE = {
    "scope_change": 1,       # 24hr 內客戶須決定
    "refund": 3,             # 3 天內雙簽完成
    "dispute": 60,           # 對齊 dispute_v2 60d sla
    "reschedule": 1,         # 24hr 內客戶須決定
    "recon_exception": 7,    # 1 週內 ops 須處理
}


async def list_pending_approvals(
    *,
    tenant_id: str,
    type_filter: str | None = None,  # scope_change|refund|dispute|reschedule|recon_exception|all
    limit: int = 100,
) -> dict:
    """統一聚合所有 pending approval row → 單一 inbox list。

    Args:
      type_filter: 限定類別（None 或 'all' = 全部）
      limit: 每類最多 row 數（防大查詢）

    Returns:
      {
        "tenant_id": str,
        "type_filter": str | None,
        "total": int,
        "by_type": {scope_change: int, refund: int, ...},
        "items": [
          {type, id, target_id, summary, severity, created_at, days_overdue},
          ...
        ]
      }
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    valid_filter = {None, "all", "scope_change", "refund", "dispute",
                    "reschedule", "recon_exception"}
    if type_filter not in valid_filter:
        raise ApiError(
            "VALIDATION_ERROR", f"invalid type_filter: {type_filter}", 422,
        )

    items: list[dict] = []
    by_type: dict[str, int] = {
        "scope_change": 0, "refund": 0, "dispute": 0,
        "reschedule": 0, "recon_exception": 0,
    }

    def _want(t: str) -> bool:
        return type_filter is None or type_filter == "all" or type_filter == t

    # 1. scope_changes pending
    if _want("scope_change"):
        cur = await db_module._conn.execute(
            "SELECT sc.id, sc.work_order_id, sc.reason, sc.created_at "
            "FROM scope_changes sc "
            "JOIN work_orders wo ON sc.work_order_id = wo.id "
            "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
            "LEFT JOIN conversations c ON pc.conversation_id = c.id "
            "LEFT JOIN users u ON c.user_id = u.id "
            "WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid AND sc.status = 'pending' "
            "ORDER BY sc.created_at LIMIT %s",
            (tenant_id, limit),
        )
        for r in await cur.fetchall():
            items.append(_envelope(
                "scope_change", r[0], r[1],
                f"範圍變更：{(r[2] or '')[:80]}", r[3],
            ))
            by_type["scope_change"] += 1

    # 2. refund_requests pending / csm_approved（等 ops_manager 簽）
    if _want("refund"):
        cur = await db_module._conn.execute(
            "SELECT rr.id, rr.work_order_id, rr.amount, rr.reason, "
            "       rr.status, rr.created_at "
            "FROM refund_requests rr "
            "LEFT JOIN work_orders wo ON rr.work_order_id = wo.id "
            "LEFT JOIN problem_cards pc ON wo.problem_card_id = pc.id "
            "LEFT JOIN conversations c ON pc.conversation_id = c.id "
            "LEFT JOIN users u ON c.user_id = u.id "
            "WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid "
            "  AND rr.status IN ('pending', 'csm_approved') "
            "ORDER BY rr.created_at LIMIT %s",
            (tenant_id, limit),
        )
        for r in await cur.fetchall():
            stage = "等 CSM 審" if r[4] == "pending" else "等 ops_manager 簽"
            items.append(_envelope(
                "refund", r[0], r[1],
                f"退款 {float(r[2] or 0):.2f}：{stage}",
                r[5],
            ))
            by_type["refund"] += 1

    # 3. saas.dispute filed / in_review
    if _want("dispute"):
        cur = await db_module._conn.execute(
            "SELECT id, work_order_id, status, description, filed_at "
            "FROM saas.dispute "
            "WHERE tenant_id = %s::uuid "
            "  AND status IN ('filed', 'in_review', 'mediation') "
            "ORDER BY filed_at LIMIT %s",
            (tenant_id, limit),
        )
        for r in await cur.fetchall():
            status_label = _DISPUTE_STATUS_LABEL.get(r[2], r[2])
            # description 為空時退 status 中文（原本退原始碼 → 出現「爭議(filed)：filed」雙重漏出）
            summary = (r[3] or "")[:80] if r[3] else status_label
            items.append(_envelope(
                "dispute", r[0], r[1],
                f"爭議（{status_label}）：{summary}", r[4],
            ))
            by_type["dispute"] += 1

    # 4. saas.reschedule_proposal pending
    if _want("reschedule"):
        cur = await db_module._conn.execute(
            "SELECT id, work_order_id, message_to_customer, created_at "
            "FROM saas.reschedule_proposal "
            "WHERE tenant_id = %s::uuid AND status = 'pending' "
            "ORDER BY created_at LIMIT %s",
            (tenant_id, limit),
        )
        for r in await cur.fetchall():
            items.append(_envelope(
                "reschedule", r[0], r[1],
                f"改約：{(r[2] or '等客戶選時段')[:80]}", r[3],
            ))
            by_type["reschedule"] += 1

    # 5. saas.reconciliation_exception 非終態（CR-0018）
    if _want("recon_exception"):
        cur = await db_module._conn.execute(
            "SELECT id, reconciliation_id, exception_kind, description, "
            "       created_at "
            "FROM saas.reconciliation_exception "
            "WHERE tenant_id = %s::uuid "
            "  AND status IN ('detected', 'ops_review', 'fix_proposed') "
            "ORDER BY created_at LIMIT %s",
            (tenant_id, limit),
        )
        for r in await cur.fetchall():
            items.append(_envelope(
                "recon_exception", r[0], r[1],
                f"對帳異常（{_EXCEPTION_KIND_LABEL.get(r[2], r[2])}）：{(r[3] or '')[:80]}", r[4],
            ))
            by_type["recon_exception"] += 1

    # sort: severity (high > medium > low) → days_overdue desc → created_at asc
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(
        key=lambda x: (
            severity_rank.get(x["severity"], 9),
            -x["days_overdue"],
            x["created_at"] or "",
        ),
    )

    return {
        "tenant_id": tenant_id,
        "type_filter": type_filter,
        "total": len(items),
        "by_type": by_type,
        "items": items,
    }


def _envelope(
    type_: str, id_: Any, target_id: Any, summary: str, created_at,
) -> dict:
    severity = _SEVERITY_BY_TYPE.get(type_, "medium")
    sla_days = _SLA_DAYS_BY_TYPE.get(type_, 1)
    return {
        "type": type_,
        "id": str(id_),
        "target_id": str(target_id) if target_id else None,
        "summary": summary,
        "severity": severity,
        "created_at": created_at.isoformat() if created_at else None,
        "days_overdue": _days_overdue(created_at, sla_days),
    }
