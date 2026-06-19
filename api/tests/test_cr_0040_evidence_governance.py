"""CR-0040 Evidence 治理測試（BR-M09-02 角色可見性 + BR-M09-03 保存期）。

- 純函式：_hidden_purposes 規則表（Q026）。
- component（真 DB，需 migration 048）：list 角色過濾 / get 可見性 404 / 軟刪清除 / 排除軟刪。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from services import media_service as ms

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ── 純函式：可見性規則表（Q026）─────────────────────────────────────────────
def test_hidden_purposes_brand_hides_env_photos():
    h = ms._hidden_purposes("brand_oem")
    assert "door_check_before" in h
    assert "completion_before" in h
    assert "completion_after" not in h  # 品牌看得到完工成品照
    assert "dispute_evidence_customer" not in h


def test_hidden_purposes_internal_staff_sees_all():
    for role in ("admin", "operations_manager", "dispatcher", "customer_service", "technician"):
        assert ms._hidden_purposes(role) == set()


def test_hidden_purposes_accounting_hides_door_check():
    h = ms._hidden_purposes("accounting")
    assert "door_check_before" in h
    assert "completion_after" not in h


# ── component：DB 行為 ──────────────────────────────────────────────────────
pytestmark_component = pytest.mark.component


async def _seed_wo_and_media(wo_id: str, media: list[tuple[str, str]]) -> None:
    """media = [(media_id, purpose), ...]；retention 預設 1 年後（未過期）。"""
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_address) "
        "VALUES (%s::uuid, 'completed', %s)",
        (wo_id, "測試地址 1 號"),
    )
    for media_id, purpose in media:
        await db_module._conn.execute(
            "INSERT INTO media_files "
            "  (id, tenant_id, work_order_id, purpose, filename, content_type, "
            "   size_bytes, storage_path, retention_until) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'image/jpeg', 100, %s, "
            "        NOW() + INTERVAL '1 year')",
            (media_id, DEFAULT_TENANT_ID, wo_id, purpose, f"{purpose}.jpg", f"path/{media_id}.jpg"),
        )


async def _cleanup(wo_id: str) -> None:
    await db_module._conn.execute("DELETE FROM media_files WHERE work_order_id = %s::uuid", (wo_id,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,))


@pytest.mark.component
@pytest.mark.asyncio
async def test_brand_list_excludes_env_photos():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    purposes = ["door_check_before", "completion_before", "completion_after", "dispute_evidence_customer"]
    await _seed_wo_and_media(wo_id, [(str(uuid.uuid4()), p) for p in purposes])
    try:
        brand = await ms.list_media_for_work_order(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=wo_id, role="brand_oem"
        )
        seen = {it["purpose"] for it in brand["items"]}
        assert "door_check_before" not in seen
        assert "completion_before" not in seen
        assert "completion_after" in seen  # 品牌看得到成品照
        assert "dispute_evidence_customer" in seen

        admin = await ms.list_media_for_work_order(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=wo_id, role="admin"
        )
        assert len(admin["items"]) == 4  # 內部 staff 看全部
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_get_media_hidden_purpose_404_for_brand():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    media_id = str(uuid.uuid4())
    await _seed_wo_and_media(wo_id, [(media_id, "door_check_before")])
    try:
        with pytest.raises(ApiError) as ei:
            await ms.get_media(tenant_id=DEFAULT_TENANT_ID, media_id=media_id, role="brand_oem")
        assert ei.value.status_code == 404  # 可見性擋下（不洩漏存在性）
    finally:
        await _cleanup(wo_id)


@pytest.mark.component
@pytest.mark.asyncio
async def test_soft_delete_expired_and_list_excludes():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    fresh_id = str(uuid.uuid4())
    expired_id = str(uuid.uuid4())
    await _seed_wo_and_media(wo_id, [(fresh_id, "completion_after")])
    # 插一筆已過期（retention_until 在過去）
    await db_module._conn.execute(
        "INSERT INTO media_files "
        "  (id, tenant_id, work_order_id, purpose, filename, content_type, "
        "   size_bytes, storage_path, retention_until) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'completion_after', 'old.jpg', 'image/jpeg', "
        "        100, %s, NOW() - INTERVAL '1 day')",
        (expired_id, DEFAULT_TENANT_ID, wo_id, f"path/{expired_id}.jpg"),
    )
    try:
        n = await ms.soft_delete_expired_media()
        assert n >= 1  # 至少把上面那筆過期軟刪
        # list 應只剩未過期那筆（軟刪被排除）
        res = await ms.list_media_for_work_order(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=wo_id, role="admin"
        )
        ids = {it["id"] for it in res["items"]}
        assert fresh_id in ids
        assert expired_id not in ids
    finally:
        await _cleanup(wo_id)
