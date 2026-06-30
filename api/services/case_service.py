"""Knowledge Base Cases 業務邏輯。

範圍：CRUD + searchCases（先以關鍵字加權打分；embedding 寫入後可改 vector）。
embedding 欄位 Phase 1 不寫入；embedding_status 預設 'processing'，
未來由背景 worker 補齊。
"""

from __future__ import annotations

import logging
import re
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

    # 總筆數（基礎過濾、不含 cursor）：供前端 tab badge 顯示真實總數
    count_cur = await db_module._conn.execute(
        f"SELECT COUNT(*) FROM case_entries WHERE {' AND '.join(where)}",
        list(args),
    )
    total_count = (await count_cur.fetchone())[0]

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

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more, "total_count": total_count}


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


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_NON_CJK_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(query: str) -> list[str]:
    """切詞：英數連續字串 + 中文 bigram（連續中文長度 < 2 時退化為單字）。"""
    if not query:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for m in _NON_CJK_TOKEN_RE.findall(query):
        t = m.lower()
        if t and t not in seen:
            seen.add(t)
            tokens.append(t)
    for m in _CJK_RE.findall(query):
        if len(m) <= 1:
            if m and m not in seen:
                seen.add(m)
                tokens.append(m)
            continue
        for i in range(len(m) - 1):
            bg = m[i : i + 2]
            if bg not in seen:
                seen.add(bg)
                tokens.append(bg)
    return tokens


def _score_case(
    *,
    case: dict,
    tokens: list[str],
    brand_filter: str | None,
    model_filter: str | None,
) -> float:
    """逐 token 累加加權命中度，最終正規化到 [0, 1]。

    權重：title 0.55、problem_description 0.30、solution 0.15。
    brand 完全相符額外 +0.10，model +0.05；總分以 1.0 為上限。
    """
    if not tokens:
        return 0.0
    title = (case.get("title") or "").lower()
    problem = (case.get("problem_description") or "").lower()
    solution = (case.get("solution") or "").lower()

    per_token_max = 0.55
    raw = 0.0
    for tok in tokens:
        if tok in title:
            raw += 0.55
        elif tok in problem:
            raw += 0.30
        elif tok in solution:
            raw += 0.15

    base = raw / (len(tokens) * per_token_max)

    if brand_filter and case.get("brand") and brand_filter.lower() == case["brand"].lower():
        base = min(1.0, base + 0.10)
    if model_filter and case.get("model") and model_filter.lower() == case["model"].lower():
        base = min(1.0, base + 0.05)

    return min(1.0, max(0.0, base))


async def search_cases(
    *,
    tenant_id: str,
    query: str,
    brand: str | None = None,
    model: str | None = None,
    limit: int = 5,
    similarity_threshold: float = 0.75,
) -> dict:
    """關鍵字加權打分：先以 brand/model + tenant 過濾，於記憶體中對 title /
    problem_description / solution 做 token 命中加權，回傳分數高於門檻的 hits。

    embedding 與 vector cosine 走 Phase 2；本實作確保契約端點可上線。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if not query or not query.strip():
        raise ApiError("VALIDATION_ERROR", "query is required", 422)

    tokens = _tokenize(query)
    if not tokens:
        return {"hits": []}

    where = ["tenant_id = %s::uuid", "is_active = TRUE"]
    args: list = [tenant_id]
    if brand:
        where.append("LOWER(brand) = LOWER(%s)")
        args.append(brand)
    if model:
        where.append("LOWER(model) = LOWER(%s)")
        args.append(model)

    sql = (
        f"SELECT {_SELECT_COLUMNS} FROM case_entries "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY updated_at DESC "
        f"LIMIT 500"
    )
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    hits: list[dict] = []
    for r in rows:
        case = _row_to_dict(r)
        score = _score_case(
            case=case,
            tokens=tokens,
            brand_filter=brand,
            model_filter=model,
        )
        if score >= similarity_threshold:
            hits.append({"case": case, "score": round(score, 4)})

    hits.sort(key=lambda h: h["score"], reverse=True)
    return {"hits": hits[:limit]}
