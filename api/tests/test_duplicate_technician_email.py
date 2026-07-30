"""同 email 同角色重複帳號的兩層防線（2026-07-30 稽核發現）。

發現經過：`users.email` **沒有唯一索引**（實測技師權威庫只有非唯一的
`idx_users_email_tenant`），而自助註冊有 EMAIL_TAKEN 檢查
（auth_service.py:640-647）、平台代建卻**完全沒有**——所以平台管理員可以
造出兩列 role='technician' 同 email。而登入 lookup 是 `LIMIT 1` 且原本
**沒有 ORDER BY**，兩列並存時 planner 任意挑一列 → 同一組帳密可能今天登進
A 帳號、明天登進 B 帳號。

兩層防線：
- 寫入面（根治）：平台代建補 EMAIL_TAKEN，與自助註冊同一條規則
- 讀取面（第二層）：登入 lookup 加 ORDER BY 讓它至少**確定**，並在偵測到
  重複時 fail-loud（不擋登入——擋了等於把使用者鎖在門外）

注意這條規則是**角色內唯一**、不是全域唯一：同一個 email 可以同時是技師與
廠商（CR-0090 明訂，登入端點以 role 過濾故不衝突）。全域唯一索引會打壞
既有的 seed 設計（test@lock-ai.com 同時有 admin 列與 technician 列）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import auth_service

pytestmark = pytest.mark.component

PLATFORM_TECH = "/api/v1/platform/technicians"


# ── 寫入面：平台代建的 EMAIL_TAKEN ──────────────────────────────────────────


async def _cleanup(tech_id: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id=%s::uuid", (tech_id,))


@pytest.mark.asyncio
async def test_platform_create_rejects_duplicate_technician_email(
    client, platform_admin_headers
):
    """同 email 建第二位技師 → 409 EMAIL_TAKEN（原本會靜默建出重複帳號）。"""
    suffix = uuid.uuid4().hex[:8]
    email = f"dup-tech-{suffix}@example.com"
    first = await client.post(
        PLATFORM_TECH, headers=platform_admin_headers,
        json={"display_name": f"重複測試甲{suffix}", "coverage_areas": ["台北市"],
              "phone": "0911223344", "email": email},
    )
    assert first.status_code == 201, first.text
    tech_id = first.json()["data"]["id"]
    try:
        # 刻意用**不同姓名**，避開 tenant+name 的冪等鍵——否則會回既有列（200）
        # 而不是真的嘗試插入，測不到 email 這條防線。
        second = await client.post(
            PLATFORM_TECH, headers=platform_admin_headers,
            json={"display_name": f"重複測試乙{suffix}", "coverage_areas": ["台北市"],
                  "phone": "0911223355", "email": email},
        )
        assert second.status_code == 409, second.text
        assert second.json()["error_code"] == "EMAIL_TAKEN"  # RFC7807 legacy 擴充欄
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_platform_create_without_email_still_works(client, platform_admin_headers):
    """email 選填——不給 email 不該被新檢查誤擋。"""
    suffix = uuid.uuid4().hex[:8]
    res = await client.post(
        PLATFORM_TECH, headers=platform_admin_headers,
        json={"display_name": f"無信箱測試{suffix}", "coverage_areas": ["台北市"]},
    )
    assert res.status_code == 201, res.text
    await _cleanup(res.json()["data"]["id"])


# ── 讀取面：登入 lookup 的確定性 ────────────────────────────────────────────


class _Cur:
    """fetchone / fetchall 都實作——這樣反向驗證（把修正 stash 掉）時，測試會因為
    「SQL 少了 ORDER BY」「重複時沒留 log」這些**真正的斷言**而紅，
    而不是因為 mock 缺方法炸掉。假 mock 會讓反向驗證變成假訊號。"""

    def __init__(self, rows):
        self._rows = rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return self._rows


class _Conn:
    """記下實際下的 SQL，供斷言 ORDER BY 真的送出去了。"""

    def __init__(self, rows):
        self._rows = rows
        self.sql = None

    async def execute(self, sql, params=None):
        self.sql = sql
        return _Cur(self._rows)


def _user_row(uid, email):
    return (uid, email, "hash", "technician", str(uuid.uuid4()), True, None)


@pytest.mark.asyncio
async def test_login_lookup_is_deterministic(monkeypatch):
    """有重複列時取查詢回傳的第一列，且 SQL 必須帶 ORDER BY（否則順序無意義）。"""
    old, new = str(uuid.uuid4()), str(uuid.uuid4())
    conn = _Conn([_user_row(old, "a@example.com"), _user_row(new, "a@example.com")])

    async def _fake_conn(role_in):
        return conn

    monkeypatch.setattr(auth_service, "_login_lookup_conn", _fake_conn)
    found = await auth_service._find_user_by_email("a@example.com", ["technician"])
    assert found is not None
    assert found["id"] == old, "應取排序後的第一列（最早建立），不是任意一列"
    assert "ORDER BY" in conn.sql.upper(), "沒有 ORDER BY 的話 LIMIT 取哪列由 planner 決定"


@pytest.mark.asyncio
async def test_login_lookup_logs_when_duplicated(monkeypatch, caplog):
    """撞到重複帳號要留下訊號——否則只會在無法重現的客訴裡浮現。"""
    conn = _Conn([_user_row(str(uuid.uuid4()), "a@example.com"),
                  _user_row(str(uuid.uuid4()), "a@example.com")])

    async def _fake_conn(role_in):
        return conn

    monkeypatch.setattr(auth_service, "_login_lookup_conn", _fake_conn)
    with caplog.at_level("ERROR", logger="api.auth_service"):
        await auth_service._find_user_by_email("a@example.com", ["technician"])
    assert any("重複帳號" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_login_lookup_single_row_unchanged(monkeypatch, caplog):
    """正常單列：行為不變、不得誤報重複。"""
    uid = str(uuid.uuid4())
    conn = _Conn([_user_row(uid, "a@example.com")])

    async def _fake_conn(role_in):
        return conn

    monkeypatch.setattr(auth_service, "_login_lookup_conn", _fake_conn)
    with caplog.at_level("ERROR", logger="api.auth_service"):
        found = await auth_service._find_user_by_email("a@example.com", ["technician"])
    assert found["id"] == uid
    assert not any("重複帳號" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_login_lookup_no_rows_returns_none(monkeypatch):
    conn = _Conn([])

    async def _fake_conn(role_in):
        return conn

    monkeypatch.setattr(auth_service, "_login_lookup_conn", _fake_conn)
    assert await auth_service._find_user_by_email("nobody@example.com", ["technician"]) is None
