"""CR-0153:三庫 URI 啟動守衛(ADR-020 Consequences,opt-in DB_URI_STRICT=1)。"""

from __future__ import annotations

import pytest

from core.db import assert_uri_strict

pytestmark = pytest.mark.unit


def test_default_off_is_noop(monkeypatch):
    monkeypatch.delenv("DB_URI_STRICT", raising=False)
    monkeypatch.delenv("POSTGRES_URI", raising=False)
    assert_uri_strict()  # 不 raise:預設關閉,pytest/本機 fallback 不變


def test_strict_missing_main_uri_raises(monkeypatch):
    monkeypatch.setenv("DB_URI_STRICT", "1")
    monkeypatch.setenv("API_SURFACE", "dispatch")
    monkeypatch.delenv("POSTGRES_URI", raising=False)
    with pytest.raises(RuntimeError, match="POSTGRES_URI"):
        assert_uri_strict()


def test_strict_tech_surface_requires_tech_uri(monkeypatch):
    monkeypatch.setenv("DB_URI_STRICT", "1")
    monkeypatch.setenv("API_SURFACE", "tech")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://x/y")
    monkeypatch.delenv("TECH_POSTGRES_URI", raising=False)
    with pytest.raises(RuntimeError, match="TECH_POSTGRES_URI"):
        assert_uri_strict()
    monkeypatch.setenv("TECH_POSTGRES_URI", "postgresql://x/tech")
    assert_uri_strict()  # 齊備即過


def test_strict_platform_surface_requires_platform_uri(monkeypatch):
    monkeypatch.setenv("DB_URI_STRICT", "1")
    monkeypatch.setenv("API_SURFACE", "platform")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://x/y")
    monkeypatch.delenv("PLATFORM_POSTGRES_URI", raising=False)
    monkeypatch.setenv("TECH_POSTGRES_URI", "postgresql://x/tech")
    with pytest.raises(RuntimeError, match="PLATFORM_POSTGRES_URI"):
        assert_uri_strict()
    monkeypatch.setenv("PLATFORM_POSTGRES_URI", "postgresql://x/pf")
    assert_uri_strict()


def test_strict_platform_surface_requires_tech_uri(monkeypatch):
    """0724 split-brain 實案：平台面操作技師生命週期（寫權威庫），漏掛
    TECH_POSTGRES_URI 時核准寫進投影庫——平台頁顯示啟用中、技師登入仍
    ACCOUNT_PENDING_APPROVAL。平台面必須同時要求技師庫 URI（fail-fast）。"""
    monkeypatch.setenv("DB_URI_STRICT", "1")
    monkeypatch.setenv("API_SURFACE", "platform")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://x/y")
    monkeypatch.setenv("PLATFORM_POSTGRES_URI", "postgresql://x/pf")
    monkeypatch.delenv("TECH_POSTGRES_URI", raising=False)
    with pytest.raises(RuntimeError, match="TECH_POSTGRES_URI"):
        assert_uri_strict()
    monkeypatch.setenv("TECH_POSTGRES_URI", "postgresql://x/tech")
    assert_uri_strict()
