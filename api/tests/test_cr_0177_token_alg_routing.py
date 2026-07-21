"""CR-0177 S1：`_decode_any_token` 依 JWT header alg 路由（dual-accept 過渡）。

鎖定：RS256→Casdoor OIDC、HS256→自簽、alg 不可判讀→保守雙試；
並斷言 **alg-confusion 防護**（RS256 token 絕不落到 HS256 驗證器）。純函式，不碰 DB。
"""

from __future__ import annotations

import base64
import json

import pytest

from core import deps
from core.oidc import OIDCError


def _tok(alg: str) -> str:
    """造一個 header 指定 alg 的 JWT 形狀字串（簽章無效，只驗路由）。"""
    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': alg, 'typ': 'JWT'})}.{b64({'sub': 'u1'})}.sig"


@pytest.fixture
def spies(monkeypatch):
    calls: list[str] = []

    def fake_decode(token):
        calls.append("hs256")
        return {"sub": "local", "type": "access"}

    def fake_oidc(token):
        calls.append("rs256")
        return {"sub": "casdoor", "type": "access"}

    monkeypatch.setattr(deps, "decode_token", fake_decode)
    monkeypatch.setattr(deps, "verify_oidc_token", fake_oidc)
    monkeypatch.setattr(deps, "oidc_enabled", lambda: True)
    return calls


def test_rs256_routes_to_oidc(spies):
    out = deps._decode_any_token(_tok("RS256"))
    assert out["sub"] == "casdoor"
    assert spies == ["rs256"]              # 只走 OIDC，未先試 HS256


def test_hs256_routes_to_local(spies):
    out = deps._decode_any_token(_tok("HS256"))
    assert out["sub"] == "local"
    assert spies == ["hs256"]


def test_alg_confusion_guard(spies):
    """RS256 token 絕不落到自簽 HS256 驗證器（防以公鑰當 HMAC secret 繞過）。"""
    deps._decode_any_token(_tok("RS256"))
    assert "hs256" not in spies


def test_rs256_without_oidc_configured_raises_clear_error(monkeypatch):
    monkeypatch.setattr(deps, "oidc_enabled", lambda: False)
    with pytest.raises(OIDCError) as ei:
        deps._decode_any_token(_tok("RS256"))
    assert "OIDC 未配置" in str(ei.value)   # 非誤導性的 HS256 解碼失敗


def test_unreadable_alg_falls_back_to_dual_try(spies):
    """壞 token（讀不到 alg）→ 保守雙試，先自簽（沿舊版行為）。"""
    out = deps._decode_any_token("not-a-jwt")
    assert out["sub"] == "local"
    assert spies == ["hs256"]


def test_unreadable_alg_then_oidc_when_local_fails(monkeypatch):
    calls: list[str] = []

    def fail_decode(token):
        calls.append("hs256")
        raise ValueError("bad")

    def ok_oidc(token):
        calls.append("rs256")
        return {"sub": "casdoor", "type": "access"}

    monkeypatch.setattr(deps, "decode_token", fail_decode)
    monkeypatch.setattr(deps, "verify_oidc_token", ok_oidc)
    monkeypatch.setattr(deps, "oidc_enabled", lambda: True)
    out = deps._decode_any_token("not-a-jwt")
    assert out["sub"] == "casdoor"
    assert calls == ["hs256", "rs256"]
