"""LINE Flex push outbox service — CR-0017 Stage 1.1.

業主裁決 (2026-06-05):
  HD-1: 階段化獨立 LINE bot service
  HD-2: Outbox table + worker pattern
  HD-3: api/templates/ Python flex builders

本 service 提供 write API：service-layer caller（propose_reschedule_v2 /
record_scope_change / _detect_schedule_conflict_and_publish）寫入 outbox
row；worker 端（Stage 2 落地）負責 poll + render Flex + push LINE。

不在本 service scope（屬 worker）：
  - Flex template render（api/templates/ Python builders）
  - 真實 push 到 LINE Messaging API
  - retry / backoff 排程
  - sent / failed / dead 狀態回寫
"""

from __future__ import annotations

import json
import logging
from typing import Literal

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.line_push_outbox_service")

# 對齊 SQL/Schema_v2_extensions.sql §12 line_push_outbox.push_kind
# 註：push_kind 為 VARCHAR(40) 無 CHECK 約束，新增 kind 不需 migration。
PushKind = Literal[
    "reschedule_proposal",
    "scope_change_proposal",
    "schedule_conflict",
    # CR-0028 LINE 公單回傳斷鏈
    "work_order_assigned",
    "work_order_accepted",
    "scope_change_result",
    # CR-0027 完工電子工單通知
    "work_order_document",
]

# 對齊 chk_push_status CHECK
OutboxStatus = Literal["pending", "sent", "failed", "dead"]


async def enqueue(
    *,
    tenant_id: str,
    push_kind: PushKind,
    payload: dict,
    target_line_id: str | None = None,
    reference_id: str | None = None,
    reference_table: str | None = None,
    max_attempts: int = 5,
) -> str:
    """寫入 outbox row → 回傳 outbox_id。

    Args:
        tenant_id: 租戶 UUID
        push_kind: 推送類型（決定走哪個 Flex builder）
        payload: 給 Flex builder 的資料（dict → JSONB）
        target_line_id: LINE userId（可 NULL，worker 從 reference 反查）
        reference_id: 對應業務 row UUID（reschedule_proposal.id 等）
        reference_table: 對應業務表名（'saas.reschedule_proposal' 等）
        max_attempts: 最大重試次數（預設 5）

    Raises:
        ApiError(503): DB 不可用
        ApiError(422): payload 序列化失敗
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "VALIDATION_ERROR",
            f"payload JSON 序列化失敗: {exc}",
            422,
        ) from exc

    cur = await db_module._conn.execute(
        "INSERT INTO line_push_outbox "
        "  (tenant_id, push_kind, target_line_id, reference_id, reference_table, "
        "   payload, max_attempts) "
        "VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s) "
        "RETURNING id",
        (tenant_id, push_kind, target_line_id, reference_id, reference_table,
         payload_json, max_attempts),
    )
    row = await cur.fetchone()
    outbox_id = str(row[0])
    logger.info(
        "outbox enqueue ok: id=%s kind=%s tenant=%s ref=%s/%s",
        outbox_id, push_kind, tenant_id, reference_table, reference_id,
    )
    return outbox_id


async def get(*, outbox_id: str) -> dict | None:
    """取單筆 outbox row（debug / status 查詢用）。

    回傳 dict 或 None（不存在）。不做 tenant 隔離（內部運維工具）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, push_kind, target_line_id, reference_id, "
        "       reference_table, payload, status, attempts, max_attempts, "
        "       next_attempt_at, last_error, sent_at, created_at, updated_at "
        "FROM line_push_outbox WHERE id = %s::uuid",
        (outbox_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "push_kind": row[2],
        "target_line_id": row[3],
        "reference_id": str(row[4]) if row[4] else None,
        "reference_table": row[5],
        "payload": row[6] if isinstance(row[6], dict) else (json.loads(row[6]) if row[6] else {}),
        "status": row[7],
        "attempts": int(row[8]),
        "max_attempts": int(row[9]),
        "next_attempt_at": row[10].isoformat() if row[10] else None,
        "last_error": row[11],
        "sent_at": row[12].isoformat() if row[12] else None,
        "created_at": row[13].isoformat() if row[13] else None,
        "updated_at": row[14].isoformat() if row[14] else None,
    }


async def count_by_status(*, tenant_id: str) -> dict[str, int]:
    """tenant 範圍 outbox 各狀態筆數（健康監控 / dashboard 用）。

    回傳 `{"pending": N, "sent": N, "failed": N, "dead": N}`。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, COUNT(*) FROM line_push_outbox "
        "WHERE tenant_id = %s::uuid "
        "GROUP BY status",
        (tenant_id,),
    )
    rows = await cur.fetchall()
    result = {"pending": 0, "sent": 0, "failed": 0, "dead": 0}
    for r in rows:
        result[r[0]] = int(r[1])
    return result
