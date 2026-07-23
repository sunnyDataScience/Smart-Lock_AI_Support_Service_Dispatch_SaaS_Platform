"""CR-0179 方案 B — 樣本圖確定性夾圖（gateway 標記剝除 + ImageMessage 附發）。

業主 2026-07-22 裁決 2-B：AI 依 SOP 在回覆文末輸出 [[photo-guide:<key>]]，
gateway 剝除標記並附發對應 ImageMessage（不動 CS_TOOL_ALLOWLIST、零濫發）。

驗證面：
- _extract_photo_guides 純函式：單/多標記、未知 key 只剝不夾、無標記 passthrough、
  截斷殘尾防外洩、空白收斂、上限 4 圖
- webhook 整合：回覆含標記 → LINE reply 2 則（乾淨文字 + ImageMessage）；
  未配置 photo_guides → 標記仍剝除、只回 1 則文字
- SKILL.md v1.6.0 含標記話術指引（結構守線）
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from lockcore.channels.line_gateway import _extract_photo_guides

_GUIDES = {
    "pre-install": "https://web.example.com/photo-guides/pre-install.jpg",
    "booking-install": "https://web.example.com/photo-guides/booking-install.jpg",
}


# ── 純函式 ──────────────────────────────────────────────

def test_extract_single_marker():
    text = "請提供門的照片喔\n[[photo-guide:pre-install]]"
    cleaned, urls = _extract_photo_guides(text, _GUIDES)
    assert cleaned == "請提供門的照片喔"
    assert urls == [_GUIDES["pre-install"]]


def test_extract_multiple_markers_dedup_and_order():
    text = (
        "拍照重點如下\n[[photo-guide:pre-install]]\n"
        "[[photo-guide:booking-install]][[photo-guide:pre-install]]"
    )
    cleaned, urls = _extract_photo_guides(text, _GUIDES)
    assert "[[" not in cleaned
    assert urls == [_GUIDES["pre-install"], _GUIDES["booking-install"]]


def test_unknown_key_stripped_no_image():
    cleaned, urls = _extract_photo_guides("好的[[photo-guide:nope-key]]", _GUIDES)
    assert cleaned == "好的"
    assert urls == []


def test_no_marker_passthrough():
    cleaned, urls = _extract_photo_guides("一般回覆，無標記。", _GUIDES)
    assert cleaned == "一般回覆，無標記。"
    assert urls == []


def test_none_guide_map_still_strips():
    """未配置映射（功能關閉）：標記仍剝除，防外洩給客人。"""
    cleaned, urls = _extract_photo_guides("請拍照[[photo-guide:pre-install]]", None)
    assert cleaned == "請拍照"
    assert urls == []


def test_truncated_partial_marker_stripped():
    """handle_text_turn 4900 截斷腰斬標記 → 殘尾剝除不外洩。"""
    cleaned, urls = _extract_photo_guides("請拍照\n[[photo-guide:pre-ins", _GUIDES)
    assert "[[" not in cleaned
    assert cleaned == "請拍照"
    assert urls == []


def test_cap_four_images():
    guides = {f"k-{i}": f"https://x.example.com/{i}.jpg" for i in range(6)}
    text = "".join(f"[[photo-guide:k-{i}]]" for i in range(6))
    _, urls = _extract_photo_guides(text, guides)
    assert len(urls) == 4  # LINE 5 則上限扣 1 則文字


def test_whitespace_collapsed():
    text = "第一段\n\n[[photo-guide:pre-install]]\n\n\n第二段"
    cleaned, _ = _extract_photo_guides(text, _GUIDES)
    assert "\n\n\n" not in cleaned
    assert cleaned.startswith("第一段") and cleaned.endswith("第二段")


# ── SKILL.md 結構守線 ──────────────────────────────────

def test_skill_md_photo_guide_guidance_present():
    skill_md = (
        Path(__file__).resolve().parent.parent
        / "lockcore" / "skills" / "locksmith-cs-sop" / "SKILL.md"
    )
    text = skill_md.read_text(encoding="utf-8")
    assert "[[photo-guide:<key>]]" in text or "[[photo-guide:" in text
    # 品牌專屬 key（業主 2026-07-23：測量圖 Chatlock 專屬，其他品牌純文字）
    assert "chatlock-pre-install" in text
    assert "至多一個" in text
    # 守線：SOP 必須明文限定「僅 Chatlock 品牌」+ 其他品牌純文字，防丟錯品牌圖
    assert "Chatlock" in text
    assert "其他品牌" in text


# ── webhook 整合（真簽章 + patch LINE API）────────────────

pytest.importorskip("linebot")
pytest.importorskip("aiohttp.test_utils")


class _FakeOut:
    def __init__(self, content):
        self.content = content


class _FakeLoop:
    def __init__(self, reply):
        self._reply = reply

    async def _process_message(self, msg, session_key=None):
        return _FakeOut(self._reply)


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _webhook_body(user_id: str, text: str) -> bytes:
    payload = {
        "destination": "xxx",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1,
                "webhookEventId": "evt-pg",
                "deliveryContext": {"isRedelivery": False},
                "source": {"type": "user", "userId": user_id},
                "replyToken": "rt-pg",
                "message": {"type": "text", "id": "m1", "text": text, "quoteToken": "q1"},
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


def _run_webhook(monkeypatch, reply_text: str, photo_guides: dict | None) -> list:
    from aiohttp.test_utils import TestClient, TestServer
    from linebot.v3.messaging import AsyncMessagingApi

    from lockcore.channels import line_gateway

    monkeypatch.setenv("LINE_DEBOUNCE_SECONDS", "0")
    secret = "testsecret"
    sent: dict = {}

    async def _fake_reply(self, req, **kw):
        sent["messages"] = req.messages

    monkeypatch.setattr(AsyncMessagingApi, "reply_message", _fake_reply, raising=True)

    app = line_gateway.build_webapp(
        _FakeLoop(reply_text), "locksmart", secret, "dummy-token",
        photo_guides=photo_guides,
    )

    async def run():
        async with TestClient(TestServer(app)) as client:
            body = _webhook_body("Upg", "門要怎麼量")
            resp = await client.post(
                "/callback", data=body, headers={"X-Line-Signature": _sign(secret, body)}
            )
            assert resp.status == 200

    asyncio.run(run())
    return sent["messages"]


def test_webhook_reply_with_guide_attaches_image(monkeypatch):
    msgs = _run_webhook(
        monkeypatch,
        "麻煩拍門的正/背/側照片\n[[photo-guide:pre-install]]",
        _GUIDES,
    )
    assert len(msgs) == 2
    assert "[[" not in msgs[0].text
    assert msgs[1].original_content_url == _GUIDES["pre-install"]
    assert msgs[1].preview_image_url == _GUIDES["pre-install"]


def test_webhook_reply_unconfigured_strips_marker(monkeypatch):
    msgs = _run_webhook(
        monkeypatch,
        "麻煩拍門的照片\n[[photo-guide:pre-install]]",
        None,
    )
    assert len(msgs) == 1
    assert "[[" not in msgs[0].text
