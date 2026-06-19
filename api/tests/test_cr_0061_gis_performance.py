"""CR-0061 GIS 距離 + 多維績效排序測試（審計 #10 #11）。"""
from __future__ import annotations
import pytest
from services import dispatch_service as ds


@pytest.mark.unit
def test_haversine_known_distance():
    # 信義區 ↔ 板橋區 約 13-15km
    d = ds._haversine_km(25.0330, 121.5654, 25.0098, 121.4595)
    assert 8 < d < 20


@pytest.mark.unit
def test_district_centroids_cover_service_areas():
    assert "林口區" in ds._DISTRICT_CENTROIDS
    assert "新莊區" in ds._DISTRICT_CENTROIDS


@pytest.mark.component
@pytest.mark.asyncio
async def test_enrich_adds_gis_and_performance():
    import core.db as db_module
    assert await db_module._ensure_conn()
    # 取一個有座標的 active 技師
    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE latitude IS NOT NULL AND status='active' LIMIT 1")
    row = await cur.fetchone()
    if not row:
        pytest.skip("無座標技師")
    tid = str(row[0])
    candidates = [{"technician": {"id": tid}, "score": 50.0}]
    out = await ds._enrich_gis_performance(candidates, "信義區")
    c = out[0]
    assert "performance" in c and "gis_distance_km" in c
    assert c["gis_distance_km"] is not None       # 有座標+區中心 → 真距離
    assert c["score"] >= 50.0                       # 績效 bonus 加成
