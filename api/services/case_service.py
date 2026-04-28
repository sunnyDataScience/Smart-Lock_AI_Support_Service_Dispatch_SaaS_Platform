"""Knowledge Base Cases 業務邏輯。

範圍：CRUD（不含向量搜尋；searchCases 屬 Phase 2）。
embedding 欄位 Phase 1 不寫入；embedding_status 預設 'processing'，
未來由背景 worker 補齊。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.case_service")


_SELECT_COLUMNS = (
    "id, title, problem_description, solution, brand, model, "
    "COALESCE(tags, ARRAY[]::TEXT[]) AS tags, "
    "COALESCE(verified, FALSE) AS verified, "
    "COALESCE(embedding_status, 'processing') AS embedding_status, "
    "created_at, updated_at"
)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "title": row[1],
        "problem_description": row[2],
        "solution": row[3],
        "brand": row[4],
        "model": row[5],
        "tags": list(row[6] or []),
        "verified": bool(row[7]),
        "embedding_status": row[8] or "processing",
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


async def list_cases(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    brand: str | None,
    verified: bool | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid", "is_active = TRUE"]
    args: list = [tenant_id]

    if brand:
        where.append("brand = %s")
        args.append(brand)
    if verified is not None:
        where.append("COALESCE(verified, FALSE) = %s")
        args.append(verified)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM case_entries "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY created_at DESC, id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[9].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_case(*, tenant_id: str, case_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM case_entries "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid AND is_active = TRUE",
        (case_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Case not found", 404)
    return _row_to_dict(row)


async def create_case(
    *, tenant_id: str, payload: dict, created_by: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    case_id = str(uuid.uuid4())
    tags = payload.get("tags") or []

    cur = await db_module._conn.execute(
        "INSERT INTO case_entries "
        "(id, tenant_id, title, problem_description, solution, brand, model, tags, "
        " verified, embedding_status, source, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, "
        "        FALSE, 'processing', 'manual_input', TRUE) "
        f"RETURNING {_SELECT_COLUMNS}",
        (
            case_id,
            tenant_id,
            payload["title"],
            payload["problem_description"],
            payload["solution"],
            payload["brand"],
            payload.get("model"),
            tags,
        ),
    )
    row = await cur.fetchone()
    return _row_to_dict(row)


async def update_case(
    *, tenant_id: str, case_id: str, patch: dict,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sets: list[str] = []
    args: list = []
    field_map = {
        "title": "title",
        "problem_description": "problem_description",
        "solution": "solution",
        "brand": "brand",
        "model": "model",
        "tags": "tags",
        "verified": "verified",
    }
    for key, column in field_map.items():
        if key in patch and patch[key] is not None:
            sets.append(f"{column} = %s")
            args.append(patch[key])

    # 內容變動需重新生成 embedding
    if any(k in patch for k in ("title", "problem_description", "solution")):
        sets.append("embedding_status = 'processing'")

    if not sets:
        return await get_case(tenant_id=tenant_id, case_id=case_id)

    args.extend([case_id, tenant_id])
    sql = (
        f"UPDATE case_entries SET {', '.join(sets)}, updated_at = NOW() "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid AND is_active = TRUE "
        f"RETURNING {_SELECT_COLUMNS}"
    )
    cur = await db_module._conn.execute(sql, args)
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Case not found", 404)
    return _row_to_dict(row)


async def delete_case(*, tenant_id: str, case_id: str) -> None:
    """軟刪除：is_active = FALSE。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "UPDATE case_entries SET is_active = FALSE, updated_at = NOW() "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND is_active = TRUE",
        (case_id, tenant_id),
    )
    if cur.rowcount == 0:
        raise ApiError("NOT_FOUND", "Case not found", 404)
