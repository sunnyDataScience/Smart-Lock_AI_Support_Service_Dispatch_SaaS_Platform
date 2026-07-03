"""LINE 通道測試 — 離線。webhook 路徑用真實簽章 + patch 掉 LINE reply API。"""

import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from lockcore.channels.line_gateway import (
    _apply_handoff_fallback_safe,
    _clean_symptom,
    _extract_brand_model,
    _extract_phone,
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


# ── CR-0097+：兜底症狀去噪 ──────────────────────────────────────────────────
def test_clean_symptom_strips_phone_brand_filler():
    """去電話 + 品牌/型號 + 開頭贅語 → 精簡症狀（非原話直搬）。"""
    assert _clean_symptom(
        "我的門鎖壞了 Chatlock A90 鎖舌卡住了 0922371211", "Chatlock", "A90"
    ) == "鎖舌卡住了"
    assert _clean_symptom(
        "Dormakaba FA9000 面板沒反應 0912345678", "Dormakaba", "FA9000"
    ) == "面板沒反應"


def test_clean_symptom_preserves_lock_word():
    """保守剝除：不可吃掉『鎖舌卡住』的『鎖』。"""
    assert _clean_symptom("鎖舌卡住", "", "") == "鎖舌卡住"


def test_clean_symptom_falls_back_when_nothing_left():
    """去噪後太短 → 退回原話，不留空。"""
    assert _clean_symptom("我的鎖壞了", "", "") == "我的鎖壞了"
    assert _clean_symptom("") == ""


def test_fallback_snapshot_carries_clean_symptom():
    """CR-0097+ 回歸：兜底 snapshot 的 symptom 為去噪後精簡描述，非客人原話直搬。"""
    esc = _mk_store()
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "我的門鎖壞了 Chatlock A90 鎖舌卡住了 0922371211",
        "好的，關於您的 Chatlock A90 鎖舌卡住問題，我已幫您轉接專員 🙋", 0,
    )
    snap = esc.list_for_user("locksmart", "U1")[0].facts_snapshot
    assert snap.get("symptom") == "鎖舌卡住了"
    assert "0922371211" not in snap.get("symptom", "")  # 電話不入症狀


# ── CR-0102：兜底電話補抽（客人留手機 → 自動填工單 customer_phone）─────────────
def test_extract_phone_various_formats():
    """台灣手機各種寫法 → 正規化 09xxxxxxxx；市話/無電話 → 空字串。"""
    assert _extract_phone("我的門鎖壞了 0922371211 麻煩盡快") == "0922371211"
    assert _extract_phone("電話 0912-345-678") == "0912345678"
    assert _extract_phone("手機是 0912 345 678 喔") == "0912345678"
    assert _extract_phone("+886912345678 找我") == "0912345678"
    assert _extract_phone("+886 912 345 678") == "0912345678"
    # 市話/分機不抽（誤判風險高）
    assert _extract_phone("公司電話 02-12345678") == ""
    # 無電話
    assert _extract_phone("門鎖壞了想修", "已幫您轉接") == ""
    assert _extract_phone("") == ""


def test_extract_phone_prefers_first_text_then_next():
    """多來源依序找：本輪原話沒有 → 退 facts_block / 摘要。"""
    assert _extract_phone("沒提電話", "facts: 客人手機 0933888999") == "0933888999"


def test_fallback_snapshot_carries_phone():
    """CR-0102 回歸：兜底 escalation 的 facts_snapshot 須帶補抽的手機，
    讓 API 端寫進 users.phone → 轉工單時 customer_phone 自動填上。"""
    esc = _mk_store()
    _apply_handoff_fallback_safe(
        esc, "locksmart", "U1", "門鎖壞了 Chatlock A90 鎖舌卡住 我電話 0922-371-211",
        "好的，已幫您轉接給真人專員處理 🙋", 0,
    )
    snap = esc.list_for_user("locksmart", "U1")[0].facts_snapshot
    assert snap.get("phone") == "0922371211"


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


# ── VLN(2026-07-03):LINE 圖片訊息接入 vision 管線 ──────────────


class _FakeMediaLoop(_FakeLoop):
    async def _process_message(self, msg, session_key=None):
        self.seen = {
            "sender_id": msg.sender_id,
            "content": msg.content,
            "media": list(msg.media or []),
            "session_key": session_key,
        }
        return _FakeOut(self._reply)


def test_handle_text_turn_carries_media_paths():
    """帶 media 的 turn:路徑進 InboundMessage.media(vision 管線入口)。"""
    loop = _FakeMediaLoop("照片裡是 Dormakaba 面板")
    out = asyncio.run(
        handle_text_turn(loop, "locksmart", "U1", "", media=["/tmp/img.jpg"])
    )
    assert out == "照片裡是 Dormakaba 面板"
    assert loop.seen["media"] == ["/tmp/img.jpg"]
    assert loop.seen["content"] == ""


def test_handle_text_turn_media_only_not_skipped():
    """純圖片(無文字)不可被空訊息 guard 擋掉。"""
    loop = _FakeMediaLoop("ok")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "  ", media=["/tmp/a.png"]))
    assert out == "ok"
    assert loop.seen["media"] == ["/tmp/a.png"]


def test_handle_text_turn_no_text_no_media_skips():
    loop = _FakeMediaLoop("x")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "", media=None))
    assert out == ""
    assert loop.seen == {}


class _FakeBlobApi:
    """模擬 AsyncMessagingApiBlob.get_message_content。"""

    def __init__(self, data):
        self._data = data
        self.called_with = None

    async def get_message_content(self, message_id):
        self.called_with = message_id
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


# 最小合法 PNG magic bytes(detect_image_mime 用 magic bytes 判 mime)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_download_line_image_writes_file(tmp_path, monkeypatch):
    from lockcore.channels import line_gateway as lg

    monkeypatch.setattr(
        "lockcore.config.paths.get_media_dir", lambda channel=None: tmp_path
    )
    blob = _FakeBlobApi(bytearray(_PNG_BYTES))
    path = asyncio.run(lg.download_line_image(blob, "msg-123"))
    assert path is not None and path.endswith("msg-123.png")
    from pathlib import Path

    assert Path(path).read_bytes() == _PNG_BYTES
    assert blob.called_with == "msg-123"


def test_download_line_image_empty_returns_none(tmp_path, monkeypatch):
    from lockcore.channels import line_gateway as lg

    monkeypatch.setattr(
        "lockcore.config.paths.get_media_dir", lambda channel=None: tmp_path
    )
    blob = _FakeBlobApi(b"")
    assert asyncio.run(lg.download_line_image(blob, "msg-e")) is None


def test_download_line_image_error_returns_none(tmp_path, monkeypatch):
    """Blob API 炸掉 → fail-soft 回 None,不 raise(webhook 不可炸)。"""
    from lockcore.channels import line_gateway as lg

    monkeypatch.setattr(
        "lockcore.config.paths.get_media_dir", lambda channel=None: tmp_path
    )
    blob = _FakeBlobApi(RuntimeError("boom"))
    assert asyncio.run(lg.download_line_image(blob, "msg-x")) is None
