"""CR-0111 後續 — 權限矩陣授權判斷 has_permission + shadow 稽核（log-only）。

「安全半」：把矩陣讀成可判斷的授權 primitive（has_permission）+ shadow dependency
（permission_shadow，只記錄「矩陣 vs 現行寫死 role_required」落差、絕不擋），為未來
把授權收斂到矩陣（CIA / CR-0092）鋪路。本檔驗證：
  1. has_permission 依矩陣預設正確判斷（含會計 Q113 工單唯讀）
  2. 未知 resource/action fail-closed → False
  3. permission_shadow 永不 raise、永遠回 None（不改變請求結果）
  4. 矩陣會拒時記 RBAC_SHADOW_DENY；矩陣允許時不記
"""

import logging

import pytest

from core.deps import CurrentUser, permission_shadow
from services import role_service

T = "00000000-0000-0000-0000-000000000001"


def test_matrix_defaults_flatten():
    """矩陣預設（純 _flatten_matrix 層，免 DB override 跨測試污染）——SA-01 7 角色正典。"""
    rev = role_service._flatten_matrix("reviewer")
    assert "refunds.approve" in rev
    assert "work_orders.write" not in rev and "work_orders.read" in rev
    tech = role_service._flatten_matrix("technician")
    assert not any(c.endswith(".approve") for c in tech)
    assert "work_orders.write" in role_service._flatten_matrix("admin")


@pytest.mark.asyncio
async def test_has_permission_reads_overrides():
    """has_permission = 矩陣 + DB overrides（純判斷、未知 fail-closed）。"""
    assert await role_service.has_permission(
        tenant_id=T, role="admin", resource="work_orders", action="write"
    ) is True
    assert await role_service.has_permission(
        tenant_id=T, role="technician", resource="refunds", action="approve"
    ) is False


@pytest.mark.asyncio
async def test_has_permission_unknown_fail_closed():
    assert await role_service.has_permission(
        tenant_id=T, role="admin", resource="does_not_exist", action="read"
    ) is False
    assert await role_service.has_permission(
        tenant_id=T, role="admin", resource="refunds", action="does_not_exist"
    ) is False


def _user(role: str) -> CurrentUser:
    return CurrentUser(
        user_id="u1", role=role, tenant_id=T, jti="j1", token_type="access"
    )


@pytest.mark.asyncio
async def test_permission_shadow_never_blocks_and_returns_none():
    dep = permission_shadow("refunds", "approve")
    # 允許者（會計）與被拒者（技師）都不 raise、都回 None（不改變請求）
    assert await dep(user=_user("reviewer")) is None
    assert await dep(user=_user("technician")) is None


@pytest.mark.asyncio
async def test_permission_shadow_logs_on_matrix_deny(caplog):
    dep = permission_shadow("refunds", "approve")
    with caplog.at_level(logging.WARNING, logger="api.deps"):
        await dep(user=_user("technician"))  # 矩陣會拒 → 應記 RBAC_SHADOW_DENY
    assert any("RBAC_SHADOW_DENY" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_permission_shadow_no_log_when_matrix_allows(caplog):
    dep = permission_shadow("refunds", "approve")
    with caplog.at_level(logging.WARNING, logger="api.deps"):
        await dep(user=_user("admin"))  # 矩陣允許 → 不記
    assert not any("RBAC_SHADOW_DENY" in r.getMessage() for r in caplog.records)
