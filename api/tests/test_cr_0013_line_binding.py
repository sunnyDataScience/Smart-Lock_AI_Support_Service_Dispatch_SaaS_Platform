"""CR-0013 Stage 3 — line_binding_service + webhook 短碼 unit tests。

不依賴 DB／LINE API：
- _hash_token / _new_token 純函式
- TOKEN_TTL_HOURS 對齊 HD-04=(a) 24h
- webhook postback g:p / b:s 短碼分派
"""

from __future__ import annotations

import pytest

from services import line_binding_service as svc


# ----------------------------- token helpers -----------------------------

def test_hash_token_deterministic():
    """相同 token → 相同 hash；不同 → 不同。"""
    a = svc._hash_token("abc")
    b = svc._hash_token("abc")
    c = svc._hash_token("abd")
    assert a == b
    assert a != c


def test_hash_token_sha256_hex_length():
    """SHA-256 hex 固定 64 chars。"""
    assert len(svc._hash_token("anything")) == 64


def test_new_token_uniqueness():
    """100 次連抽不重複（極高機率）。"""
    seen = {svc._new_token() for _ in range(100)}
    assert len(seen) == 100


def test_new_token_length_reasonable():
    """token_urlsafe(32) 約 43 chars。"""
    t = svc._new_token()
    assert 40 <= len(t) <= 50


def test_token_ttl_hours_constant():
    """HD-04=(a) 24h TTL — 不該被無意改動。"""
    assert svc.TOKEN_TTL_HOURS == 24


# ----------------------------- webhook postback dispatch -----------------------------

@pytest.mark.asyncio
async def test_postback_get_progress_dispatches(monkeypatch):
    from routers import line_webhook

    called = {}

    async def fake_handle(*, line_uid):
        called["line_uid"] = line_uid

    monkeypatch.setattr(line_webhook, "_handle_get_progress", fake_handle)
    await line_webhook._handle_postback({
        "source": {"userId": "U1234567890"},
        "postback": {"data": "g:p"},
    })
    assert called["line_uid"] == "U1234567890"


@pytest.mark.asyncio
async def test_postback_binding_start_dispatches(monkeypatch):
    from routers import line_webhook

    called = {}

    async def fake_handle(*, line_uid):
        called["line_uid"] = line_uid

    monkeypatch.setattr(line_webhook, "_handle_binding_start", fake_handle)
    await line_webhook._handle_postback({
        "source": {"userId": "U999"},
        "postback": {"data": "b:s"},
    })
    assert called["line_uid"] == "U999"


@pytest.mark.asyncio
async def test_postback_g_p_with_extra_args_ignored(monkeypatch):
    """g:p 短碼是無參；帶 |args 應落入 unknown kind branch（不該誤觸 handler）。"""
    from routers import line_webhook

    called = {}

    async def fake_handle(*, line_uid):
        called["fired"] = True

    monkeypatch.setattr(line_webhook, "_handle_get_progress", fake_handle)
    await line_webhook._handle_postback({
        "source": {"userId": "U1"},
        "postback": {"data": "g:p|extra"},
    })
    assert "fired" not in called


@pytest.mark.asyncio
async def test_handle_get_progress_no_binding_pushes_hint(monkeypatch):
    """resolve_user_by_line_uid 回 None → push「尚未綁定」提示。"""
    from routers import line_webhook

    async def fake_resolve(**kwargs):
        return None

    pushed = {}

    async def fake_push(line_uid, text):
        pushed["line_uid"] = line_uid
        pushed["text"] = text

    monkeypatch.setattr(
        line_webhook.line_binding_service, "resolve_user_by_line_uid",
        fake_resolve,
    )
    monkeypatch.setattr(line_webhook, "_push_text", fake_push)

    await line_webhook._handle_get_progress(line_uid="Uabc")
    assert "尚未綁定" in pushed["text"]


@pytest.mark.asyncio
async def test_handle_get_progress_with_binding_pushes_link(monkeypatch):
    """resolve_user_by_line_uid 回 user_id → push 含 web link。"""
    from routers import line_webhook

    async def fake_resolve(**kwargs):
        return "user-uuid-1"

    pushed = {}

    async def fake_push(line_uid, text):
        pushed["text"] = text

    monkeypatch.setattr(
        line_webhook.line_binding_service, "resolve_user_by_line_uid",
        fake_resolve,
    )
    monkeypatch.setattr(line_webhook, "_push_text", fake_push)

    await line_webhook._handle_get_progress(line_uid="Uabc")
    assert "/track/orders" in pushed["text"]


@pytest.mark.asyncio
async def test_handle_binding_start_pushes_web_link(monkeypatch):
    """b:s 啟動 binding → push 訊息含 web/track/binding-start 連結。"""
    from routers import line_webhook

    pushed = {}

    async def fake_push(line_uid, text):
        pushed["text"] = text

    monkeypatch.setattr(line_webhook, "_push_text", fake_push)
    await line_webhook._handle_binding_start(line_uid="Uxyz")
    assert "binding-start" in pushed["text"]


# ----------------------------- rich menu schema -----------------------------

def test_rich_menu_definition_matches_spec():
    """setup_rich_menu.py 的 RICH_MENU_DEFINITION 應有 2 areas + 對齊短碼。"""
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(ROOT / "scripts" / "line"))
    import setup_rich_menu

    rm = setup_rich_menu.RICH_MENU_DEFINITION
    assert rm["size"] == {"width": 2500, "height": 843}
    assert len(rm["areas"]) == 2

    # 左半「查進度」postback g:p
    left = rm["areas"][0]
    assert left["action"]["type"] == "postback"
    assert left["action"]["data"] == "g:p"
    assert left["bounds"]["x"] == 0

    # 右半「綁定」postback b:s
    right = rm["areas"][1]
    assert right["action"]["data"] == "b:s"
    assert right["bounds"]["x"] == 1250
