"""CR-0177 S4（HD-6）：SSO 已配置時的本地密碼登入＝break-glass，必留稽核。

鎖定三件事：
  1. OIDC 未配置 → **不記**（本地密碼本就是正常路徑，避免稽核噪音）
  2. OIDC 已配置 → **必記** security/break_glass_local_login，帶 actor/role/tenant
  3. 稽核寫入失敗 → **不得阻斷登入**（否則 break-glass 本身失效）
不碰 DB。
"""

from __future__ import annotations

import pytest

import core.oidc as oidc_mod
import services.audit_log_service as als
from services import auth_service

USER = {"id": "0a000001-0000-0000-0000-000000000001", "role": "operations_manager",
        "tenant_id": "00000000-0000-0000-0000-000000000001"}


@pytest.fixture
def audit_spy(monkeypatch):
    calls: list[dict] = []

    async def spy(**kw):
        calls.append(kw)

    monkeypatch.setattr(als, "log_event", spy)
    return calls


@pytest.mark.asyncio
async def test_no_audit_when_oidc_disabled(monkeypatch, audit_spy):
    monkeypatch.setattr(oidc_mod, "oidc_enabled", lambda: False)
    await auth_service._audit_break_glass_login(USER, via="email")
    assert audit_spy == []          # 本地密碼是正常路徑 → 不製造噪音


@pytest.mark.asyncio
async def test_audit_when_oidc_enabled(monkeypatch, audit_spy):
    monkeypatch.setattr(oidc_mod, "oidc_enabled", lambda: True)
    await auth_service._audit_break_glass_login(USER, via="email")
    assert len(audit_spy) == 1
    ev = audit_spy[0]
    assert ev["event_type"] == "security"
    assert ev["action"] == "break_glass_local_login"
    assert ev["actor_id"] == USER["id"]
    assert ev["actor_role"] == USER["role"]
    assert ev["payload"]["via"] == "email"
    assert ev["payload"]["tenant_id"] == USER["tenant_id"]


@pytest.mark.asyncio
async def test_audit_failure_does_not_break_login(monkeypatch):
    monkeypatch.setattr(oidc_mod, "oidc_enabled", lambda: True)

    async def boom(**kw):
        raise RuntimeError("audit sink down")

    monkeypatch.setattr(als, "log_event", boom)
    # 不得拋出——break-glass 在稽核故障時仍須可用
    await auth_service._audit_break_glass_login(USER, via="identifier")


@pytest.mark.asyncio
async def test_via_label_recorded(monkeypatch, audit_spy):
    monkeypatch.setattr(oidc_mod, "oidc_enabled", lambda: True)
    await auth_service._audit_break_glass_login(USER, via="identifier")
    assert audit_spy[0]["payload"]["via"] == "identifier"   # 技師 identifier 登入可分辨
