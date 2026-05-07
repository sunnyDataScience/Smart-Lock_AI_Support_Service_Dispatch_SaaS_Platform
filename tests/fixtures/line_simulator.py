"""LINE Webhook 模擬器 — 可重用的 pytest fixture 與工具函式。

對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §10 #6 與 §5.3
"LINE Bot 不對真 LINE 做 E2E"，建立 forge HMAC-SHA256 webhook + capture reply
的測試 fixture。

實作來源：lift 自 tests/tools/simulate_e2e.py:44-63（dev tool）的純函式部分，
不動 dev tool 本身（保留它做 manual scenario 演練）。

Mock 光譜層：**Fake**（in-memory 同介面，無真 LINE 連線）

用法（在 component 或 contract test 中）：

    def test_my_webhook_handler(line_client):
        # line_client 是 (client_factory, sign_body) tuple
        client_factory, sign_body = line_client
        # 自行起 FastAPI TestClient 後：
        from fastapi.testclient import TestClient
        from agent.app import app
        with TestClient(app) as c:
            body = '{"events": [...]}'
            sig = sign_body(body, secret="test_secret")
            c.post("/webhook", content=body, headers={"X-Line-Signature": sig})

或使用便利方法 `LINESimulator`：

    sim = LINESimulator(secret="test_secret", user_id="U_test_001")
    payload, headers = sim.build_text_event("我的鎖壞了")
    response = test_client.post("/webhook", content=payload, headers=headers)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import pytest

# ── 純函式（與 simulate_e2e.py:44 等價，無 side effect） ────────────


def create_line_signature(body: str, secret: str) -> str:
    """產生 LINE Webhook signature header 值。

    LINE 平台對 webhook body 用 channel secret 做 HMAC-SHA256，
    再 base64 編碼後放 `X-Line-Signature` header。
    """
    digest = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_text_event(
    user_id: str,
    text: str,
    *,
    msg_id: str = "msg_001",
    reply_token: str | None = None,
) -> dict[str, Any]:
    """建構單筆 text MessageEvent payload（不含 destination wrapper）。"""
    return {
        "type": "message",
        "message": {"id": msg_id, "type": "text", "text": text},
        "source": {"type": "user", "userId": user_id},
        "replyToken": reply_token or f"token_{msg_id}",
        "mode": "active",
        "timestamp": int(time.time() * 1000),
    }


def build_media_event(
    user_id: str,
    media_type: str,
    *,
    msg_id: str = "media_001",
    reply_token: str | None = None,
) -> dict[str, Any]:
    """建構單筆 image / audio / video MessageEvent payload。"""
    return {
        "type": "message",
        "message": {"id": msg_id, "type": media_type},
        "source": {"type": "user", "userId": user_id},
        "replyToken": reply_token or f"token_{msg_id}",
        "mode": "active",
        "timestamp": int(time.time() * 1000),
    }


# ── 高階 wrapper：用來在 test 內快速建構整包 webhook payload ──────────


@dataclass
class LINESimulator:
    """LINE Webhook 模擬器 — 一個物件管 secret + user_id，產出 (body, headers) tuple。

    用例：

        sim = LINESimulator(secret="test_secret", user_id="U_001")
        body, headers = sim.text("我的鎖壞了")
        response = test_client.post("/webhook", content=body, headers=headers)
    """

    secret: str
    user_id: str = "U_TEST_DEFAULT"

    def _wrap(self, event: dict[str, Any]) -> tuple[str, dict[str, str]]:
        payload = {"destination": "dest", "events": [event]}
        body = json.dumps(payload)
        sig = create_line_signature(body, self.secret)
        return body, {"X-Line-Signature": sig, "Content-Type": "application/json"}

    def text(self, text: str, *, msg_id: str = "msg_001") -> tuple[str, dict[str, str]]:
        return self._wrap(build_text_event(self.user_id, text, msg_id=msg_id))

    def image(self, *, msg_id: str = "img_001") -> tuple[str, dict[str, str]]:
        return self._wrap(build_media_event(self.user_id, "image", msg_id=msg_id))

    def audio(self, *, msg_id: str = "audio_001") -> tuple[str, dict[str, str]]:
        return self._wrap(build_media_event(self.user_id, "audio", msg_id=msg_id))

    def video(self, *, msg_id: str = "video_001") -> tuple[str, dict[str, str]]:
        return self._wrap(build_media_event(self.user_id, "video", msg_id=msg_id))


# ── pytest fixtures ───────────────────────────────────────────────


@pytest.fixture
def line_secret() -> str:
    """測試用 LINE channel secret（永不接 prod）。"""
    return "test_secret"


@pytest.fixture
def line_simulator(line_secret) -> LINESimulator:
    """預配置的 LINESimulator 實例，user_id 用測試保留前綴 U_TEST_。"""
    return LINESimulator(secret=line_secret, user_id="U_TEST_FIXTURE")


@pytest.fixture
def line_sign():
    """`create_line_signature` 的 fixture 形式，方便 parametrize。"""
    return create_line_signature
