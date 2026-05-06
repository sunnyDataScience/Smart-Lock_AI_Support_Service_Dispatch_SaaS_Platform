"""LINE Flex Message builder for Flow 11 客戶端改期 RSVP。

對應流程：
  1. 技師 v1.7.0 /reschedule 送出 1-3 個 proposed_slots
  2. 系統 push LINE Flex 給客戶（本模組產生 Flex JSON）
  3. 客戶點選某個時段 → LINE 觸發 PostbackEvent
  4. webhook 解析後呼叫 api /work-orders/{id}/reschedule/customer-confirm
  5. api 更新 wo.scheduled_at + 推 WS 給技師

postback data 格式：
  reschedule_select?wo={wo_id}&start={iso}&end={iso}
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from urllib.parse import urlencode


def _format_slot_label(start_iso: str, end_iso: str) -> str:
    """例：2026-05-10 14:00–15:30"""
    try:
        s = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except ValueError:
        return f"{start_iso} ~ {end_iso}"
    if s.date() == e.date():
        return f"{s.strftime('%Y-%m-%d')} {s.strftime('%H:%M')}–{e.strftime('%H:%M')}"
    return f"{s.strftime('%m/%d %H:%M')} → {e.strftime('%m/%d %H:%M')}"


def build_reschedule_flex(
    *,
    wo_id: str,
    proposed_slots: Iterable[dict],
    message_to_customer: str | None = None,
) -> dict:
    """產生 Flex Message bubble JSON 供 LINE Messaging API 使用。

    Args:
        wo_id: 工單 UUID
        proposed_slots: list of {"start": iso, "end": iso}
        message_to_customer: 技師端輸入的訊息（取代預設說明）

    Returns:
        dict — alt_text + flex contents
    """
    slots = list(proposed_slots)
    if not slots:
        raise ValueError("proposed_slots is empty")

    intro = (
        message_to_customer
        or "很抱歉需要調整時間，請選擇下方任一可行時段："
    )

    slot_buttons = []
    for slot in slots[:3]:
        start = slot.get("start", "")
        end = slot.get("end", "")
        label = _format_slot_label(start, end)
        # postback data 走 querystring 格式，方便 webhook 解析
        data = "reschedule_select?" + urlencode(
            {"wo": wo_id, "start": start, "end": end}
        )
        slot_buttons.append(
            {
                "type": "button",
                "style": "primary",
                "color": "#2563EB",
                "margin": "sm",
                "action": {
                    "type": "postback",
                    "label": label,
                    "data": data,
                    "displayText": f"我選擇 {label}",
                },
            }
        )

    # 拒絕按鈕（postback "reschedule_reject"）
    slot_buttons.append(
        {
            "type": "button",
            "style": "secondary",
            "margin": "md",
            "action": {
                "type": "postback",
                "label": "都不方便",
                "data": "reschedule_reject?" + urlencode({"wo": wo_id}),
                "displayText": "我都不方便這幾個時段",
            },
        }
    )

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "改期通知",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "lg",
                }
            ],
            "backgroundColor": "#2563EB",
            "paddingAll": "md",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": intro,
                    "wrap": True,
                    "size": "sm",
                    "color": "#1E293B",
                },
                {
                    "type": "separator",
                    "margin": "md",
                },
                {
                    "type": "text",
                    "text": "請選擇方便的時段：",
                    "margin": "md",
                    "size": "xs",
                    "color": "#64748B",
                },
                *slot_buttons,
            ],
            "spacing": "none",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"工單 #{wo_id[:8]}",
                    "size": "xxs",
                    "color": "#94A3B8",
                    "align": "center",
                }
            ],
        },
    }

    return {
        "alt_text": "改期通知 — 請選擇時段",
        "contents": bubble,
    }


def parse_postback_data(data: str) -> dict[str, str] | None:
    """解析 postback data：reschedule_select?wo=...&start=...&end=...

    Returns:
        {"action": ..., "wo": ..., "start": ..., "end": ...} 或 None（非本模組事件）
    """
    if "?" not in data:
        return None
    action, qs = data.split("?", 1)
    if action not in {"reschedule_select", "reschedule_reject"}:
        return None
    pairs = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
    from urllib.parse import unquote

    return {
        "action": action,
        **{k: unquote(v) for k, v in pairs.items()},
    }
