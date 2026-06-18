"""CR-0028 — LINE 公單回傳斷鏈 builder + dispatch 測試（純函式，無需 DB）。

驗證：
- render_work_order_assigned / accepted：有 wo_id → flex；無 wo_id → text fallback
- render_scope_change_result：accept / reject 兩種文案不同
- build_messages：三個新 push_kind 都能 dispatch（非 None）
- PushKind Literal 含三個新值
"""

from __future__ import annotations

from templates.line_flex.builders import (
    BUILDERS,
    build_messages,
    render_scope_change_result,
    render_work_order_accepted,
    render_work_order_assigned,
)


def _is_flex(msg: dict) -> bool:
    return msg.get("type") == "flex" and "contents" in msg


def test_assigned_flex_with_wo_id():
    msgs = render_work_order_assigned(
        {"work_order_id": "11111111-1111-1111-1111-111111111111", "document_number": "TP-000123"}
    )
    assert len(msgs) == 1
    assert _is_flex(msgs[0])
    # 公單號顯示在 header
    assert "TP-000123" in str(msgs[0])
    # 客戶端不應出現 raw UUID
    assert "11111111-1111" not in str(msgs[0])


def test_assigned_text_fallback_without_wo_id():
    msgs = render_work_order_assigned({})
    assert len(msgs) == 1
    assert msgs[0]["type"] == "text"


def test_accepted_flex():
    msgs = render_work_order_accepted(
        {"work_order_id": "22222222-2222-2222-2222-222222222222"}
    )
    assert len(msgs) == 1
    assert _is_flex(msgs[0])
    assert "接" in str(msgs[0])  # 「技師已接單」語意


def test_scope_change_result_accept_vs_reject_differ():
    accept = render_scope_change_result(
        {"scope_change_id": "sc1", "work_order_id": "wo1", "decision": "accept"}
    )
    reject = render_scope_change_result(
        {"scope_change_id": "sc1", "work_order_id": "wo1", "decision": "reject"}
    )
    assert _is_flex(accept[0]) and _is_flex(reject[0])
    assert str(accept) != str(reject)
    assert "同意" in str(accept)


def test_build_messages_dispatches_new_kinds():
    # work_order_document（CR-0027）一併驗證 dispatch
    kinds = ("work_order_assigned", "work_order_accepted", "scope_change_result",
             "work_order_document")
    for kind in kinds:
        assert kind in BUILDERS
        out = build_messages(kind, {"work_order_id": "wo1", "decision": "accept",
                                    "final_amount": "2000"})
        assert out is not None
        assert isinstance(out, list) and len(out) >= 1


def test_work_order_document_shows_final_amount_only():
    out = build_messages("work_order_document",
                         {"work_order_id": "wo1", "document_number": "PB-000123",
                          "final_amount": "2000"})
    s = str(out)
    assert "2000" in s and "PB-000123" in s
    assert "完成" in s


def test_pushkind_literal_includes_new_values():
    from services.line_push_outbox_service import PushKind  # type: ignore
    import typing

    values = set(typing.get_args(PushKind))
    assert {"work_order_assigned", "work_order_accepted", "scope_change_result"} <= values
