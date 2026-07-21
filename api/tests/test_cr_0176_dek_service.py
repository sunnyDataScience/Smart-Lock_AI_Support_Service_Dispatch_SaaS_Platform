"""CR-0176：dek_service crypto-shred 全流程測試（in-memory registry，不碰 DB）。

以 monkeypatch 把三個 registry 存取函式換成 in-memory store，證明端到端：
  encrypt_pii → decrypt_pii 可讀 → destroy_dek → decrypt_pii 回 None（不可讀），
且 **shred subject A 不影響 subject B**（per-subject 隔離的服務層證明）。
"""

from __future__ import annotations

import pytest

from services import dek_service


@pytest.fixture
def mem_registry(monkeypatch):
    """in-memory DEK registry：{subject: {"wrapped": str|None, "status": str}}。"""
    store: dict[str, dict] = {}

    async def _load(subject):
        rec = store.get(subject)
        return rec["wrapped"] if rec and rec["status"] == "active" else None

    async def _store(subject, tenant, wrapped):
        # ON CONFLICT DO NOTHING：已有 active 不覆寫
        if subject not in store or store[subject]["status"] != "active":
            store[subject] = {"wrapped": wrapped, "status": "active", "tenant": tenant}

    async def _destroy(subject, actor):
        rec = store.get(subject)
        if rec and rec["status"] == "active":
            rec.update(wrapped=None, status="destroyed", destroyed_by=actor)
            return True
        return False

    monkeypatch.setattr(dek_service, "_load_wrapped", _load)
    monkeypatch.setattr(dek_service, "_store_wrapped", _store)
    monkeypatch.setattr(dek_service, "_mark_destroyed", _destroy)
    # 每測試乾淨、隔離的 cache（避開 ContextVar 跨測試傳播）
    cache: dict = {}
    monkeypatch.setattr(dek_service, "_cache", lambda: cache)
    return store


@pytest.mark.asyncio
async def test_encrypt_then_decrypt_roundtrip(mem_registry):
    ct = await dek_service.encrypt_pii("subject-A", "tenant-1", "0912345678")
    assert ct and ct != "0912345678"
    assert await dek_service.decrypt_pii("subject-A", ct) == "0912345678"


@pytest.mark.asyncio
async def test_destroy_makes_pii_unreadable(mem_registry):
    ct = await dek_service.encrypt_pii("subject-A", "tenant-1", "王小明")
    assert await dek_service.decrypt_pii("subject-A", ct) == "王小明"

    destroyed = await dek_service.destroy_dek("subject-A", actor_user_id="admin-1")
    assert destroyed is True
    # crypto-shred 後：同一密文再也解不出（DEK 已 tombstone）
    assert await dek_service.decrypt_pii("subject-A", ct) is None
    assert mem_registry["subject-A"]["status"] == "destroyed"
    assert mem_registry["subject-A"]["wrapped"] is None


@pytest.mark.asyncio
async def test_shred_isolation_between_subjects(mem_registry):
    ct_a = await dek_service.encrypt_pii("subject-A", "t", "AAA")
    ct_b = await dek_service.encrypt_pii("subject-B", "t", "BBB")

    await dek_service.destroy_dek("subject-A")

    assert await dek_service.decrypt_pii("subject-A", ct_a) is None   # A 已 shred
    assert await dek_service.decrypt_pii("subject-B", ct_b) == "BBB"  # B 不受影響


@pytest.mark.asyncio
async def test_destroy_without_dek_is_noop(mem_registry):
    # 尚無加密 PII 的 subject（過渡期）→ destroy 回 False，不報錯
    assert await dek_service.destroy_dek("subject-never-encrypted") is False


@pytest.mark.asyncio
async def test_reuse_existing_active_dek(mem_registry):
    ct1 = await dek_service.encrypt_pii("subject-A", "t", "one")
    ct2 = await dek_service.encrypt_pii("subject-A", "t", "two")
    # 兩次加密用同一把 active DEK（registry 只一筆 active）
    assert await dek_service.decrypt_pii("subject-A", ct1) == "one"
    assert await dek_service.decrypt_pii("subject-A", ct2) == "two"
    assert sum(1 for r in mem_registry.values() if r["status"] == "active") == 1
