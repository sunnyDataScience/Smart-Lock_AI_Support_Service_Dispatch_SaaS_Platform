"""LINE Flex message builders — CR-0017 HD-3。

Stage 2 階段：先回 TextMessage placeholder（rich text 含 token / proposal_id），
讓 worker→push 鏈路可端到端跑通；Stage 3 將每個 builder 升級為 real Flex
carousel/bubble（含按鈕 → postback → customer-confirm/reject）。

Builder 介面：`(payload: dict) -> list` 回傳 LINE Messaging API 接受的
messages list。Stage 2 回 `[TextMessage(text=...)]`；Stage 3 改回
`[FlexMessage(alt_text=..., contents=...)]`。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("api.templates.line_flex")


def _make_text_message(text: str) -> dict:
    """產生 LINE Messaging API v3 TextMessage dict。

    Worker 端把 dict 轉成 SDK 物件（TextMessage(**dict)）；目前 placeholder
    階段先用 dict 簡化。Stage 3 升 Flex 時改回 builder 用 SDK objects。
    """
    return {"type": "text", "text": text[:5000]}  # LINE 單訊息 5000 字限


def render_reschedule_proposal(payload: dict) -> list[dict]:
    """Flow 11 改約提案 placeholder。

    payload 對應 outbox.payload schema (work_order_service.propose_reschedule_v2
    enqueue 寫入):
      - proposal_id (uuid str)
      - work_order_id (uuid str)
      - proposed_slots (list of {start, end?})
      - message_to_customer (str | None)

    Stage 3 將升級為 Flex carousel：每個 slot 一個 bubble + postback button
    (action=reschedule:confirm, payload=proposal_id+slot_idx)，外加「都不方便」
    bubble (action=reschedule:reject)。
    """
    proposal_id = payload.get("proposal_id", "?")
    wo_id = payload.get("work_order_id", "?")
    slots = payload.get("proposed_slots", [])
    msg = payload.get("message_to_customer") or "請問哪個時段方便施工？"

    lines = [
        f"📅 改約時段請選擇（工單 {str(wo_id)[:8]}）",
        "",
        msg,
        "",
        "可選時段：",
    ]
    for i, slot in enumerate(slots, 1):
        start = slot.get("start", "?")
        end = slot.get("end")
        lines.append(f"{i}. {start}" + (f" ~ {end}" if end else ""))
    lines.append("")
    lines.append(f"（proposal: {proposal_id[:8]}）")

    return [_make_text_message("\n".join(lines))]


def render_scope_change_proposal(payload: dict) -> list[dict]:
    """Flow 3 範圍變更 proposal placeholder。

    payload schema (work_order_service.record_scope_change enqueue):
      - scope_change_id (uuid str)
      - work_order_id (uuid str)
      - reason (str)
      - items (list of {name, unit_price, quantity})
      - total_estimate (str | None)
      - public_token (str | None) — 7-day TTL，連 web/track 用

    Stage 3 升級：Flex bubble 含 reason / items 列表 / 估價 + 兩個 button
    (action=scope_change:accept|reject, payload=scope_change_id)。token 嵌
    button URI 跳 web/track/scope-change/{token} 作 fallback。
    """
    sc_id = payload.get("scope_change_id", "?")
    wo_id = payload.get("work_order_id", "?")
    reason = payload.get("reason", "?")
    items = payload.get("items", [])
    total = payload.get("total_estimate") or "—"
    token = payload.get("public_token")

    lines = [
        f"⚠️ 工單範圍變更通知（{str(wo_id)[:8]}）",
        "",
        f"變更原因：{reason}",
        "",
        "新增項目：",
    ]
    for it in items:
        nm = it.get("name", "?")
        qty = it.get("quantity", 1)
        price = it.get("unit_price", "?")
        lines.append(f"  • {nm} ×{qty} @ {price}")
    lines.append(f"\n預估金額：{total}")
    if token:
        lines.append(f"\n詳情/確認：https://track.example/scope/{token[:16]}...")
    lines.append(f"\n（scope: {sc_id[:8]}）")

    return [_make_text_message("\n".join(lines))]


def render_schedule_conflict(payload: dict) -> list[dict]:
    """Flow 14 排班衝突 placeholder。

    payload schema (_detect_schedule_conflict_and_publish enqueue):
      - conflicting_wo_ids (list of uuid str)
      - technician_id (uuid str)
      - window_hours (int)
      - scheduled_at (iso str)

    Stage 3 升級：Flex bubble 給 admin（非客戶）— 紅色警示 + 衝突 wo 列表 +
    跳轉「派工佇列」鈕。本通知本質是 admin-facing 而非 customer-facing。
    """
    tech_id = payload.get("technician_id", "?")
    win = payload.get("window_hours", 2)
    sched = payload.get("scheduled_at", "?")
    conflicts = payload.get("conflicting_wo_ids", [])

    lines = [
        "⚠️ 派工衝突警示",
        "",
        f"技師 {str(tech_id)[:8]} 在 ±{win}hr 視窗有衝突排班",
        f"排定時間：{sched}",
        f"衝突工單數：{len(conflicts)}",
    ]
    for wid in conflicts[:5]:
        lines.append(f"  • {str(wid)[:8]}")
    if len(conflicts) > 5:
        lines.append(f"  ...等 {len(conflicts)} 筆")

    return [_make_text_message("\n".join(lines))]


# Dispatch table（worker 用 push_kind 路由）— 對齊
# line_push_outbox_service.PushKind Literal
BUILDERS: dict[str, Callable[[dict], list[dict]]] = {
    "reschedule_proposal": render_reschedule_proposal,
    "scope_change_proposal": render_scope_change_proposal,
    "schedule_conflict": render_schedule_conflict,
}


def build_messages(push_kind: str, payload: dict) -> list[dict] | None:
    """Worker entry：dispatch by push_kind → render 訊息 list。

    回傳 None 若 push_kind 未支援（worker 應標 status='dead'）。
    """
    builder = BUILDERS.get(push_kind)
    if not builder:
        logger.warning("unknown push_kind: %s", push_kind)
        return None
    try:
        return builder(payload)
    except Exception:  # noqa: BLE001
        logger.exception("flex builder %s failed", push_kind)
        return None
