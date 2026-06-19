"""CR-0044 esales 已決定值 de-hardcode 測試。

業主 2026-06-19 裁決：取消費 SoT 衝突採 esales（S3=500/S4=800）；已決定值入 config。
- 純函式：DEFAULT_CANCELLATION_CONFIG s3/s4 已校正
- component（需 migration 054）：get_cancellation_config 反映 500/800；有效期讀 config 14/3
"""

from __future__ import annotations

import pytest

import core.db as db_module
from services import cancellation_service, config_service, quote_engine_service

TID = "00000000-0000-0000-0000-000000000001"


# ── 純函式：code default 已校正 ──────────────────────────────────────────────
def test_cancellation_default_fees_corrected():
    fees = cancellation_service.DEFAULT_CANCELLATION_CONFIG["fees"]
    assert fees["s2_cancellation_fee"] == 300
    assert fees["s3_cancellation_fee"] == 500  # esales CNL-S3（業主裁決）
    assert fees["s4_cancellation_fee"] == 800  # esales CNL-S4


# ── component：DB config 反映 esales 值 ──────────────────────────────────────
@pytest.mark.component
@pytest.mark.asyncio
async def test_get_cancellation_config_reflects_esales():
    assert await db_module._ensure_conn()
    cfg, _version = await config_service.get_cancellation_config(TID)
    assert cfg["fees"]["s3_cancellation_fee"] == 500
    assert cfg["fees"]["s4_cancellation_fee"] == 800


@pytest.mark.component
@pytest.mark.asyncio
async def test_validity_days_from_config():
    assert await db_module._ensure_conn()
    assert await quote_engine_service._validity_days(False) == 14
    assert await quote_engine_service._validity_days(True) == 3
