"""LINE 通道測試 — 離線。webhook 路徑用真實簽章 + patch 掉 LINE reply API。"""

import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from lockcore.channels.line_gateway import (
    _apply_handoff_fallback_safe,
    _extract_brand_model,
    _promised_handoff,
    handle_text_turn,
    load_dotenv,
    resolve_identity,
)


def test_resolve_identity_line_uses_userid():
    assert resolve_identity("line", "U1234", "locksmart") == ("locksmart", "U1234")


# ── CR-0097 方案 A 兜底：AI 承諾轉接卻沒呼叫工具 → 程式補 escalation ──────────────


def test_promised_handoff_detects_real_shibboleth():
    # 實測 prod 蒸發的那句（AI 說了卻沒呼叫工具）
    assert _promised_handoff("好的，這部分我已幫您轉接給真人專員處理 🙋") is True
    assert _promised_handoff("已為您安排專員，將與您聯繫") is True
    assert _promised_handoff("我幫您安排師傅到府維修") is True


def test_promised_handoff_ignores_plain_info():
    assert _promised_handoff("您的鎖是 Dormakaba AS701，可以長按設定鍵重設") is False
    assert _promised_handoff("") is False


def _mk_store():
    from lockcore.agent.user_memory.escalation import EscalationStore

    return EscalationStore(":memory:")


def test_fallback_logs_when_promised_but_no_tool_call():
    """AI 承諾轉接 + 本輪 escalation 未新增 → 兜底補一筆。"""
    esc = _mk_store()
    before = 0  # 本輪前無 escalation
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "門鎖壞了 Chatlock A90 鎖舌卡住 0922371211",
        "好的，我已幫您轉接給真人專員處理 🙋", before,
    )
    recs = esc.list_for_user("locksmart", "U1")
    assert len(recs) == 1
    assert recs[0].facts_snapshot.get("fallback") is True


def test_fallback_skips_when_tool_already_called():
    """本輪 AI 已正常呼叫工具（escalation 較 before 新增）→ 不重複補。"""
    esc = _mk_store()
    before = 0  # turn 前無 escalation
    esc.log("locksmart", "U1", "正常轉真人", True, {})  # turn 中 AI 呼叫 transfer_to_human 寫一筆
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "報價多少", "已幫您轉接給真人專員", before,
    )
    # _latest(1) > before(0) → 已 escalate，兜底不再補；仍只有那 1 筆
    assert len(esc.list_for_user("locksmart", "U1")) == 1


def test_fallback_skips_when_no_promise():
    """AI 沒承諾轉接（純資訊回答）→ 不兜底。"""
    esc = _mk_store()
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "怎麼重設密碼", "長按設定鍵 3 秒即可重設", 0,
    )
    assert esc.list_for_user("locksmart", "U1") == []


def test_fallback_none_store_is_noop():
    """無 escalation store → 安靜略過，不爆。"""
    _apply_handoff_fallback_safe(None, "locksmart", "U1", "x", "已幫您轉接真人專員", 0)


# ── CR-0097+：兜底品牌/型號補抽 ──────────────────────────────────────────────
def test_extract_brand_model_from_user_text():
    """客人原話含品牌型號 → 抽出（品牌正規化為正典寫法）。"""
    assert _extract_brand_model("我的門鎖壞了 Chatlock A90 鎖舌卡住了 0922371211") == (
        "Chatlock",
        "A90",
    )
    assert _extract_brand_model("Dormakaba FA9000 面板沒反應") == ("Dormakaba", "FA9000")
    # 品牌不分大小寫，回正典寫法
    assert _extract_brand_model("我家的 philips 9300 開不了") == ("Philips", "9300")


def test_extract_brand_model_from_assistant_reply():
    """客人原話沒明寫、AI 回覆複述「品牌/型號：…」→ 也能抽（兩來源合併）。"""
    assert _extract_brand_model(
        "門鎖壞了", "關於您提到的 Chatlock A90 門鎖鎖舌卡住問題"
    ) == ("Chatlock", "A90")


def test_extract_brand_model_none_when_no_brand():
    """無已知品牌 → ('', '')，不亂猜。"""
    assert _extract_brand_model("門鎖壞了 想修", "已幫您轉接專員") == ("", "")
    assert _extract_brand_model("") == ("", "")


def test_fallback_snapshot_carries_brand_model():
    """CR-0097+ 回歸：兜底 escalation 的 facts_snapshot 須帶補抽的 brand/model，
    讓 API 端 CR-0098 自動填問題卡（LLM 沒呼叫工具時不再整欄空白）。"""
    esc = _mk_store()
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "門鎖壞了 Chatlock A90 鎖舌卡住 0922371211",
        "好的，關於您的 Chatlock A90，我已幫您轉接給真人專員處理 🙋", 0,
    )
    recs = esc.list_for_user("locksmart", "U1")
    assert len(recs) == 1
    snap = recs[0].facts_snapshot
    assert snap.get("brand") == "Chatlock"
    assert snap.get("model") == "A90"


def test_load_dotenv_parses_quoted(tmp_path, monkeypatch):
    monkeypatch.delenv("FOO_X", raising=False)
    f = tmp_path / ".env"
    f.write_text('# comment\nFOO_X="bar baz"\nEMPTY=\n', encoding="utf-8")
    loaded = load_dotenv(f)
    assert loaded["FOO_X"] == "bar baz"
    import os
    assert os.environ["FOO_X"] == "bar baz"


def test_load_dotenv_missing_file_ok(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") == {}


class _FakeOut:
    def __init__(self, content):
        self.content = content


class _FakeLoop:
    def __init__(self, reply):
        self._reply = reply
        self.seen: dict = {}

    async def _process_message(self, msg, session_key=None):
        self.seen = {"sender_id": msg.sender_id, "content": msg.content, "session_key": session_key}
        return _FakeOut(self._reply)


def test_handle_text_turn_routes_and_returns():
    loop = _FakeLoop("您家的鎖是 Dormakaba AS701")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "我的鎖什麼型號"))
    assert out == "您家的鎖是 Dormakaba AS701"
    assert loop.seen["sender_id"] == "U1"
    assert loop.seen["session_key"] == "locksmart:U1"


def test_handle_text_turn_blank_skips():
    loop = _FakeLoop("x")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "   "))
    assert out == ""
    assert loop.seen == {}   # 空訊息不進 loop


def test_handle_text_turn_truncates_long_reply():
    loop = _FakeLoop("一" * 6000)
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "問題"))
    assert len(out) == 4900


def test_handle_text_turn_masks_internal_error():
    """LLM/provider 失敗時的 [litellm error] 不可外洩給客人,改友善話術。"""
    loop = _FakeLoop("[litellm error] litellm.BadRequestError: ...403 billing...")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "你好"))
    assert "litellm" not in out
    assert "error" not in out.lower()
    assert "專員" in out   # 友善 fallback


def test_handle_text_turn_empty_reply_returns_empty():
    loop = _FakeLoop("   ")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "你好"))
    assert out == ""


# ---- webhook 路徑(需 line-bot-sdk + aiohttp test server)----

pytest.importorskip("linebot")
aiohttp_test = pytest.importorskip("aiohttp.test_utils")


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _webhook_body(user_id: str, text: str, reply_token: str = "rt1") -> bytes:
    payload = {
        "destination": "xxx",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1,
                "webhookEventId": "evt1",
                "deliveryContext": {"isRedelivery": False},
                "source": {"type": "user", "userId": user_id},
                "replyToken": reply_token,
                "message": {"type": "text", "id": "m1", "text": text, "quoteToken": "q1"},
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


def test_webhook_valid_signature_invokes_loop_and_replies(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    from lockcore.channels import line_gateway

    secret = "testsecret"
    loop = _FakeLoop("好的,已為您記下 🔐")

    replied: dict = {}

    async def _fake_reply(self, req, **kw):
        replied["text"] = req.messages[0].text
        replied["token"] = req.reply_token

    # 不要真的打 LINE API
    from linebot.v3.messaging import AsyncMessagingApi
    monkeypatch.setattr(AsyncMessagingApi, "reply_message", _fake_reply, raising=True)

    app = line_gateway.build_webapp(loop, "locksmart", secret, "dummy-token")

    async def run():
        async with TestClient(TestServer(app)) as client:
            body = _webhook_body("Uabc", "我的鎖是 Kaadas K9")
            sig = _sign(secret, body)
            resp = await client.post("/callback", data=body, headers={"X-Line-Signature": sig})
            assert resp.status == 200
            # bad signature → 400
            bad = await client.post("/callback", data=body, headers={"X-Line-Signature": "nope"})
            assert bad.status == 400

    asyncio.run(run())

    assert loop.seen["sender_id"] == "Uabc"
    assert loop.seen["content"] == "我的鎖是 Kaadas K9"
    assert replied["text"] == "好的,已為您記下 🔐"
    assert replied["token"] == "rt1"
