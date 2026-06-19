"""CR-0039 完工硬閘測試（BR-M08-03，業主裁決 §8）。

component（真 DB；需 work_orders / digital_signatures 表）：直接測
work_order_service._enforce_completion_gate 三道硬閘 + 主管 override 路徑。
門檻讀 M18 config completion_policy（migration 047；缺則 fallback 預設 min_photos=3）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

pytestmark = pytest.mark.component

# digital_signatures.signer_id 有 FK → users；用既有 admin seed uuid（_signature_exists 只看
# document_id + signer_role='customer'，signer 是誰不影響閘判定）。
_SEED_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"


async def _insert_customer_signature(wo_id: str) -> None:
    await db_module._conn.execute(
        "INSERT INTO digital_signatures "
        "  (signer_id, signer_role, document_type, document_id, "
        "   signature_method, signature_data, integrity_hash) "
        "VALUES (%s, 'customer', 'work_order', %s::uuid, 'canvas', '{}'::jsonb, %s)",
        (_SEED_USER_ID, wo_id, f"hash-{wo_id[:8]}"),
    )


async def _insert_wo(wo_id: str, *, service_category: str, serial: str | None = None) -> None:
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address, service_category, serial_number) "
        "VALUES (%s::uuid, 'in_progress', %s, %s, %s)",
        (wo_id, "測試地址 1 號", service_category, serial),
    )


async def _cleanup(wo_id: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM digital_signatures WHERE document_id = %s::uuid", (wo_id,)
    )
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,))


async def _gate(**kw):
    """跑 _enforce_completion_gate，預設＝足量證據的快樂路徑，由 kw 覆寫單一條件。"""
    base = dict(
        wo_id=str(uuid.uuid4()),
        summary="完工",
        photo_evidence_ids=["p1", "p2", "p3"],
        signature_evidence_id="sig-1",
        is_override=False,
        override_reason=None,
        actor_role=None,
    )
    base.update(kw)
    return await svc._enforce_completion_gate(**base)


# ── 照片門檻 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_insufficient_photos_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(photo_evidence_ids=["p1", "p2"])  # 2 < 3
    assert ei.value.status_code == 422
    assert ei.value.error_code == "INSUFFICIENT_PHOTOS"


# ── 簽名驗證（HD-4 真存在）──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_signature_required_when_no_record_422():
    """3 照片但簽名紀錄不存在（fake wo）→ 422 SIGNATURE_REQUIRED。"""
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(wo_id=str(uuid.uuid4()), signature_evidence_id="sig-1")
    assert ei.value.error_code == "SIGNATURE_REQUIRED"


@pytest.mark.asyncio
async def test_signature_required_when_id_empty_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(signature_evidence_id=None)
    assert ei.value.error_code == "SIGNATURE_REQUIRED"


# ── serial gate（HD-3 只 install）+ 快樂路徑 ─────────────────────────────────
@pytest.mark.asyncio
async def test_repair_with_signature_passes():
    """維修案（非 serial 類別）+ 3 照片 + 簽名存在 → 通過，回原 summary。"""
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id, service_category="repair")
    await _insert_customer_signature(wo_id)
    try:
        out = await _gate(wo_id=wo_id)
        assert out == "完工"
    finally:
        await _cleanup(wo_id)


@pytest.mark.asyncio
async def test_install_without_serial_422():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id, service_category="install", serial=None)
    await _insert_customer_signature(wo_id)
    try:
        with pytest.raises(ApiError) as ei:
            await _gate(wo_id=wo_id)
        assert ei.value.error_code == "SERIAL_REQUIRED"
    finally:
        await _cleanup(wo_id)


@pytest.mark.asyncio
async def test_install_with_serial_passes():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id, service_category="install", serial="SN-CR39-001")
    await _insert_customer_signature(wo_id)
    try:
        out = await _gate(wo_id=wo_id)
        assert out == "完工"
    finally:
        await _cleanup(wo_id)


# ── 主管 override（HD-2）──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_override_requires_reason_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(is_override=True, override_reason=None, photo_evidence_ids=[])
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_override_with_reason_skips_evidence():
    """override + reason：0 照片、無簽名也通過，summary 加稽核註記。"""
    assert await db_module._ensure_conn()
    out = await _gate(
        is_override=True,
        override_reason="主管放行：客戶趕時間",
        actor_role="operations_manager",
        photo_evidence_ids=[],
        signature_evidence_id=None,
    )
    assert "COMPLETE_OVERRIDE" in out
    assert "主管放行" in out
    assert "operations_manager" in out
