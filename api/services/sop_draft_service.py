"""SOP Drafts 業務邏輯（Phase 1.11 read-only + Phase 1.15 寫入路徑）。

範圍：listSopDrafts、getSopDraft、reviewSopDraft、adoptSopDraft。
不含：草稿生成 pipeline（由家族覆核引擎背景產出）。

DB↔OpenAPI 欄位對齊：
  - source_problem_card_id (DB) → problem_card_id (API)
  - source_conversation_id  (DB) → 不暴露（API schema 沒此欄位）
  - reviewed_by             (DB) → reviewer_id (API)
  - case_event_id           (API) → 始終 None（DB 無對應欄位）
  - status mapping (DB 4-value → API 4-value):
      pending_review → under_review
      approved       → approved
      rejected       → rejected
      published      → approved   （已發布視為已核准的終態）
  - steps (JSONB) 由 service 層 coerce 為 list[{order,title,description}]，
    缺欄位則 best-effort 補齊（保證 API schema required 不違反）。

寫入路徑狀態機（review / adopt）：
  pending_review --review(approve)--> approved
  pending_review --review(reject)---> rejected
  approved -------adopt-------------> published（同時建立 case_entries 一筆）
其他轉換一律 409 Conflict。已 published 不可再 adopt（一次性入庫）。
"""

from __future__ import annotations

import json
import logging
import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.sop_draft_service")


_DB_STATUS_TO_API = {
    "pending_review": "under_review",
    "approved": "approved",
    "rejected": "rejected",
    "published": "approved",
}

# 反向 mapping — API status filter → DB status 集合（一個 API 值可能對應多個 DB 值）
_API_STATUS_TO_DB = {
    "draft": [],  # DB 沒有 draft 狀態，API 篩選此值會返回空
    "under_review": ["pending_review"],
    "approved": ["approved", "published"],
    "rejected": ["rejected"],
}


_SELECT_COLUMNS = (
    "id, source_problem_card_id, title, steps, status, "
    "reviewed_by, reviewed_at, review_comment, created_at, document_number"
)


def _coerce_steps(raw) -> list[dict]:
    """把 DB JSONB steps 轉成 API SopDraftStep list。

    DB 沒有強制 schema；常見格式：
      [{"order":1,"title":"...","description":"..."}]
      [{"step":"...","detail":"..."}]            ← 舊格式
      [{"title":"...","desc":"..."}]             ← 前端 mock 格式
    缺欄位用 index + 1 / 空字串 fallback，保證符合 OpenAPI required。
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        order = item.get("order")
        if not isinstance(order, int) or order < 1:
            order = idx + 1
        title = (
            item.get("title")
            or item.get("step")
            or item.get("name")
            or f"Step {order}"
        )
        description = (
            item.get("description")
            or item.get("desc")
            or item.get("detail")
            or ""
        )
        out.append({
            "order": order,
            "title": str(title)[:200],
            "description": str(description)[:2000],
        })
    return out


def _row_to_dict(row: tuple) -> dict:
    db_status = (row[4] or "pending_review").lower()
    api_status = _DB_STATUS_TO_API.get(db_status, "under_review")
    return {
        "id": str(row[0]),
        "case_event_id": None,
        "problem_card_id": str(row[1]) if row[1] else None,
        "title": row[2] or "",
        "steps": _coerce_steps(row[3]),
        "status": api_status,
        "reviewer_id": str(row[5]) if row[5] else None,
        "reviewed_at": row[6].isoformat() if row[6] else None,
        "review_comment": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "document_number": row[9] if len(row) > 9 else None,
    }


async def list_drafts(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    status: str | None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if status:
        db_statuses = _API_STATUS_TO_DB.get(status, [])
        if not db_statuses:
            # 對應不到任何 DB 值 → 直接回空頁，省去查 DB
            return {"items": [], "next_cursor": None, "has_more": False}
        placeholders = ",".join(["%s"] * len(db_statuses))
        where.append(f"status IN ({placeholders})")
        args.extend(db_statuses)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(created_at, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM sop_drafts "
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
        next_cursor = encode_cursor({"ts": last[8].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_draft(*, tenant_id: str, draft_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM sop_drafts "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)
    return _row_to_dict(row)


async def create_draft(
    *,
    tenant_id: str,
    source_case_id: str,
    source_type: str,
    draft_content: str,
    model_version: str,
    confidence_score: float | None = None,
) -> tuple[dict, bool]:
    """F-017 SopDraft 建立（ADR-009 D pattern, agent 異步觸發）。

    Idempotency: business unique key (source_problem_card_id, model_version) —
    同案不同 LLM 版本可重出 draft。

    source_type 決定 draft_content 來源是 problem_card / case_entry / conversation。
    本 MVP 把 draft_content 整段塞 steps 第一筆，title 從 source_case 拉。
    後續可改為結構化 LLM output（多個 step）。

    Returns: (draft_dict, created_flag)
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 解析 source_problem_card_id（依 source_type）
    pc_id = None
    if source_type == "problem_card":
        pc_id = source_case_id
    elif source_type == "case_entry":
        # case_entries 可能有 problem_card_id ref，未實作時 keep None
        pc_id = None
    elif source_type == "conversation":
        # 從 conversation 找關聯 PC
        cur = await db_module._conn.execute(
            "SELECT id FROM problem_cards WHERE conversation_id = %s::uuid LIMIT 1",
            (source_case_id,),
        )
        row = await cur.fetchone()
        pc_id = str(row[0]) if row else None

    # 2. Idempotency check（pc_id + model_version）
    if pc_id:
        cur = await db_module._conn.execute(
            "SELECT id FROM sop_drafts "
            "WHERE source_problem_card_id = %s::uuid AND model_version = %s "
            "ORDER BY created_at ASC LIMIT 1",
            (pc_id, model_version),
        )
        existing = await cur.fetchone()
        if existing:
            draft = await get_draft(tenant_id=tenant_id, draft_id=str(existing[0]))
            return draft, False

    # 3. 從 source 拉 title（best-effort）
    title = "AI 自動生成 SOP"
    if pc_id:
        cur = await db_module._conn.execute(
            "SELECT brand, model FROM problem_cards WHERE id = %s::uuid",
            (pc_id,),
        )
        row = await cur.fetchone()
        if row:
            title = f"{row[0] or '未知品牌'} {row[1] or ''} 處置流程".strip()

    # 4. 把 draft_content 包成單 step（後續可改 LLM 多 step output）
    steps_json = json.dumps([
        {"order": 1, "title": "處置步驟", "description": draft_content[:2000]}
    ])

    # 5. INSERT + 自動 doc number
    cur = await db_module._conn.execute(
        "INSERT INTO sop_drafts "
        "  (source_problem_card_id, title, steps, status, model_version, "
        "   confidence_score, tenant_id, document_number) "
        "VALUES (%s, %s, %s::jsonb, 'pending_review', %s, %s, %s::uuid, "
        "        generate_doc_number('SOP', 'doc_seq_sop')) "
        "RETURNING id",
        (
            pc_id, title, steps_json, model_version, confidence_score, tenant_id,
        ),
    )
    new_row = await cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert SOP draft", 500)
    new_draft_id = str(new_row[0])

    draft = await get_draft(tenant_id=tenant_id, draft_id=new_draft_id)
    return draft, True


async def review_draft(
    *,
    tenant_id: str,
    draft_id: str,
    decision: str,
    comment: str | None,
    reviewer_id: str | None,
) -> dict:
    """初審決策：approve / reject。

    僅允許 pending_review → approved / rejected。
    其他狀態回 409 Conflict（含已 approved / rejected / published）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if decision not in ("approve", "reject"):
        raise ApiError("VALIDATION_ERROR", "decision must be approve or reject", 422)

    cur = await db_module._conn.execute(
        "SELECT status FROM sop_drafts "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)

    current = (row[0] or "").lower()
    if current != "pending_review":
        raise ApiError(
            "CONFLICT",
            f"Cannot review draft in status '{current}'; only 'pending_review' is allowed",
            409,
        )

    next_status = "approved" if decision == "approve" else "rejected"
    cur = await db_module._conn.execute(
        f"UPDATE sop_drafts "
        f"SET status = %s, "
        f"    reviewed_by = %s::uuid, "
        f"    review_comment = %s, "
        f"    reviewed_at = NOW() "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid AND status = 'pending_review' "
        f"RETURNING {_SELECT_COLUMNS}",
        (next_status, reviewer_id, comment, draft_id, tenant_id),
    )
    updated = await cur.fetchone()
    if not updated:
        # 競態：其他請求剛把 status 移走 → 視為 409
        raise ApiError(
            "CONFLICT",
            "SOP draft was modified concurrently; please retry",
            409,
        )
    return _row_to_dict(updated)


async def adopt_draft(
    *,
    tenant_id: str,
    draft_id: str,
    target_case_id: str | None,
    approver_id: str | None,
) -> dict:
    """採納 approved 草稿 → 入庫成為 case_entries 一筆，並把 sop_drafts 狀態推進為 published。

    回傳值為新建（或更新）的 case_entry，shape 對齊 CaseEntryEnvelope.data。
    僅允許 approved → published。其他狀態回 409。

    target_case_id 暫不支援（更新既有案例的 pipeline 尚未開放）；
    若呼叫方提供，回 422，避免靜默忽略造成意外覆蓋。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if target_case_id is not None:
        raise ApiError(
            "VALIDATION_ERROR",
            "target_case_id is not supported in this phase; only fresh adoption is allowed",
            422,
        )

    cur = await db_module._conn.execute(
        "SELECT status, title, COALESCE(applicable_conditions, ''), steps, "
        "       COALESCE(notes, '') "
        "FROM sop_drafts "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)

    current_status = (row[0] or "").lower()
    if current_status != "approved":
        raise ApiError(
            "CONFLICT",
            f"Cannot adopt draft in status '{current_status}'; only 'approved' is allowed",
            409,
        )

    title: str = row[1] or ""
    conditions: str = row[2] or ""
    raw_steps = row[3]
    notes: str = row[4] or ""

    # 把 steps + conditions + notes 攤平成 case_entries.solution（純文字），
    # 後續編輯人員可在 KB 案例頁微調。
    coerced = _coerce_steps(raw_steps)
    bullets = "\n".join(
        f"{s['order']}. {s['title']}：{s['description']}".rstrip("：") for s in coerced
    ) or "（無步驟）"
    solution_parts = [bullets]
    if notes:
        solution_parts.append(f"\n注意事項：{notes}")
    solution = "\n".join(solution_parts).strip()
    problem_description = conditions or title

    new_case_id = str(uuid.uuid4())
    # CaseEntry.brand 在 OpenAPI 上是必填字串；SOP 草稿目前無 brand 欄位 →
    # 採納時填入「未指定」placeholder，提示管理員後續至案例庫編輯補齊。
    cur = await db_module._conn.execute(
        "INSERT INTO case_entries "
        "(id, tenant_id, title, problem_description, solution, "
        " brand, model, tags, verified, embedding_status, "
        " source, approved_by, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, "
        "        %s, NULL, ARRAY[]::TEXT[], TRUE, 'processing', "
        "        'sop_approved', %s::uuid, TRUE) "
        "RETURNING id, title, problem_description, solution, brand, model, "
        "          COALESCE(tags, ARRAY[]::TEXT[]) AS tags, "
        "          COALESCE(verified, FALSE) AS verified, "
        "          COALESCE(embedding_status, 'processing') AS embedding_status, "
        "          created_at, updated_at",
        (
            new_case_id,
            tenant_id,
            title,
            problem_description,
            solution,
            "未指定",
            approver_id,
        ),
    )
    case_row = await cur.fetchone()
    if not case_row:
        raise ApiError("DB_ERROR", "Failed to insert case_entry", 500)

    # 標記 sop_draft 已發布並掛上 case_entry_id（含再次的 status guard 防競態）
    upd = await db_module._conn.execute(
        "UPDATE sop_drafts "
        "SET status = 'published', "
        "    published_as_case_entry_id = %s::uuid, "
        "    reviewed_at = COALESCE(reviewed_at, NOW()) "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND status = 'approved'",
        (new_case_id, draft_id, tenant_id),
    )
    if upd.rowcount == 0:
        # 草稿在 INSERT case_entry 之間被別的人改走 → 回 409
        # 注：autocommit 模式下 case_entry 已成立；對使用者而言，最安全的訊號是
        # 拒絕本次 adopt 並請其手動覆核新建立的 case_entry。
        raise ApiError(
            "CONFLICT",
            "SOP draft status changed during adoption; manual reconciliation needed",
            409,
        )

    return {
        "id": str(case_row[0]),
        "title": case_row[1],
        "problem_description": case_row[2],
        "solution": case_row[3],
        "brand": case_row[4],
        "model": case_row[5],
        "tags": list(case_row[6] or []),
        "verified": bool(case_row[7]),
        "embedding_status": case_row[8] or "processing",
        "created_at": case_row[9].isoformat() if case_row[9] else None,
        "updated_at": case_row[10].isoformat() if case_row[10] else None,
    }
