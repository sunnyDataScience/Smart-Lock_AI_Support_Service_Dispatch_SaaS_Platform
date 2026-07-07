"""CR-0032 報價引擎 service（Phase A）。

報價主表狀態機 + 從 CR-0034 catalog 帶價 + 送客戶凍結 snapshot。
數值走 mock 主檔（CR-0034 / 決議 5）；核准門檻/訂金/正式價待 esales Q-01~Q-12。

狀態機：draft → pending_approval → approved → sent → accepted | rejected | expired | superseded
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import public_token

logger = logging.getLogger("api.quote_engine_service")

# 客戶端報價查看 public_token TTL fallback（無 expiry_at 時）；正常以 quote.expiry_at 為準
_VIEW_TOKEN_FALLBACK_DAYS = 7

# 允許的狀態轉換（action → (from_states, to_state)）
_TRANSITIONS = {
    "submit":  ({"draft"}, "pending_approval"),
    "approve": ({"pending_approval"}, "approved"),
    "reject":  ({"pending_approval"}, "rejected"),
    "send":    ({"approved", "draft"}, "sent"),  # draft 可直送（免核門檻內，門檻 esales Q-11 待定）
    "accept":  ({"sent"}, "accepted"),
    "decline": ({"sent"}, "rejected"),
}

# 有效期（BR-M04-05）：一般 14d、急件 3d（CR-0044 已知規格；以下為 config fallback 預設）
_VALIDITY_DAYS_NORMAL = 14
_VALIDITY_DAYS_URGENT = 3


async def _validity_days(urgent: bool) -> int:
    """CR-0044：有效期讀 M18 config quote_validity_policy（缺則 fallback 14/3，不寫死）。"""
    from services import config_m18_service

    cfg = await config_m18_service.read_global_value(namespace="quote_validity_policy")
    if isinstance(cfg, dict):
        key = "urgent_days" if urgent else "normal_days"
        try:
            return int(cfg.get(key, _VALIDITY_DAYS_URGENT if urgent else _VALIDITY_DAYS_NORMAL))
        except (TypeError, ValueError):
            pass
    return _VALIDITY_DAYS_URGENT if urgent else _VALIDITY_DAYS_NORMAL

# 核准門檻（fallback 預設；正式值 esales Q-11，CR-0046 入 config discount_policy）
_APPROVAL_THRESHOLD = 10000.0


async def _approval_threshold() -> float:
    """CR-0046：報價核准門檻讀 M18 config discount_policy（fallback 10000，不寫死）。"""
    from services import config_m18_service

    cfg = await config_m18_service.read_global_value(namespace="discount_policy")
    if isinstance(cfg, dict):
        try:
            return float(cfg.get("approval_threshold", _APPROVAL_THRESHOLD))
        except (TypeError, ValueError):
            pass
    return _APPROVAL_THRESHOLD


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


def _quote_number(work_order_number: str | None, version) -> str | None:
    """CR-0095：可讀報價編號 = {公單號}-Q{版本}（如 TP-000001-Q1）；無公單號則 None（前端 fallback 顯 UUID 短碼）。"""
    if work_order_number:
        return f"{work_order_number}-Q{int(version)}"
    return None


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


async def create_quote(
    *, tenant_id: str, work_order_id: str, created_by: str | None = None,
    urgent: bool = False,
) -> dict:
    """從 work_order 建 draft 報價（version 沿同工單遞增，有效期 BR-M04-05）。"""
    conn = await _conn()
    # 取 problem_card_id（沿 work_order）
    pc = await (await conn.execute(
        "SELECT problem_card_id FROM work_orders WHERE id = %s::uuid", (work_order_id,)
    )).fetchone()
    if not pc:
        raise ApiError("NOT_FOUND", "work order not found", 404)
    days = await _validity_days(urgent)
    expiry = datetime.now(timezone.utc) + timedelta(days=days)
    # CR-0095 UX2：version 沿同工單遞增（DB default 恆為 1，會讓可讀編號 TP-000001-Qn 撞號）
    next_version = (await (await conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM quote WHERE work_order_id = %s::uuid",
        (work_order_id,),
    )).fetchone())[0]
    row = await (await conn.execute(
        "INSERT INTO quote (work_order_id, problem_card_id, state, expiry_at, tenant_id, created_by, version) "
        "VALUES (%s::uuid, %s, 'draft', %s, %s::uuid, %s, %s) RETURNING id",
        (work_order_id, pc[0], expiry, tenant_id, created_by, next_version),
    )).fetchone()
    return await get_quote(quote_id=str(row[0]), tenant_id=tenant_id, include_cost=True)


async def add_line(
    *, tenant_id: str, quote_id: str, quantity: int = 1,
    service_code: str | None = None, material_code: str | None = None,
    item_name: str | None = None,
) -> dict:
    """加一筆報價項，價格從 CR-0034 catalog 帶（mock）。"""
    conn = await _conn()
    q = await (await conn.execute("SELECT state, work_order_id FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not q:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if q[0] not in ("draft", "pending_approval"):
        raise ApiError("STATE_CONFLICT", f"cannot add line to quote in '{q[0]}'", 409)

    if service_code:
        cat = await (await conn.execute(
            "SELECT service_name, internal_base_cost, suggested_customer_price, 'labor' "
            "FROM service_catalog WHERE service_code = %s", (service_code,))).fetchone()
        category = "labor"
    elif material_code:
        cat = await (await conn.execute(
            "SELECT material_name, internal_cost, suggested_price, 'material' "
            "FROM material_catalog WHERE material_code = %s", (material_code,))).fetchone()
        category = "material"
    else:
        raise ApiError("VALIDATION_ERROR", "service_code or material_code required", 422)
    if not cat:
        raise ApiError("NOT_FOUND", "catalog item not found", 404)

    name = item_name or cat[0]
    unit_cost = cat[1] or 0
    cust_price = cat[2] or 0
    await conn.execute(
        "INSERT INTO quote_line_items (quote_id, work_order_id, tenant_id, item_name, category, "
        "  unit_price, quantity, customer_price, is_mock, service_code, material_code) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, TRUE, %s, %s)",
        (quote_id, q[1], tenant_id, name, category, unit_cost, quantity, cust_price,
         service_code, material_code),
    )
    await _recompute_total(quote_id)
    return await get_quote(quote_id=quote_id, tenant_id=tenant_id, include_cost=True)


async def remove_line(*, tenant_id: str, quote_id: str, line_id: str) -> dict:
    """移除一筆報價項（add_line 的反向；僅 draft / pending_approval 可改，移除後重算總額）。"""
    conn = await _conn()
    q = await (await conn.execute("SELECT state FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not q:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if q[0] not in ("draft", "pending_approval"):
        raise ApiError("STATE_CONFLICT", f"cannot remove line from quote in '{q[0]}'", 409)
    cur = await conn.execute(
        "DELETE FROM quote_line_items WHERE id = %s::uuid AND quote_id = %s::uuid",
        (line_id, quote_id),
    )
    if cur.rowcount == 0:
        raise ApiError("NOT_FOUND", "line item not found", 404)
    await _recompute_total(quote_id)
    return await get_quote(quote_id=quote_id, tenant_id=tenant_id, include_cost=True)


async def delete_quote(*, tenant_id: str, quote_id: str) -> None:
    """硬刪整張報價單（子表 lines/approval/snapshot 皆 ON DELETE CASCADE）。
    僅 draft / pending_approval 可刪；已送客戶/接受的報價為對外紀錄，不可刪（請用 reject）。"""
    conn = await _conn()
    q = await (await conn.execute(
        "SELECT state FROM quote WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (quote_id, tenant_id),
    )).fetchone()
    if not q:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if q[0] not in ("draft", "pending_approval"):
        raise ApiError(
            "STATE_CONFLICT",
            f"cannot delete quote in '{q[0]}'；已送客戶/接受的報價為紀錄，請改用 reject",
            409,
        )
    await conn.execute("DELETE FROM quote WHERE id = %s::uuid", (quote_id,))


async def _recompute_total(quote_id: str) -> None:
    conn = await _conn()
    total = (await (await conn.execute(
        "SELECT COALESCE(SUM(customer_price * quantity), 0) FROM quote_line_items WHERE quote_id = %s::uuid",
        (quote_id,))).fetchone())[0]
    await conn.execute(
        "UPDATE quote SET total_amount = %s, updated_at = NOW() WHERE id = %s::uuid", (total, quote_id))


async def get_quote(*, tenant_id: str, quote_id: str, include_cost: bool) -> dict:
    conn = await _conn()
    # CR-0095 UX：join work_orders 帶出友善公單號（TP-000001）+ 客戶名供前端顯示
    r = await (await conn.execute(
        "SELECT q.id, q.work_order_id, q.version, q.state, q.total_amount, q.deposit_required, "
        "       q.expiry_at, q.snapshot_hash, q.is_mock, q.created_at, "
        "       wo.document_number, wo.customer_name "
        "FROM quote q LEFT JOIN work_orders wo ON q.work_order_id = wo.id "
        "WHERE q.id = %s::uuid AND (q.tenant_id = %s::uuid OR q.tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone()
    if not r:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    lines_rows = await (await conn.execute(
        "SELECT id, item_name, category, unit_price, quantity, customer_price, service_code, material_code "
        "FROM quote_line_items WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    lines = []
    for lr in lines_rows:
        line = {"id": str(lr[0]), "item_name": lr[1], "category": lr[2], "quantity": int(lr[4]),
                "customer_price": _dec(lr[5]), "service_code": lr[6], "material_code": lr[7]}
        if include_cost:
            line["unit_price"] = _dec(lr[3])
        lines.append(line)
    return {
        "id": str(r[0]), "work_order_id": str(r[1]) if r[1] else None, "version": int(r[2]),
        "state": r[3], "total_amount": _dec(r[4]), "deposit_required": _dec(r[5]),
        "expiry_at": r[6].isoformat() if r[6] else None, "snapshot_hash": r[7],
        "is_mock": bool(r[8]), "lines": lines, "cost_visible": include_cost,
        "work_order_number": r[10], "customer_name": r[11],
        "quote_number": _quote_number(r[10], r[2]),  # CR-0095 可讀編號 TP-000001-Q1
    }


async def list_quotes(*, tenant_id: str, limit: int = 100) -> list[dict]:
    """CR-0095 UX：列出租戶所有報價（含公單號 TP + 客戶名 + 狀態），最新在前。

    供 /admin/quotes 報價列表 dashboard 用，免手貼 UUID。不含明細/成本（列表輕量）。
    """
    conn = await _conn()
    rows = await (await conn.execute(
        "SELECT q.id, q.work_order_id, wo.document_number, q.state, q.total_amount, "
        "       q.created_at, wo.customer_name, q.version "
        "FROM quote q LEFT JOIN work_orders wo ON q.work_order_id = wo.id "
        "WHERE q.tenant_id = %s::uuid "
        "ORDER BY q.created_at DESC LIMIT %s",
        (tenant_id, limit))).fetchall()
    return [
        {"id": str(x[0]), "work_order_id": str(x[1]) if x[1] else None,
         "work_order_number": x[2], "state": x[3], "total_amount": _dec(x[4]),
         "created_at": x[5].isoformat() if x[5] else None, "customer_name": x[6],
         "quote_number": _quote_number(x[2], x[7])}  # CR-0095 可讀編號
        for x in rows
    ]


async def transition(
    *, tenant_id: str, quote_id: str, action: str, actor_id: str | None = None,
    comment: str | None = None,
) -> dict:
    """狀態機轉換。send → 凍結 pricing snapshot；approve/reject → 記 quote_approval。"""
    if action not in _TRANSITIONS:
        raise ApiError("VALIDATION_ERROR", f"unknown action '{action}'", 422)
    conn = await _conn()
    from_states, to_state = _TRANSITIONS[action]
    cur = await (await conn.execute("SELECT state FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not cur:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if cur[0] not in from_states:
        raise ApiError("STATE_CONFLICT", f"cannot {action} quote in '{cur[0]}'", 409)

    # 核准門檻（esales Q-11）：總額超門檻不可從 draft 直送，須先 submit→approve。
    # CR-0046：門檻讀 M18 config discount_policy.approval_threshold（mock 範例待業主確認，可動態改）。
    if action == "send" and cur[0] == "draft":
        threshold = await _approval_threshold()
        tot = await (await conn.execute(
            "SELECT COALESCE(total_amount, 0) FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if float(tot[0]) > threshold:
            raise ApiError(
                "APPROVAL_REQUIRED",
                f"報價總額超過 {threshold:.0f}（discount_policy 門檻），須先送審核准",
                409,
            )

    # 過期檢查：sent 後逾 expiry 不可 accept
    if action == "accept":
        exp = await (await conn.execute("SELECT expiry_at FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if exp[0] and exp[0] < datetime.now(timezone.utc):
            await conn.execute("UPDATE quote SET state = 'expired', updated_at = NOW() WHERE id = %s::uuid", (quote_id,))
            raise ApiError("STATE_CONFLICT", "quote expired", 409)

    await conn.execute("UPDATE quote SET state = %s, updated_at = NOW() WHERE id = %s::uuid", (to_state, quote_id))

    # CR-0117 S1：報價總額回寫工單 estimated_price —— 先前此欄全系統無寫入點（死欄位），
    # 師傅端首頁今日/本週/本月「預估收入」SUM 它永遠 NT$ 0、sla_monitor quote_expiring
    # （estimated_price 非空 + status=created = 已報價待客戶確認）永不觸發。
    # 寫入點 = send（送客戶當下價格已凍結快照，quote_expiring 語意正確起算）；
    # accept 再冪等重寫一次作保險（改單重送情境同步最終承諾額）。total NULL（無明細）不寫。
    # - tenant 雙重限定：transition() 既有查詢以 quote id 直查不過濾租戶（既有缺口，
    #   另案處理），本回寫自帶 tenant 條件，不讓新寫入面繼承跨租戶污染財務欄位的風險。
    # - fail-soft：本回寫夾在「state 已 commit（autocommit）」與下游快照/發票/推播之間，
    #   若在此拋錯，重試會被狀態機 409 擋死、下游永久跳過 —— estimated_price 屬可回填的
    #   派生欄位，失敗只 log 不阻斷主流程。
    if action in ("send", "accept"):
        try:
            await conn.execute(
                "UPDATE work_orders wo SET estimated_price = q.total_amount, updated_at = NOW() "
                "FROM quote q "
                "WHERE q.id = %s::uuid AND wo.id = q.work_order_id "
                "  AND q.total_amount IS NOT NULL "
                "  AND wo.tenant_id = %s::uuid "
                "  AND (q.tenant_id = %s::uuid OR q.tenant_id IS NULL)",
                (quote_id, tenant_id, tenant_id),
            )
        except Exception:  # noqa: BLE001 — 派生欄位回寫失敗不可卡死 transition 下游
            logger.exception(
                "estimated_price 回寫失敗（可用回填修復，不阻斷 %s）quote=%s", action, quote_id,
            )

    if action in ("approve", "reject"):
        await conn.execute(
            "INSERT INTO quote_approval (quote_id, approver_id, decision, comment) "
            "VALUES (%s::uuid, %s::uuid, %s, %s)",
            (quote_id, actor_id, "approved" if action == "approve" else "rejected", comment))
    if action == "send":
        await _freeze_snapshot(quote_id, tenant_id)
    # 客戶接受 → best-effort 開立客戶應收發票（CR-0035；work_order_id UNIQUE 天然冪等，
    # 失敗不阻斷 accept —— 報價接受是客戶動作，發票開立是下游帳務，解耦）
    if action == "accept":
        try:
            from services import invoice_service
            inv = await invoice_service.create_from_quote(tenant_id=tenant_id, quote_id=quote_id)
            logger.info("quote accepted → invoice %s", inv.get("id"))
        except Exception as exc:  # noqa: BLE001 — best-effort 解耦：開票失敗不阻斷客戶接受報價
            # ERROR 級（可告警）：金流斷層需人工補開 —— 後台 POST .../accounting/invoices:from-quote
            logger.error("quote %s accepted but invoice creation FAILED (manual from-quote needed): %s",
                         quote_id, exc)

    result = await get_quote(quote_id=quote_id, tenant_id=tenant_id, include_cost=True)
    # 送客戶 → 一併鑄客戶端查看連結（stateless public_token，quote_view purpose）
    if action == "send":
        link = await mint_view_token(tenant_id=tenant_id, quote_id=quote_id)
        result = {**result, **link}
        # CR-0095：送單同時推 LINE 報價給客戶（含 postback 同意/拒絕 + 網頁 fallback）。
        # best-effort：複用 CR-0017 outbox，worker 從 reference 反查 LINE uid；
        # 失敗不阻斷送單（與 assign/complete 推送一致，只露對客價不含內部成本）。
        try:
            from services import line_push_outbox_service

            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="quote_proposal",
                payload={
                    "quote_id": result["id"],
                    "work_order_id": result.get("work_order_id"),
                    "items": [
                        {"name": ln.get("item_name"),
                         "customer_price": ln.get("customer_price"),
                         "quantity": ln.get("quantity")}
                        for ln in result.get("lines", [])
                    ],
                    "total": result.get("total_amount"),
                    "public_token": link.get("public_token"),
                },
                reference_id=quote_id,
                reference_table="quote",
            )
        except Exception:  # noqa: BLE001 — 推送失敗不阻斷送單
            logger.exception("outbox enqueue quote_proposal failed (non-fatal) quote=%s", quote_id)
    # CR-0095：把報價事件（發送 / 客戶同意 / 客戶拒絕）同步到對話管理，best-effort。
    if action in ("send", "accept", "decline"):
        try:
            await _log_quote_event_to_conversation(quote_id, action, result)
        except Exception:  # noqa: BLE001 — 事件記錄不可阻斷主流程
            logger.exception("quote event → conversation note failed (non-fatal) quote=%s", quote_id)
    return result


async def _resolve_conversation_id(quote_id: str) -> str | None:
    """quote → work_order → problem_card → conversation_id（同步報價事件到對話用）。"""
    conn = await _conn()
    row = await (await conn.execute(
        "SELECT pc.conversation_id FROM quote q "
        "JOIN work_orders wo ON q.work_order_id = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "WHERE q.id = %s::uuid", (quote_id,))).fetchone()
    return str(row[0]) if row and row[0] else None


async def _log_quote_event_to_conversation(quote_id: str, action: str, result: dict) -> None:
    """CR-0095：報價事件 → 對話管理系統訊息。conv 查無則略過。"""
    conv_id = await _resolve_conversation_id(quote_id)
    if not conv_id:
        return
    from services import conversation_service

    label = result.get("quote_number") or f"報價 {quote_id[:8]}"
    total = result.get("total_amount")
    # CR-0117：total 為 NULL（無明細）時不可直接內插 —— 曾產生「總額 NT$ None」外洩給客服畫面
    total_label = f"總額 NT$ {total}" if total not in (None, "") else "金額未定"
    if action == "send":
        note = f"🧾 已發送報價單 {label}（{total_label}）給客戶，等待客戶於 LINE 回覆。"
    elif action == "accept":
        note = f"✅ 客戶已同意報價單 {label}（{total_label}），可進行派工。"
    else:  # decline
        note = f"❌ 客戶不同意報價單 {label}，請客服調整後重送。"
    await conversation_service.append_event_note(conversation_id=conv_id, content=note)


def _ttl_days_from(expiry: datetime | None) -> int:
    """token TTL 對齊報價有效期；無 expiry 則 fallback。至少 1 天。

    用小時粒度 ceil（非 .days 整日截斷）—— 報價剩 6h 時應給能完整覆蓋的天數，
    避免 token 反而比報價長命；已過期報價（remaining ≤ 0）給最小 1 天供唯讀查看。
    """
    if not expiry:
        return _VIEW_TOKEN_FALLBACK_DAYS
    remaining_days = (expiry - datetime.now(timezone.utc)).total_seconds() / 86400
    return max(1, math.ceil(remaining_days))


async def mint_view_token(*, tenant_id: str, quote_id: str) -> dict:
    """鑄客戶端報價查看連結（已送客戶的報價才有意義）。

    複用 public_token（HMAC stateless，purpose=quote_view），不另建 token 表
    —— 報價快照已凍結（ADR-0064），token 只是無狀態的查看授權。
    """
    conn = await _conn()
    r = await (await conn.execute(
        "SELECT state, expiry_at FROM quote WHERE id = %s::uuid "
        "AND (tenant_id = %s::uuid OR tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone()
    if not r:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if r[0] not in ("sent", "accepted", "rejected", "expired"):
        raise ApiError("STATE_CONFLICT", f"quote in '{r[0]}' has no customer link (send it first)", 409)
    token = public_token.generate_token(
        quote_id, purpose="quote_view", ttl_days=_ttl_days_from(r[1]), tenant_id=tenant_id)
    # token_expires_at 明確命名（token 的過期，非報價的 expiry_at），避免與 get_quote 欄位混淆
    return {"public_token": token, "public_path": f"/quotes/{token}",
            "token_expires_at": r[1].isoformat() if r[1] else None}


async def resolve_customer_line_uid(*, tenant_id: str, quote_id: str) -> str | None:
    """反查此報價對應客戶的 LINE userId（quote→work_order→problem_card→conversation→user）。

    與 line_push_outbox_worker._resolve_line_uid 的 quote 路徑一致；查無回 None。
    """
    conn = await _conn()
    row = await (await conn.execute(
        "SELECT u.line_user_id "
        "FROM quote q "
        "JOIN work_orders wo ON q.work_order_id = wo.id "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE q.id = %s::uuid AND (q.tenant_id = %s::uuid OR q.tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone()
    return row[0] if row else None


async def customer_respond_to_quote(
    *, tenant_id: str, quote_id: str, line_user_id: str, decision: str,
) -> dict:
    """CR-0095：客戶經 LINE postback 同意/拒絕報價（agent gateway → internal 端點呼叫）。

    安全：先驗證 line_user_id 確實是此報價對應客戶（防客戶 A 同意客戶 B 的報價）；
    不符 → 403。再走狀態機 transition（accept→accepted / reject→decline→rejected）。
    decision='accept'|'reject'。
    """
    if decision not in {"accept", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)
    owner = await resolve_customer_line_uid(tenant_id=tenant_id, quote_id=quote_id)
    if owner is None:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if owner != line_user_id:
        # 不洩露歸屬細節，但 log 供稽核
        logger.warning("quote %s respond denied: line_user mismatch", quote_id)
        raise ApiError("FORBIDDEN", "this LINE user does not own the quote", 403)
    action = "accept" if decision == "accept" else "decline"
    result = await transition(tenant_id=tenant_id, quote_id=quote_id, action=action)
    return {"quote_id": result["id"], "state": result["state"], "decision": decision}


async def _freeze_snapshot(quote_id: str, tenant_id: str) -> None:
    """送客戶當下凍結價格規則 + 算 hash（報價快照不可變）。"""
    conn = await _conn()
    lines = await (await conn.execute(
        "SELECT item_name, category, customer_price, quantity FROM quote_line_items "
        "WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    snap = {"lines": [{"name": l[0], "cat": l[1], "price": _dec(l[2]), "qty": int(l[3])} for l in lines]}
    blob = json.dumps(snap, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    await conn.execute(
        "INSERT INTO pricing_rule_snapshot (quote_id, rules_json, hash) VALUES (%s::uuid, %s::jsonb, %s)",
        (quote_id, blob, h))
    await conn.execute("UPDATE quote SET snapshot_hash = %s, updated_at = NOW() WHERE id = %s::uuid", (h, quote_id))
