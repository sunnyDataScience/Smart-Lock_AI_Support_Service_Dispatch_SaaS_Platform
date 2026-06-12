"""公單號 generate_wo_number / wo_region_code（CR-0020）DB 函式測試。

驗證：地區碼對應、ZZ fallback、{2碼地區}-{6碼流水} 格式、per-region 原子遞增。
"""

from __future__ import annotations

import re

import pytest

import core.db as db_module
from core.db import _ensure_conn

pytestmark = pytest.mark.component


async def _scalar(sql: str, *args):
    assert await _ensure_conn()
    cur = await db_module._conn.execute(sql, args or None)
    row = await cur.fetchone()
    return row[0] if row else None


@pytest.mark.asyncio
async def test_region_code_mapping_and_fallback():
    assert await _scalar("SELECT wo_region_code(%s)", "台北市大安區xx路1號") == "TP"
    assert await _scalar("SELECT wo_region_code(%s)", "高雄市三民區yy街") == "KH"
    assert await _scalar("SELECT wo_region_code(%s)", "臺中市西屯區") == "TC"  # 臺/台 異體字
    assert await _scalar("SELECT wo_region_code(%s)", "火星基地") == "ZZ"  # 解析不到
    assert await _scalar("SELECT wo_region_code(NULL)") == "ZZ"
    assert await _scalar("SELECT wo_region_code(%s)", "") == "ZZ"


@pytest.mark.asyncio
async def test_generate_wo_number_format_and_per_region_increment():
    n1 = await _scalar("SELECT generate_wo_number(%s)", "桃園市中壢區A路")
    n2 = await _scalar("SELECT generate_wo_number(%s)", "桃園市平鎮區B路")
    # {2碼大寫}-{6碼數字}
    assert re.match(r"^TY-\d{6}$", n1), n1
    assert re.match(r"^TY-\d{6}$", n2), n2
    # 同地區流水連號遞增
    assert int(n2.split("-")[1]) == int(n1.split("-")[1]) + 1


@pytest.mark.asyncio
async def test_different_regions_independent_serials():
    a = await _scalar("SELECT generate_wo_number(%s)", "基隆市仁愛區")
    b = await _scalar("SELECT generate_wo_number(%s)", "宜蘭縣羅東鎮")
    assert a.startswith("KL-")
    assert b.startswith("IL-")
    # 不同地區序列互不干擾（各自獨立計數）
    assert a.split("-")[0] != b.split("-")[0]
