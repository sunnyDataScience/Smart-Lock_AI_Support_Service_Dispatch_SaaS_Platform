"""CR-0017 Stage 5 — Flex builder unit tests。

純函式測試，不需要 DB / LINE API。驗證：
- render_reschedule_proposal: carousel 結構、bubble 數、postback 短碼
- render_scope_change_proposal: bubble、accept/reject postback、URI fallback
- render_schedule_conflict: admin bubble + URI button (無 postback)
- build_messages dispatch + 異常 fallback
"""

from __future__ import annotations

import json

import pytest

from templates.line_flex import builders


# ----------------------------- reschedule -----------------------------

def test_reschedule_carousel_structure():
    payload = {
        "proposal_id": "11111111-1111-1111-1111-111111111111",
        "work_order_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "proposed_slots": [
            {"start": "2026-06-10T10:00:00+08:00", "end": "2026-06-10T12:00:00+08:00"},
            {"start": "2026-06-11T14:00:00+08:00"},
        ],
        "message_to_customer": "上午方便嗎？",
    }
    msgs = builders.render_reschedule_proposal(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "flex"
    assert "改約時段提案" in msg["altText"]

    carousel = msg["contents"]
    assert carousel["type"] == "carousel"
    # 2 slot bubbles + 1 reject bubble
    assert len(carousel["contents"]) == 3

    # Bubble 0：選擇此時段 postback
    btn = carousel["contents"][0]["footer"]["contents"][0]
    assert btn["action"]["type"] == "postback"
    assert btn["action"]["data"] == "r:c|11111111-1111-1111-1111-111111111111|0"

    # Bubble 1：第 2 個 slot index=1
    btn1 = carousel["contents"][1]["footer"]["contents"][0]
    assert btn1["action"]["data"] == "r:c|11111111-1111-1111-1111-111111111111|1"

    # 末 bubble：reject
    reject_btn = carousel["contents"][2]["footer"]["contents"][0]
    assert reject_btn["action"]["data"] == "r:r|11111111-1111-1111-1111-111111111111"


def test_reschedule_caps_at_3_slots():
    """業務上限 3，多餘 slot 應截斷。"""
    payload = {
        "proposal_id": "p1",
        "work_order_id": "w1",
        "proposed_slots": [
            {"start": f"2026-06-{10+i:02d}T10:00:00+08:00"} for i in range(5)
        ],
    }
    msgs = builders.render_reschedule_proposal(payload)
    carousel = msgs[0]["contents"]
    # 3 slot + 1 reject = 4 bubbles
    assert len(carousel["contents"]) == 4


def test_reschedule_empty_slots_falls_back_to_text():
    msgs = builders.render_reschedule_proposal({
        "proposal_id": "p1", "work_order_id": "w1", "proposed_slots": [],
    })
    assert msgs[0]["type"] == "text"
    assert "不完整" in msgs[0]["text"]


# ----------------------------- scope_change -----------------------------

def test_scope_change_bubble_with_buttons():
    payload = {
        "scope_change_id": "22222222-2222-2222-2222-222222222222",
        "work_order_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "reason": "現場發現主控板故障",
        "items": [
            {"name": "主控板更換", "quantity": 1, "unit_price": "3500"},
            {"name": "工資", "quantity": 1, "unit_price": "800"},
        ],
        "total_estimate": "4300 TWD",
        "public_token": "abc123def456",
    }
    msgs = builders.render_scope_change_proposal(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "flex"
    bubble = msg["contents"]
    assert bubble["type"] == "bubble"

    footer_btns = bubble["footer"]["contents"]
    # accept + reject + URI fallback
    assert len(footer_btns) == 3
    assert footer_btns[0]["action"]["data"] == "s:a|22222222-2222-2222-2222-222222222222"
    assert footer_btns[1]["action"]["data"] == "s:r|22222222-2222-2222-2222-222222222222"
    assert footer_btns[2]["action"]["type"] == "uri"
    assert "abc123def456" in footer_btns[2]["action"]["uri"]


def test_scope_change_without_token_omits_uri_button():
    payload = {
        "scope_change_id": "sc1", "work_order_id": "w1",
        "reason": "x", "items": [], "total_estimate": "0",
    }
    msgs = builders.render_scope_change_proposal(payload)
    footer_btns = msgs[0]["contents"]["footer"]["contents"]
    # 只剩 accept + reject
    assert len(footer_btns) == 2
    assert all(b["action"]["type"] == "postback" for b in footer_btns)


def test_scope_change_missing_id_falls_back_to_text():
    msgs = builders.render_scope_change_proposal({
        "scope_change_id": "", "work_order_id": "w1",
    })
    assert msgs[0]["type"] == "text"


# ----------------------------- schedule_conflict -----------------------------

def test_schedule_conflict_admin_bubble_no_postback():
    payload = {
        "technician_id": "tttttttt-tttt-tttt-tttt-tttttttttttt",
        "window_hours": 2,
        "scheduled_at": "2026-06-15T09:00:00+08:00",
        "conflicting_wo_ids": [f"wo-{i:08d}-aaaa-aaaa-aaaa-aaaaaaaaaaaa" for i in range(3)],
    }
    msgs = builders.render_schedule_conflict(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "flex"
    bubble = msg["contents"]
    # 紅色 header
    assert bubble["header"]["backgroundColor"] == "#DC3545"
    # 只有 URI button，無 postback
    btn = bubble["footer"]["contents"][0]
    assert btn["action"]["type"] == "uri"


def test_schedule_conflict_truncates_at_5():
    payload = {
        "technician_id": "t1",
        "conflicting_wo_ids": [f"wo-{i}" for i in range(10)],
    }
    msgs = builders.render_schedule_conflict(payload)
    body_rows = msgs[0]["contents"]["body"]["contents"]
    # 找 "...等 N 筆" 行
    extras = [r for r in body_rows if "...等" in str(r.get("text", ""))]
    assert len(extras) == 1


# ----------------------------- dispatch -----------------------------

def test_build_messages_dispatch_to_right_builder():
    msgs = builders.build_messages("reschedule_proposal", {
        "proposal_id": "p1", "work_order_id": "w1",
        "proposed_slots": [{"start": "2026-06-10T10:00:00"}],
    })
    assert msgs and msgs[0]["type"] == "flex"


def test_build_messages_unknown_kind_returns_none():
    assert builders.build_messages("foo_bar_kind", {}) is None


def test_build_messages_swallows_builder_exception():
    """Builder 內部 KeyError 不該 leak — worker 預期回 None 標 dead。"""
    # 給一個 builder 會崩的 payload（None 觸發 slot.get() AttributeError）
    msgs = builders.build_messages("reschedule_proposal", {
        "proposal_id": "p1", "work_order_id": "w1",
        "proposed_slots": [None],  # slot.get 觸發 AttributeError
    })
    # builder 內 try/except 應吞，回 None
    assert msgs is None
