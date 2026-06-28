"""M01 進線 Case 業務邏輯（CR-0108）。

Case = 一次進線事件（上游容器，下可含多 problem_card / work_order，D4）。
- 多渠道客服代建（D1：line/phone/web/referral）。
- 建案即啟動 first-response SLA 計時（D2：級距入 [intake].first_response_sla_minutes config，
  暫定 30 分待業主確認）。
- 可讀號 C-NNNNNN（D5，per-序列）。
- D3 漸進：problem_cards/work_orders 的 case_id 為 nullable 關聯，本服務不硬擋既有流程。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import core.db as db_module
from core.config import load_config
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.intake_case_service")

_SOURCE_CHANNELS = ("line", "phone", "web", "referral")  # D1 Phase I
_STATUSES = ("open", "in_progress", "closed")
_DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"


def _sla_minutes() -> int:
    return int(load_config().intake.get("first_response_sla_minutes", 30))


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "case_number": row[1],
        "source_channel": row[2],
        "customer_id": str(row[3]) if row[3] else None,
        "customer_name": row[4],
        "customer_phone": row[5],
        "customer_line_id": row[6],
        "summary": row[7],
        "status": row[8],
        "first_response_due_at": row[9].isoformat() if row[9] else None,
        "first_responded_at": row[10].isoformat() if row[10] else None,
        "created_by": str(row[11]) if row[11] else None,
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }


_SELECT_COLS = (
    "id, case_number, source_channel, customer_id, customer_name, customer_phone, "
    "customer_line_id, summary, status, first_response_due_at, first_responded_at, "
    "created_by, created_at, updated_at"
)


async def create_case(
    *,
    tenant_id: str,
    source_channel: str,
    summary: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_line_id: str | None = None,
    customer_id: str | None = None,
    created_by: str | None = None,
) -> dict:
    """客服代建 Case；建案即啟動 first-response SLA。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if source_channel not in _SOURCE_CHANNELS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"source_channel must be one of {list(_SOURCE_CHANNELS)}（partner 渠道屬 Phase II）",
            422,
        )

    case_id = str(uuid.uuid4())
    # D5 可讀號：C-NNNNNN（序列原子遞增）
    cur = await db_module._conn.execute("SELECT nextval('saas.intake_case_number_seq')")
    seq = (await cur.fetchone())[0]
    case_number = f"C-{int(seq):06d}"

    await db_module._conn.execute(
        f"INSERT INTO saas.intake_case "
        f"(id, tenant_id, case_number, source_channel, customer_id, customer_name, "
        f" customer_phone, customer_line_id, summary, status, first_response_due_at, created_by) "
        f"VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, 'open', "
        f"        NOW() + make_interval(mins => %s), %s)",
        (
            case_id, tenant_id, case_number, source_channel,
            customer_id, customer_name, customer_phone, customer_line_id, summary,
            _sla_minutes(), created_by,
        ),
    )
    return await get_case(tenant_id=tenant_id, case_id=case_id)


async def list_cases(
    *, tenant_id: str, status: str | None = None, source_channel: str | None = None,
    limit: int = 50,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    clauses = ["tenant_id = %s::uuid"]
    params: list = [tenant_id]
    if status:
        clauses.append("status = %s")
        params.append(status)
    if source_channel:
        clauses.append("source_channel = %s")
        params.append(source_channel)
    params.append(min(int(limit), 200))

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLS} FROM saas.intake_case "
        f"WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT %s",
        tuple(params),
    )
    rows = await cur.fetchall()
    now = datetime.now(timezone.utc)
    items = []
    for r in rows:
        d = _row_to_dict(r)
        # 衍生 SLA 逾時旗標（未回應且已過期）
        d["sla_overdue"] = bool(r[9] and r[10] is None and r[9] < now)
        items.append(d)
    return {"items": items}


async def get_case(*, tenant_id: str, case_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLS} FROM saas.intake_case "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid LIMIT 1",
        (case_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CASE_NOT_FOUND", "Case not found in this tenant", 404)
    d = _row_to_dict(row)
    now = datetime.now(timezone.utc)
    d["sla_overdue"] = bool(row[9] and row[10] is None and row[9] < now)
    return {"data": d}


_ALLOWED_UPDATE = {"status", "summary", "customer_name", "customer_phone"}


async def update_case(*, tenant_id: str, case_id: str, patch: dict) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 先確認存在且同租戶（防跨租戶）
    await get_case(tenant_id=tenant_id, case_id=case_id)

    if "status" in patch and patch["status"] is not None and patch["status"] not in _STATUSES:
        raise ApiError("VALIDATION_ERROR", f"status must be one of {list(_STATUSES)}", 422)

    sets, params = [], []
    for col in _ALLOWED_UPDATE:
        if col in patch and patch[col] is not None:
            sets.append(f"{col} = %s")
            params.append(patch[col])
    # 標記首次回應（狀態由 open → in_progress 時記 first_responded_at）
    if patch.get("status") == "in_progress":
        sets.append("first_responded_at = COALESCE(first_responded_at, NOW())")
    if not sets:
        return await get_case(tenant_id=tenant_id, case_id=case_id)

    sets.append("updated_at = NOW()")
    params.extend([case_id, tenant_id])
    await db_module._conn.execute(
        f"UPDATE saas.intake_case SET {', '.join(sets)} "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
        tuple(params),
    )
    return await get_case(tenant_id=tenant_id, case_id=case_id)
