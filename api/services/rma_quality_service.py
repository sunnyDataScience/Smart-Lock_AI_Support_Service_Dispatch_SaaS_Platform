"""RMA Quality Feedback Loop Service — FR-0048 Phase II MVP。

RMA 結案後品質訊號回收：4 cascade 對應：
  (a) brand_quality_score → 品牌商 feedback
  (b) technician_quality_score → M07 績效
  (c) ai_diagnosis_accuracy → SOP feedback (FR-0051)
  (d) customer_satisfaction_score → 月結 commission

提供 ops:
  - log_finding: 寫 row + 可選自動 propagate 到 sop_feedback (rma_finding source)
  - list_findings: filter by failure_mode / brand / technician / date
  - get_brand_summary: 聚合 by failure_mode + brand_quality 平均（給品牌商 report）
  - get_technician_summary: 聚合 by technician + technician_quality 平均（給 M07 績效）
"""

from __future__ import annotations

import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.rma_quality_service")

_VALID_AI_ACCURACY = {"accurate", "partial", "wrong"}


async def log_finding(
    *,
    tenant_id: str,
    failure_mode: str,
    warranty_claim_id: str | None = None,
    work_order_id: str | None = None,
    technician_id: str | None = None,
    brand: str | None = None,
    device_model: str | None = None,
    root_cause: str | None = None,
    is_repeat_failure: bool = False,
    brand_quality_score: float | None = None,
    technician_quality_score: float | None = None,
    ai_diagnosis_accuracy: str | None = None,
    customer_satisfaction_score: float | None = None,
    reported_by_user_id: str | None = None,
    notes: str | None = None,
    propagate_to_sop_feedback_sop_id: str | None = None,
    propagate_to_sop_feedback_sop_type: str | None = None,
) -> dict:
    """寫 finding row；若 `propagate_to_sop_feedback_sop_id` 提供且 ai_diagnosis_accuracy
    為 'wrong' 或 'partial'，自動連動寫一條 sop_feedback (source='rma_finding')。"""
    if not failure_mode or len(failure_mode.strip()) < 3:
        raise ApiError("VALIDATION_ERROR", "failure_mode ≥3 字元", 422)
    if ai_diagnosis_accuracy and ai_diagnosis_accuracy not in _VALID_AI_ACCURACY:
        raise ApiError(
            "VALIDATION_ERROR",
            f"invalid ai_diagnosis_accuracy: {ai_diagnosis_accuracy}",
            422,
        )
    for name, val in (
        ("brand_quality_score", brand_quality_score),
        ("technician_quality_score", technician_quality_score),
        ("customer_satisfaction_score", customer_satisfaction_score),
    ):
        if val is not None and not (1.0 <= val <= 5.0):
            raise ApiError(
                "VALIDATION_ERROR", f"{name} must be 1.0..5.0 or null", 422,
            )
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "INSERT INTO saas.rma_quality_finding "
        "  (tenant_id, warranty_claim_id, work_order_id, technician_id, "
        "   brand, device_model, failure_mode, root_cause, is_repeat_failure, "
        "   brand_quality_score, technician_quality_score, "
        "   ai_diagnosis_accuracy, customer_satisfaction_score, "
        "   reported_by_user_id, notes) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, "
        "        %s, %s, %s, %s, %s::uuid, %s) "
        "RETURNING id, created_at",
        (
            tenant_id, warranty_claim_id, work_order_id, technician_id,
            brand, device_model, failure_mode.strip()[:200],
            root_cause.strip()[:1000] if root_cause else None,
            is_repeat_failure,
            brand_quality_score, technician_quality_score,
            ai_diagnosis_accuracy, customer_satisfaction_score,
            reported_by_user_id,
            notes.strip()[:2000] if notes else None,
        ),
    )
    row = await cur.fetchone()
    finding_id = str(row[0])

    # Cascade (c): AI 分診差 → 寫 sop_feedback rma_finding source
    if (
        propagate_to_sop_feedback_sop_id
        and propagate_to_sop_feedback_sop_type
        and ai_diagnosis_accuracy in {"partial", "wrong"}
    ):
        try:
            from services import sop_feedback_service
            sentiment = "negative" if ai_diagnosis_accuracy == "wrong" else "neutral"
            await sop_feedback_service.log_feedback(
                tenant_id=tenant_id,
                sop_id=propagate_to_sop_feedback_sop_id,
                sop_type=propagate_to_sop_feedback_sop_type,
                source="rma_finding",
                sentiment=sentiment,
                comment=f"AI diagnosis {ai_diagnosis_accuracy}: {failure_mode}",
                metadata={
                    "rma_quality_finding_id": finding_id,
                    "warranty_claim_id": warranty_claim_id,
                    "work_order_id": work_order_id,
                    "ai_diagnosis_accuracy": ai_diagnosis_accuracy,
                },
                work_order_id=work_order_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "sop_feedback cascade failed for finding=%s", finding_id[:8],
            )

    return {
        "id": finding_id,
        "created_at": row[1].isoformat() if row[1] else None,
        "failure_mode": failure_mode,
        "cascade_sop_feedback": bool(
            propagate_to_sop_feedback_sop_id
            and ai_diagnosis_accuracy in {"partial", "wrong"}
        ),
    }


async def list_findings(
    *,
    tenant_id: str,
    failure_mode: str | None = None,
    brand: str | None = None,
    technician_id: str | None = None,
    is_repeat_failure: bool | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if failure_mode:
        where.append("failure_mode = %s")
        args.append(failure_mode)
    if brand:
        where.append("brand = %s")
        args.append(brand)
    if technician_id:
        where.append("technician_id = %s::uuid")
        args.append(technician_id)
    if is_repeat_failure is not None:
        where.append("is_repeat_failure = %s")
        args.append(is_repeat_failure)
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    args.append(limit)

    cur = await db_module._conn.execute(
        "SELECT id, warranty_claim_id, work_order_id, technician_id, brand, "
        "       device_model, failure_mode, root_cause, is_repeat_failure, "
        "       brand_quality_score, technician_quality_score, "
        "       ai_diagnosis_accuracy, customer_satisfaction_score, "
        "       created_at "
        "FROM saas.rma_quality_finding "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "warranty_claim_id": str(r[1]) if r[1] else None,
            "work_order_id": str(r[2]) if r[2] else None,
            "technician_id": str(r[3]) if r[3] else None,
            "brand": r[4],
            "device_model": r[5],
            "failure_mode": r[6],
            "root_cause": r[7],
            "is_repeat_failure": r[8],
            "brand_quality_score": (
                float(r[9]) if r[9] is not None else None
            ),
            "technician_quality_score": (
                float(r[10]) if r[10] is not None else None
            ),
            "ai_diagnosis_accuracy": r[11],
            "customer_satisfaction_score": (
                float(r[12]) if r[12] is not None else None
            ),
            "created_at": r[13].isoformat() if r[13] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


async def get_brand_summary(
    *,
    tenant_id: str,
    brand: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Cascade (a) brand 視角：top failure_mode + brand_quality 平均。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if brand:
        where.append("brand = %s")
        args.append(brand)
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    base = " AND ".join(where)

    # top failure_mode
    cur = await db_module._conn.execute(
        "SELECT failure_mode, COUNT(*) FROM saas.rma_quality_finding "
        f"WHERE {base} GROUP BY failure_mode ORDER BY COUNT(*) DESC LIMIT 10",
        tuple(args),
    )
    top_failure_modes = [
        {"failure_mode": r[0], "count": int(r[1])}
        for r in await cur.fetchall()
    ]

    # brand_quality avg + total + repeat_failure rate
    cur = await db_module._conn.execute(
        "SELECT COUNT(*), AVG(brand_quality_score), "
        "       COUNT(*) FILTER (WHERE is_repeat_failure = true) "
        f"FROM saas.rma_quality_finding WHERE {base}",
        tuple(args),
    )
    agg = await cur.fetchone()
    total = int(agg[0] or 0) if agg else 0
    avg_brand_quality = (
        round(float(agg[1]), 2) if agg and agg[1] is not None else None
    )
    repeat_count = int(agg[2] or 0) if agg else 0
    repeat_failure_pct = (
        round(100.0 * repeat_count / total, 2) if total > 0 else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "brand": brand,
        "total_findings": total,
        "avg_brand_quality_score": avg_brand_quality,
        "repeat_failure_pct": repeat_failure_pct,
        "top_failure_modes": top_failure_modes,
    }


async def get_technician_summary(
    *,
    tenant_id: str,
    technician_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Cascade (b) 技師視角：technician_quality 平均 + 處理筆數 + repeat rate。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "technician_id = %s::uuid"]
    args: list = [tenant_id, technician_id]
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    base = " AND ".join(where)

    cur = await db_module._conn.execute(
        "SELECT COUNT(*), AVG(technician_quality_score), "
        "       AVG(customer_satisfaction_score), "
        "       COUNT(*) FILTER (WHERE is_repeat_failure = true) "
        f"FROM saas.rma_quality_finding WHERE {base}",
        tuple(args),
    )
    agg = await cur.fetchone()
    total = int(agg[0] or 0) if agg else 0
    avg_tq = round(float(agg[1]), 2) if agg and agg[1] is not None else None
    avg_cs = round(float(agg[2]), 2) if agg and agg[2] is not None else None
    repeat_count = int(agg[3] or 0) if agg else 0
    repeat_pct = (
        round(100.0 * repeat_count / total, 2) if total > 0 else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "technician_id": technician_id,
        "total_findings": total,
        "avg_technician_quality_score": avg_tq,
        "avg_customer_satisfaction_score": avg_cs,
        "repeat_failure_pct": repeat_pct,
    }
