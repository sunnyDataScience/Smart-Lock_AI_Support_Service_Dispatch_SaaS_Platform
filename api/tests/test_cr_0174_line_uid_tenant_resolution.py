"""CR-0174 — 多租戶 line_uid→user 反解 tenant-scoped(mocked,無需 DB)。

驗證 R29 修復:resolve_user_by_line_uid 的 step-2 users fallback
- 加 tenant 條件(封跨租戶洩漏);
- 同租戶多筆撞同 line_uid → fail-closed 回 None(HD-2);
- step-1 binding 命中則不進 step-2。

(真 DB 的跨租戶隔離已用實際 legacy user 讀取驗證:對的 tenant 找到、別的 tenant 0。)
"""

from __future__ import annotations

import pytest

import core.db as dbm
import services.line_binding_service as lbs


class _FakeCur:
    def __init__(self, rows):
        self._rows = rows

    async def fetchall(self):
        return self._rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows):
        self.calls: list[tuple] = []
        self._rows = rows

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _FakeCur(self._rows)


async def _true():
    return True


@pytest.fixture
def wire(monkeypatch):
    def install(rows, *, binding=None):
        fake = _FakeConn(rows)
        monkeypatch.setattr(lbs, "_ensure_conn", _true)
        monkeypatch.setattr(dbm, "_conn", fake)

        async def _binding(**kwargs):
            return binding
        monkeypatch.setattr(lbs, "get_active_binding", _binding)
        return fake
    return install


@pytest.mark.asyncio
async def test_fallback_tenant_scoped_single_match(wire):
    """step-2 fallback 單筆命中 → 回 user_id;SQL 帶 tenant 條件、params 帶 tenant。"""
    fake = wire([("user-1",)])
    uid = await lbs.resolve_user_by_line_uid(tenant_id="tenant-1", line_user_id="Uabc")
    assert uid == "user-1"
    sql, params = fake.calls[-1]
    assert "tenant_id" in sql                 # tenant-scoped(封跨租戶洩漏)
    assert params == ("Uabc", "tenant-1")     # 帶入 tenant


@pytest.mark.asyncio
async def test_fallback_ambiguous_fail_closed(wire):
    """同租戶多筆撞同 line_uid（資料異常）→ fail-closed 回 None(HD-2),不任意猜。"""
    wire([("u1",), ("u2",)])
    uid = await lbs.resolve_user_by_line_uid(tenant_id="tenant-1", line_user_id="Uabc")
    assert uid is None


@pytest.mark.asyncio
async def test_fallback_no_match_returns_none(wire):
    """該租戶無此 line_uid → None(fail-safe,非跨租戶洩漏)。"""
    wire([])
    uid = await lbs.resolve_user_by_line_uid(tenant_id="tenant-1", line_user_id="Uabc")
    assert uid is None


@pytest.mark.asyncio
async def test_binding_hit_skips_fallback(wire):
    """step-1 binding 命中 → 直接回,step-2 users fallback 不執行。"""
    fake = wire([("should-not-be-used",)], binding={"user_id": "bound-user"})
    uid = await lbs.resolve_user_by_line_uid(tenant_id="tenant-1", line_user_id="Uabc")
    assert uid == "bound-user"
    assert fake.calls == []  # 未觸 step-2 SELECT
