"""LINE Flex message builders — CR-0017 HD-3 (Stage 3 升級為 real Flex)。

Stage 3：3 個 builder 改回 FlexMessage carousel/bubble + postback button。

Builder 介面：`(payload: dict) -> list[dict]` 回 LINE Messaging API
messages list (dict 形式，worker 端轉 SDK obj)。

Stage 3 起 messages 型別包含：
  - {"type": "text", "text": ...}（fallback）
  - {"type": "flex", "altText": ..., "contents": {...}}（主路徑）

postback data 格式（短碼節省 LINE 300/1000 字限）：
  - "r:c|<proposal_id>|<slot_idx>" — reschedule confirm
  - "r:r|<proposal_id>"             — reschedule reject
  - "s:a|<scope_change_id>"         — scope_change accept
  - "s:r|<scope_change_id>"         — scope_change reject
  - schedule_conflict 為 admin-only，無 postback（含 URI button 跳 web）
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger("api.templates.line_flex")

# Web 連結 fallback 用（scope_change 的 public_token 跳 web/track）
_WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://lock-ai-web.example.com")


def _make_text_message(text: str) -> dict:
    """fallback：純文字訊息（Flex 建構失敗時 worker 仍能送）。"""
    return {"type": "text", "text": text[:5000]}


def _make_flex_message(alt_text: str, contents: dict) -> dict:
    """產生 FlexMessage dict（worker 端轉 FlexMessage(alt_text, contents=FlexContainer)）。"""
    return {"type": "flex", "altText": alt_text[:400], "contents": contents}


def render_reschedule_proposal(payload: dict) -> list[dict]:
    """Flow 11 改約提案 — Flex carousel of slot bubbles + 都不方便 bubble。

    payload schema (work_order_service.propose_reschedule_v2 enqueue):
      - proposal_id (uuid str)
      - work_order_id (uuid str)
      - proposed_slots (list of {start, end?})
      - message_to_customer (str | None)

    每個 slot → bubble 含「選擇此時段」postback。末 bubble 含「都不方便」postback。
    """
    proposal_id = str(payload.get("proposal_id", ""))
    wo_id = str(payload.get("work_order_id", ""))
    slots = payload.get("proposed_slots", []) or []
    msg = payload.get("message_to_customer") or "請問哪個時段方便？"

    if not proposal_id or not slots:
        return [_make_text_message(f"改約提案參數不完整（wo {wo_id[:8]}）")]

    bubbles: list[dict] = []
    for i, slot in enumerate(slots[:3]):  # LINE Flex carousel 上限 12，但業務上限 3
        start = str(slot.get("start", ""))
        end = str(slot.get("end", "")) if slot.get("end") else None
        display = start[:16].replace("T", " ")
        if end:
            display += f"\n～ {end[:16].replace('T', ' ')}"
        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "contents": [{
                    "type": "text",
                    "text": f"時段 {i + 1}",
                    "weight": "bold", "color": "#1DB446", "size": "sm",
                }],
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": display, "wrap": True, "weight": "bold", "size": "md"},
                    {"type": "text", "text": msg, "wrap": True, "size": "xs", "color": "#888888"},
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{
                    "type": "button", "style": "primary", "color": "#1DB446",
                    "action": {
                        "type": "postback",
                        "label": "選擇此時段",
                        "data": f"r:c|{proposal_id}|{i}",
                        "displayText": f"選擇時段 {i + 1}",
                    },
                }],
            },
        })

    # 末 bubble：都不方便
    bubbles.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "❌", "size": "xxl", "align": "center"},
                {"type": "text", "text": "都不方便", "weight": "bold", "align": "center"},
                {"type": "text", "text": "客服將另行聯絡", "wrap": True,
                 "size": "xs", "color": "#888888", "align": "center"},
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "button", "style": "secondary",
                "action": {
                    "type": "postback",
                    "label": "都不方便",
                    "data": f"r:r|{proposal_id}",
                    "displayText": "都不方便",
                },
            }],
        },
    })

    return [_make_flex_message(
        alt_text=f"改約時段提案（工單 {wo_id[:8]}）",
        contents={"type": "carousel", "contents": bubbles},
    )]


def render_scope_change_proposal(payload: dict) -> list[dict]:
    """Flow 3 範圍變更 — Flex bubble 含 reason / items / 估價 + accept/reject + web fallback。

    payload schema (record_scope_change enqueue):
      - scope_change_id (uuid str)
      - work_order_id (uuid str)
      - reason (str)
      - items (list of {name, unit_price, quantity})
      - total_estimate (str | None)
      - public_token (str | None) — 7-day TTL，web/track fallback
    """
    sc_id = str(payload.get("scope_change_id", ""))
    wo_id = str(payload.get("work_order_id", ""))
    reason = str(payload.get("reason") or "技師現場評估後須變更項目")
    items = payload.get("items") or []
    total = payload.get("total_estimate") or "—"
    token = payload.get("public_token")

    if not sc_id:
        return [_make_text_message(f"範圍變更提案參數不完整（wo {wo_id[:8]}）")]

    item_rows: list[dict] = []
    for it in items[:8]:
        nm = str(it.get("name", "?"))[:40]
        qty = it.get("quantity", 1)
        price = it.get("unit_price", "?")
        item_rows.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "text", "text": f"• {nm}", "size": "sm",
                 "color": "#555555", "flex": 4, "wrap": True},
                {"type": "text", "text": f"×{qty}", "size": "sm",
                 "color": "#999999", "flex": 1, "align": "end"},
                {"type": "text", "text": str(price), "size": "sm",
                 "color": "#111111", "flex": 2, "align": "end"},
            ],
        })

    footer_buttons: list[dict] = [
        {
            "type": "button", "style": "primary", "color": "#1DB446", "height": "sm",
            "action": {
                "type": "postback", "label": "同意變更",
                "data": f"s:a|{sc_id}", "displayText": "同意變更",
            },
        },
        {
            "type": "button", "style": "secondary", "height": "sm",
            "action": {
                "type": "postback", "label": "不同意",
                "data": f"s:r|{sc_id}", "displayText": "不同意",
            },
        },
    ]
    if token:
        footer_buttons.append({
            "type": "button", "style": "link", "height": "sm",
            "action": {
                "type": "uri", "label": "查看詳情",
                "uri": f"{_WEB_BASE_URL}/track/scope/{token}",
            },
        })

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": "⚠️ 工單變更通知", "weight": "bold",
                 "color": "#E97600", "size": "md"},
                {"type": "text", "text": f"工單 {wo_id[:8]}", "size": "xs", "color": "#888888"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": "變更原因", "size": "xs", "color": "#999999"},
                {"type": "text", "text": reason, "wrap": True, "size": "sm"},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": "新增項目", "size": "xs", "color": "#999999"},
                *item_rows,
                {"type": "separator", "margin": "md"},
                {"type": "box", "layout": "horizontal",
                 "contents": [
                     {"type": "text", "text": "預估金額", "size": "sm", "color": "#555555"},
                     {"type": "text", "text": str(total), "weight": "bold",
                      "size": "md", "align": "end"},
                 ]},
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": footer_buttons,
        },
    }

    return [_make_flex_message(
        alt_text=f"工單變更通知（{wo_id[:8]}） 預估 {total}",
        contents=bubble,
    )]


def render_schedule_conflict(payload: dict) -> list[dict]:
    """Flow 14 排班衝突 — admin Flex bubble (紅色警示)。

    payload schema (_detect_schedule_conflict_and_publish enqueue):
      - conflicting_wo_ids (list of uuid str)
      - technician_id (uuid str)
      - window_hours (int)
      - scheduled_at (iso str)
    """
    tech_id = str(payload.get("technician_id", ""))
    win = payload.get("window_hours", 2)
    sched = str(payload.get("scheduled_at", ""))
    conflicts = payload.get("conflicting_wo_ids") or []

    conflict_rows: list[dict] = [
        {"type": "text", "text": f"• {str(w)[:8]}", "size": "sm", "color": "#555555"}
        for w in conflicts[:5]
    ]
    if len(conflicts) > 5:
        conflict_rows.append({
            "type": "text", "text": f"...等 {len(conflicts)} 筆",
            "size": "xs", "color": "#999999",
        })

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#DC3545",
            "contents": [{
                "type": "text", "text": "🚨 派工衝突警示",
                "weight": "bold", "color": "#FFFFFF", "size": "md",
            }],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": f"技師 {tech_id[:8]}",
                 "weight": "bold", "size": "sm"},
                {"type": "text",
                 "text": f"在 ±{win}hr 視窗有 {len(conflicts)} 筆衝突",
                 "size": "sm", "color": "#555555"},
                {"type": "text", "text": f"排定：{sched[:16].replace('T', ' ')}",
                 "size": "xs", "color": "#888888"},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": "衝突工單", "size": "xs", "color": "#999999"},
                *conflict_rows,
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "button", "style": "primary", "color": "#DC3545", "height": "sm",
                "action": {
                    "type": "uri", "label": "前往派工佇列",
                    "uri": f"{_WEB_BASE_URL}/admin/dispatch",
                },
            }],
        },
    }

    return [_make_flex_message(
        alt_text=f"派工衝突警示：技師 {tech_id[:8]} 有 {len(conflicts)} 筆衝突",
        contents=bubble,
    )]


def render_work_order_assigned(payload: dict) -> list[dict]:
    """CR-0028 斷點 1 — 派工完成通知客戶（assign_order enqueue）。

    payload schema:
      - work_order_id (uuid str)
      - document_number (str | None) — 公單號（有則顯示，無則略）

    客戶端通知（無 postback，純告知）：已為您安排技師。
    """
    wo_id = str(payload.get("work_order_id", ""))
    doc = payload.get("document_number")
    sub = [{"type": "text", "text": f"工單 {doc}", "size": "xs", "color": "#888888"}] if doc else []
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔧 已為您安排技師", "weight": "bold",
                 "color": "#1DB446", "size": "md"},
                *sub,
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [{
                "type": "text",
                "text": "您的維修工單已指派專業技師，技師將盡快與您聯繫安排到府時間。",
                "wrap": True, "size": "sm",
            }],
        },
    }
    if not wo_id:
        return [_make_text_message("您的維修工單已指派技師，技師將盡快與您聯繫。")]
    return [_make_flex_message(alt_text="已為您安排技師", contents=bubble)]


def render_work_order_accepted(payload: dict) -> list[dict]:
    """CR-0028 斷點 3 — 技師接單通知客戶（accept_order enqueue）。

    payload schema:
      - work_order_id (uuid str)
      - document_number (str | None)

    客戶端通知（無 postback）：技師已接單、即將為您服務。
    """
    wo_id = str(payload.get("work_order_id", ""))
    doc = payload.get("document_number")
    sub = [{"type": "text", "text": f"工單 {doc}", "size": "xs", "color": "#888888"}] if doc else []
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": "✅ 技師已接單", "weight": "bold",
                 "color": "#1DB446", "size": "md"},
                *sub,
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [{
                "type": "text",
                "text": "技師已接受您的維修工單，將依約定時間前往為您服務。",
                "wrap": True, "size": "sm",
            }],
        },
    }
    if not wo_id:
        return [_make_text_message("技師已接受您的工單，將依約定時間前往服務。")]
    return [_make_flex_message(alt_text="技師已接單", contents=bubble)]


def render_scope_change_result(payload: dict) -> list[dict]:
    """CR-0028 斷點 2 — 客戶報價決議後回推確認（respond_public enqueue）。

    payload schema:
      - scope_change_id (uuid str)
      - work_order_id (uuid str)
      - decision ('accept' | 'reject')

    accept → 告知技師將繼續施工；reject → 告知客服將聯繫。
    """
    decision = str(payload.get("decision") or "")
    if decision == "accept":
        title, color, text = (
            "✅ 已收到您的同意",
            "#1DB446",
            "感謝您確認變更項目，技師將繼續為您施工。",
        )
    else:
        title, color, text = (
            "📋 已收到您的回覆",
            "#E97600",
            "我們已收到您的回覆，客服將盡快與您聯繫後續安排。",
        )
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [{"type": "text", "text": title, "weight": "bold",
                          "color": color, "size": "md"}],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [{"type": "text", "text": text, "wrap": True, "size": "sm"}],
        },
    }
    return [_make_flex_message(alt_text=title, contents=bubble)]


# Dispatch table（worker 用 push_kind 路由）
BUILDERS: dict[str, Callable[[dict], list[dict]]] = {
    "reschedule_proposal": render_reschedule_proposal,
    "scope_change_proposal": render_scope_change_proposal,
    "schedule_conflict": render_schedule_conflict,
    # CR-0028 LINE 公單回傳斷鏈
    "work_order_assigned": render_work_order_assigned,
    "work_order_accepted": render_work_order_accepted,
    "scope_change_result": render_scope_change_result,
}


def build_messages(push_kind: str, payload: dict) -> list[dict] | None:
    """Worker entry：dispatch by push_kind → render messages list。

    回 None 若 push_kind 未支援（worker 標 status='dead'）。
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
