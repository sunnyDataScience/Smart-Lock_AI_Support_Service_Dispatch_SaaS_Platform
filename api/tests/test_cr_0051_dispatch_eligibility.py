"""CR-0051 派工資格 gate 測試（BR-M06 / G004-G005）。

生命週期不可派工狀態（未核准/停權/終止/退回）一律排除候選，與操作性 circuit 區分。
"""
from __future__ import annotations
import pytest
from services import dispatch_service as ds


@pytest.mark.unit
@pytest.mark.parametrize("status, eligible", [
    ("active", True),
    ("inactive", True),          # 操作性不可用，但生命週期仍合格（由 circuit 排除）
    ("on_leave", True),
    ("pending_approval", False),  # 未核准
    ("suspended", False),         # 停權
    ("terminated", False),        # 終止
    ("rejected", False),          # 退回
])
def test_is_dispatch_eligible(status, eligible):
    assert ds._is_dispatch_eligible(status) is eligible


@pytest.mark.unit
def test_score_rows_excludes_ineligible():
    """合成 row：suspended 技師不入候選，active 入。"""
    def _row(status):
        # 對齊 _TECH_SELECT：status 在 index 9；其餘欄位 best-effort 佔位
        r = [None] * 12
        r[0] = "00000000-0000-0000-0000-000000000099"  # id
        r[2] = "技師"          # name (位置依 _tech_row_to_dict 容錯)
        r[9] = status
        return tuple(r)
    out = ds._score_rows([_row("suspended"), _row("active")], brand="Yale", district="信義區")
    statuses = {c["technician"].get("status") for c in out}
    assert "suspended" not in statuses
