"""CR-0164 F#6（衝突②裁定）：RMA 證據保留 2y→3y（NFR-Priv-003/Aud-003 合約下限為正典）。

dispute_evidence 與保固 warranty WO 的媒體證據保留期由 2 年改 3 年（推翻 Q027 的 2 年）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import media_service

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000100")  # noqa: E501


async def _retention_years(purpose: str, work_order_id: str | None = None) -> float:
    out = await media_service.upload_media(
        tenant_id=TID, uploader_user_id=None, file_bytes=PNG + uuid.uuid4().bytes,
        filename="e.png", content_type="image/png", purpose=purpose,
        work_order_id=work_order_id)
    row = await (await db_module._conn.execute(
        "SELECT EXTRACT(YEAR FROM AGE(retention_until, created_at)) "
        "FROM media_files WHERE id=%s::uuid", (out["id"],))).fetchone()
    await db_module._conn.execute("DELETE FROM media_files WHERE id=%s::uuid", (out["id"],))
    return float(row[0])


@pytest.mark.asyncio
async def test_dispute_evidence_retention_is_3_years():
    """dispute_evidence 保留 3 年（原 2 年）。"""
    assert await db_module._ensure_conn()
    yrs = await _retention_years("dispute_evidence_customer")
    assert yrs == 3, f"RMA dispute 證據應保留 3 年，實得 {yrs}"


@pytest.mark.asyncio
async def test_non_rma_retention_stays_1_year():
    """非 RMA（完工照）保留 1 年不變。"""
    assert await db_module._ensure_conn()
    yrs = await _retention_years("completion_after")
    assert yrs == 1, f"非 RMA 證據應保留 1 年，實得 {yrs}"
