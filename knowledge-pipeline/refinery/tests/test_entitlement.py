"""CR-0166 R3：refinery 模組 License 開通 gate（純邏輯，不需 DB）。"""

import os

import pytest

from refinery import entitlement


def test_core_env_skip(monkeypatch):
    """REFINERY_SKIP_ENTITLEMENT=1 → 恆放行。"""
    monkeypatch.setenv("REFINERY_SKIP_ENTITLEMENT", "1")
    assert entitlement.is_refinery_entitled("00000000-0000-0000-0000-000000000001") is True


def test_no_platform_db_fail_open(monkeypatch):
    """無 PLATFORM_POSTGRES_URI（單庫 dev）→ fail-open 放行。"""
    monkeypatch.delenv("REFINERY_SKIP_ENTITLEMENT", raising=False)
    monkeypatch.delenv("PLATFORM_POSTGRES_URI", raising=False)
    assert entitlement.is_refinery_entitled("00000000-0000-0000-0000-000000000001") is True


def test_invalid_tenant_fail_closed(monkeypatch):
    """有平台庫但 tenant 非 UUID → fail-closed。"""
    monkeypatch.delenv("REFINERY_SKIP_ENTITLEMENT", raising=False)
    monkeypatch.setenv("PLATFORM_POSTGRES_URI", "postgresql://x/y")
    assert entitlement.is_refinery_entitled("not-a-uuid") is False


def test_assert_raises(monkeypatch):
    monkeypatch.delenv("REFINERY_SKIP_ENTITLEMENT", raising=False)
    monkeypatch.setenv("PLATFORM_POSTGRES_URI", "postgresql://x/y")
    with pytest.raises(entitlement.ModuleNotEntitledError):
        entitlement.assert_refinery_entitled("not-a-uuid")
