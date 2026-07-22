"""CR-0176 S2：users PII dual-write / dual-read helper 單元測試。

比照 test_cr_0176_dek_service.py：in-memory registry monkeypatch，不碰 DB。
驗證三鐵律：
  1. dual-read enc 優先（密文在手就不信明文欄——S5 DROP 前明文只是回退）
  2. 明文回退（enc 空＝backfill 前舊列，明文照回）
  3. crypto-shred fail-closed（DEK 銷毀後 enc 在也解不開 → None，不回退明文）
"""

from types import SimpleNamespace

import pytest

from services import dek_service

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def mem_registry(monkeypatch):
    """in-memory registry + 獨立 cache（同 test_cr_0176_dek_service 手法）。"""
    store: dict[str, dict] = {}
    cache: dict = {}

    async def _load(subject_user_id: str):
        rec = store.get(subject_user_id)
        return rec["wrapped"] if rec and rec["status"] == "active" else None

    async def _store(subject_user_id: str, tenant_id, wrapped: str):
        if subject_user_id in store and store[subject_user_id]["status"] == "active":
            return  # 模擬 ON CONFLICT DO NOTHING
        store[subject_user_id] = {"wrapped": wrapped, "status": "active", "tenant": tenant_id}

    async def _destroy(subject_user_id: str, actor_user_id):
        rec = store.get(subject_user_id)
        if not rec or rec["status"] != "active":
            return False
        rec.update(wrapped=None, status="destroyed")
        return True

    monkeypatch.setattr(dek_service, "_load_wrapped", _load)
    monkeypatch.setattr(dek_service, "_store_wrapped", _store)
    monkeypatch.setattr(dek_service, "_mark_destroyed", _destroy)
    monkeypatch.setattr(dek_service, "_cache", lambda: cache)
    return store


async def test_encrypt_user_pii_only_given_fields(mem_registry):
    enc = await dek_service.encrypt_user_pii("u-1", None, {"email": "a@b.tw", "phone": None})
    assert set(enc) == {"email_enc", "phone_enc"}
    assert enc["email_enc"] and enc["phone_enc"] is None  # None/空 → 密文 None


async def test_dual_read_enc_first(mem_registry):
    enc = await dek_service.encrypt_user_pii(
        "u-1", None, {"display_name": "王小明", "email": "a@b.tw", "phone": "0912345678"}
    )
    row = {
        "display_name": "decoy-明文已漂移", "email": "decoy@x", "phone": "000",
        "display_name_enc": enc["display_name_enc"],
        "email_enc": enc["email_enc"],
        "phone_enc": enc["phone_enc"],
        "role": "line_user",
    }
    out = await dek_service.decrypt_user_pii_row("u-1", row)
    assert (out["display_name"], out["email"], out["phone"]) == ("王小明", "a@b.tw", "0912345678")
    assert "display_name_enc" not in out and "email_enc" not in out and "phone_enc" not in out
    assert out["role"] == "line_user"  # 非 PII 欄原樣


async def test_dual_read_plaintext_fallback(mem_registry):
    row = {"display_name": "舊列明文", "display_name_enc": None, "email": "e@x", "email_enc": None}
    out = await dek_service.decrypt_user_pii_row("u-2", row)
    assert out["display_name"] == "舊列明文" and out["email"] == "e@x"


async def test_dual_read_shredded_fail_closed(mem_registry):
    enc = await dek_service.encrypt_user_pii("u-3", None, {"phone": "0987654321"})
    assert await dek_service.destroy_dek("u-3") is True
    out = await dek_service.decrypt_user_pii_row(
        "u-3", {"phone": "decoy-明文殘留", "phone_enc": enc["phone_enc"]}
    )
    assert out["phone"] is None  # 銷毀即不可讀：不解密、也不回退明文


async def test_dual_write_sql(mem_registry, monkeypatch):
    calls: list[tuple[str, tuple]] = []

    async def _exec(sql, params):
        calls.append((sql, params))

    monkeypatch.setattr(
        dek_service, "db_module",
        SimpleNamespace(_conn=SimpleNamespace(execute=_exec)),
    )
    await dek_service.dual_write_user_pii("u-4", "t-1", {"display_name": "阿明", "phone": None})
    assert len(calls) == 1
    sql, params = calls[0]
    assert "display_name_enc = %s" in sql and "phone_enc = %s" in sql
    assert "WHERE id = %s::uuid" in sql
    assert params[-1] == "u-4" and params[1] is None  # phone None → 密文 None
    # 回寫的 display_name 密文可解回原文
    assert await dek_service.decrypt_pii("u-4", params[0]) == "阿明"


async def test_dual_write_empty_noop(mem_registry, monkeypatch):
    async def _boom(sql, params):  # pragma: no cover — 不該被呼叫
        raise AssertionError("空 fields 不應執行 SQL")

    monkeypatch.setattr(
        dek_service, "db_module",
        SimpleNamespace(_conn=SimpleNamespace(execute=_boom)),
    )
    await dek_service.dual_write_user_pii("u-5", None, {})
