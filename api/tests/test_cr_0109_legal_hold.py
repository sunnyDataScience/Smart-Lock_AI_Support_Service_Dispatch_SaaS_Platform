"""CR-0109 媒體法務保留（legal_hold）手動設定面測試。

  LH-1 PATCH hold=true → 200 + legal_hold=true；工單 media 列表該筆 legal_hold=true
  LH-2 PATCH hold=false → 解除
  LH-3 cross-tenant → 403
  LH-4 不存在 media → 404
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from tests.conftest import DEFAULT_TENANT_ID

OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000099"


async def _insert_media() -> tuple[str, str]:
    """建 work_order（FK 需要）+ media_files，回 (media_id, work_order_id)。"""
    import core.db as db_module

    await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    media_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, tenant_id) VALUES (%s::uuid, %s::uuid)",
        (wo_id, DEFAULT_TENANT_ID),
    )
    await db_module._conn.execute(
        "INSERT INTO media_files "
        "  (id, tenant_id, work_order_id, purpose, filename, content_type, size_bytes, "
        "   storage_path, sha256, retention_until, legal_hold) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'completion_after', 'lh-test.jpg', 'image/jpeg', "
        "        1234, %s, %s, NOW() + make_interval(years => 1), FALSE)",
        (media_id, DEFAULT_TENANT_ID, wo_id, f"test/{media_id}.jpg", uuid.uuid4().hex),
    )
    return media_id, wo_id


async def _cleanup(media_id: str, wo_id: str) -> None:
    import core.db as db_module

    if not await db_module._ensure_conn():
        return
    await db_module._conn.execute("DELETE FROM media_files WHERE id = %s::uuid", (media_id,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,))


def _path(media_id: str, tenant: str = DEFAULT_TENANT_ID) -> str:
    return f"/tenants/{tenant}/media/{media_id}/legal-hold"


@pytest.mark.asyncio
@pytest.mark.component
async def test_set_and_release_legal_hold(client, admin_headers):
    """LH-1/LH-2：設定 → 列表反映 → 解除。"""
    media_id, wo_id = await _insert_media()
    try:
        # 設定
        r = await client.patch(_path(media_id), json={"hold": True, "reason": "爭議調查中"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["legal_hold"] is True

        # 工單 media 列表反映 legal_hold
        lst = await client.get(
            f"/tenants/{DEFAULT_TENANT_ID}/work-orders/{wo_id}/media", headers=admin_headers
        )
        assert lst.status_code == 200, lst.text
        item = next((m for m in lst.json()["items"] if m["id"] == media_id), None)
        assert item is not None and item["legal_hold"] is True

        # 解除
        r2 = await client.patch(_path(media_id), json={"hold": False}, headers=admin_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["legal_hold"] is False
    finally:
        await _cleanup(media_id, wo_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_cross_tenant_403(client, admin_headers):
    """LH-3：cross-tenant → 403。"""
    media_id, wo_id = await _insert_media()
    try:
        r = await client.patch(_path(media_id, OTHER_TENANT_ID), json={"hold": True}, headers=admin_headers)
        assert r.status_code == 403, r.text
    finally:
        await _cleanup(media_id, wo_id)


@pytest.mark.asyncio
@pytest.mark.component
async def test_not_found_404(client, admin_headers):
    """LH-4：不存在 media → 404。"""
    r = await client.patch(_path(str(uuid.uuid4())), json={"hold": True}, headers=admin_headers)
    assert r.status_code == 404, r.text
