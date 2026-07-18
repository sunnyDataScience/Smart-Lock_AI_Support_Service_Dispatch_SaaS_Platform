"""第二輪代理 UAT 修復回歸測試（2026-07-18，api 分區）。

- P1-B：手建問題卡（conversation_id=NULL）建報價 404 → LEFT JOIN + COALESCE tenant guard。
- R1：師傅生命週期非原子——鏡射失敗補償回滾權威庫＋無稽核殘留；成功路徑稽核必寫。
- R2：A2 停權踢出 fail-open——technician 於雙庫模式安全狀態讀權威庫、讀不到 fail-closed 503。
- W4-3：技師停用原因讀權威庫（張冠李戴修復，結構性驗證＋功能驗證）。
- W4-6：ACCOUNT_LOCKED 已釘契約（觸發鎖定那次＋鎖定期間都 403 含剩餘分鐘）。
- W3-3：註冊自填證照鏡射品牌庫投影。
- W1-1：月結對 co-sign 已建結算的對帳單不再重複建結算。
- W1-2：對帳駁回端點（pending→rejected＋審計欄位；409/422 語意）。
- W1-3：未收帳款口徑＝draft+issued（結構性驗證）。
- W5-2：push_notification 落庫後 WS 推播（fail-soft）。
- W5-3：工單自動通知帶 related_entity 可點跳轉。
- W5-8：SLA 告警 WS 白名單放行 customer_service / dispatcher。
- W2-4：consumer track last_update_at＝真實更新時間＋獨立 scheduled_at 欄位。
- W5-4：進線案件三關聯欄（conversation/problem_card/work_order）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.db as db_module
from core.errors import ApiError
from tests.conftest import ADMIN_USER_ID, DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


# ────────────────────────────────────────────────────────────────────────────
# P1-B：手建卡（conversation_id=NULL）建報價
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_p1b_manual_card_create_quote_succeeds():
    """手建卡（conversation_id=NULL）建報價不再 404。"""
    from services import quote_engine_service

    assert await db_module._ensure_conn()
    pc_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
        "VALUES (%s::uuid, %s::uuid, NULL, 'Yale', 'YDM7116', 'confirmed')",
        (pc_id, TID),
    )
    try:
        quote = await quote_engine_service.create_quote(
            tenant_id=TID, problem_card_id=pc_id,
        )
        assert quote["id"]
        assert quote["state"] == "draft"
    finally:
        await db_module._conn.execute(
            "DELETE FROM quote WHERE problem_card_id = %s::uuid", (pc_id,))
        await db_module._conn.execute(
            "DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,))


def test_p1b_no_remaining_inner_join_conversations_in_quote_engine():
    """quote_engine 存在性檢查不再 INNER JOIN conversations。"""
    import inspect

    from services import quote_engine_service
    src = inspect.getsource(quote_engine_service.create_quote)
    assert "LEFT JOIN conversations" in src
    assert "COALESCE(pc.tenant_id, u.tenant_id)" in src


# ────────────────────────────────────────────────────────────────────────────
# R1：生命週期鏡射失敗補償回滾
# ────────────────────────────────────────────────────────────────────────────


async def _mk_technician(status: str = "pending_approval") -> tuple[str, str]:
    """建 user(role=technician, is_active 依 status) + technician。回 (tech_id, user_id)。"""
    from core.auth import hash_password

    assert await db_module._ensure_conn()
    user_id, tech_id = str(uuid.uuid4()), str(uuid.uuid4())
    email = f"uat2-tech-{user_id[:8]}@example.com"
    # 手機刻意避開種子 demo-tech 的 0911222333（避免手機歧義 409 污染他測試）
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, phone, password_hash, "
        " role, is_active) "
        "VALUES (%s::uuid, %s::uuid, 'UAT2技師', %s, '0911777444', %s, 'technician', %s)",
        (user_id, TID, email, hash_password("Sup3rSecret!"), status == "active"),
    )
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'UAT2技師', '0911777444', %s)",
        (tech_id, TID, user_id, status),
    )
    return tech_id, user_id


async def _rm_technician(tech_id: str, user_id: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id = %s::uuid",
        (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest.mark.asyncio
async def test_r1_mirror_failure_reverts_authority_and_no_audit(monkeypatch):
    """鏡射失敗 → 權威庫狀態回滾（status/is_active 不變）＋無稽核殘留＋500 如實回報。"""
    from services import technician_lifecycle_service as svc

    tech_id, user_id = await _mk_technician("pending_approval")

    async def _boom(table, ids):
        raise RuntimeError("模擬鏡射炸裂（UndefinedColumn 類）")

    monkeypatch.setattr(svc, "mirror_rows", _boom)
    try:
        with pytest.raises(ApiError) as e:
            await svc.approve_onboarding(
                tenant_id=TID, tech_id=tech_id, actor_user_id=ADMIN_USER_ID,
            )
        assert e.value.error_code == "MIRROR_FAILED"
        assert e.value.status_code == 500

        cur = await db_module._conn.execute(
            "SELECT status FROM technicians WHERE id = %s::uuid", (tech_id,))
        assert (await cur.fetchone())[0] == "pending_approval", "權威庫 status 應回滾"

        cur = await db_module._conn.execute(
            "SELECT is_active FROM users WHERE id = %s::uuid", (user_id,))
        assert (await cur.fetchone())[0] is False, "users.is_active 應回滾"

        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM saas.technician_lifecycle_event "
            "WHERE technician_id = %s::uuid", (tech_id,))
        assert (await cur.fetchone())[0] == 0, "不得有稽核殘留"
    finally:
        await _rm_technician(tech_id, user_id)


@pytest.mark.asyncio
async def test_r1_success_path_always_writes_audit():
    """成功路徑：核准後稽核一定寫入（單庫 fallback 鏡射 no-op）。"""
    from services import technician_lifecycle_service as svc

    tech_id, user_id = await _mk_technician("pending_approval")
    try:
        result = await svc.approve_onboarding(
            tenant_id=TID, tech_id=tech_id, actor_user_id=ADMIN_USER_ID,
        )
        assert result["new_status"] == "active"

        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM saas.technician_lifecycle_event "
            "WHERE technician_id = %s::uuid AND event_type = 'onboarding_approved'",
            (tech_id,))
        assert (await cur.fetchone())[0] == 1, "成功路徑稽核必寫"

        cur = await db_module._conn.execute(
            "SELECT is_active FROM users WHERE id = %s::uuid", (user_id,))
        assert (await cur.fetchone())[0] is True
    finally:
        await _rm_technician(tech_id, user_id)


# ────────────────────────────────────────────────────────────────────────────
# R2：technician 安全狀態讀權威庫 + fail-closed
# ────────────────────────────────────────────────────────────────────────────


class _FakeCur:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeAuthorityConn:
    """模擬技師權威庫連線（回固定 users 安全狀態列）。"""

    def __init__(self, row):
        self._row = row

    async def execute(self, sql, params=None):
        return _FakeCur(self._row)


@pytest.mark.asyncio
async def test_r2_technician_state_reads_authority(monkeypatch):
    """雙庫模式：technician 安全狀態讀權威庫（非品牌投影）。"""
    from core import auth as core_auth

    fake = _FakeAuthorityConn((False, None))  # 權威庫：已停權

    monkeypatch.setattr(db_module, "tech_db_enabled", lambda: True)

    async def _fake_tech_conn():
        return fake

    monkeypatch.setattr(db_module, "require_tech_conn", _fake_tech_conn)

    state = await core_auth.load_user_security_state(str(uuid.uuid4()), "technician")
    assert state is not None
    assert state["is_active"] is False


@pytest.mark.asyncio
async def test_r2_technician_authority_down_fail_closed(monkeypatch):
    """雙庫模式：權威庫讀取失敗 → 503 fail-closed（拒絕請求，不放行）。"""
    from core import auth as core_auth

    monkeypatch.setattr(db_module, "tech_db_enabled", lambda: True)

    async def _down():
        raise RuntimeError("Tech DB unavailable")

    monkeypatch.setattr(db_module, "require_tech_conn", _down)

    with pytest.raises(ApiError) as e:
        await core_auth.load_user_security_state(str(uuid.uuid4()), "technician")
    assert e.value.error_code == "SECURITY_STATE_UNAVAILABLE"
    assert e.value.status_code == 503

    # security_state_verifiable 同步反映不可驗
    assert await core_auth.security_state_verifiable("technician") is False


@pytest.mark.asyncio
async def test_r2_non_technician_unaffected(monkeypatch):
    """非 technician 角色不受權威庫路由影響（單庫語意不變）。"""
    from core import auth as core_auth

    monkeypatch.setattr(db_module, "tech_db_enabled", lambda: True)

    async def _down():
        raise RuntimeError("Tech DB unavailable")

    monkeypatch.setattr(db_module, "require_tech_conn", _down)

    # admin 走主連線——不 raise（fail-open：查無回 None 或回真實列）
    state = await core_auth.load_user_security_state(str(uuid.uuid4()), "admin")
    assert state is None  # 隨機 uuid 查無 → None


# ────────────────────────────────────────────────────────────────────────────
# W4-3：停用原因讀權威庫（兩源合一）
# ────────────────────────────────────────────────────────────────────────────


def test_w4_3_disabled_reason_reads_authority_source():
    """_technician_disabled_reason 走 require_tech_conn（權威庫路由）。"""
    import inspect

    from services import auth_service
    src = inspect.getsource(auth_service._technician_disabled_reason)
    assert "require_tech_conn" in src


@pytest.mark.asyncio
async def test_w4_3_suspended_login_message(client):
    """停權技師登入 → 403 ACCOUNT_SUSPENDED「帳號已停權，請聯繫平台管理員」。"""
    tech_id, user_id = await _mk_technician("suspended")
    cur = await db_module._conn.execute(
        "SELECT email FROM users WHERE id = %s::uuid", (user_id,))
    email = (await cur.fetchone())[0]
    try:
        r = await client.post(
            "/api/v1/technicians/login",
            json={"identifier": email, "password": "Sup3rSecret!"},
        )
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["error_code"] == "ACCOUNT_SUSPENDED"
        assert "停權" in body["message"]
    finally:
        await _rm_technician(tech_id, user_id)


# ────────────────────────────────────────────────────────────────────────────
# W4-6：ACCOUNT_LOCKED 已釘契約
# ────────────────────────────────────────────────────────────────────────────


async def _mk_login_user() -> tuple[str, str, str]:
    from core.auth import hash_password

    assert await db_module._ensure_conn()
    user_id = str(uuid.uuid4())
    email = f"uat2-lock-{user_id[:8]}@example.com"
    password = "Sup3rSecret!"
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, email, password_hash, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, 'UAT2鎖定', %s, %s, 'admin', TRUE)",
        (user_id, TID, email, hash_password(password)),
    )
    return user_id, email, password


@pytest.mark.asyncio
async def test_w4_6_lockout_contract(client):
    """1-4 次錯誤 → 401 通用訊息；第 5 次（觸發鎖定）→ 403 ACCOUNT_LOCKED；
    鎖定期間正確密碼也 403 ACCOUNT_LOCKED 含剩餘分鐘。"""
    user_id, email, password = await _mk_login_user()
    try:
        for _ in range(4):
            r = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": "WrongPass99"})
            assert r.status_code == 401, r.text
            assert r.json()["error_code"] == "UNAUTHENTICATED"
            # 通用訊息，不洩剩餘次數
            assert "帳號或密碼錯誤" in r.json()["message"]

        # 第 5 次（觸發鎖定那一次）也回 ACCOUNT_LOCKED（已釘契約）
        r = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "WrongPass99"})
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["error_code"] == "ACCOUNT_LOCKED"
        assert "分鐘後再試" in body["detail"]

        # 鎖定期間輸入「正確密碼」也擋，同樣 403 ACCOUNT_LOCKED
        r = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["error_code"] == "ACCOUNT_LOCKED"
        assert "分鐘後再試" in body["detail"]
    finally:
        await db_module._conn.execute(
            "DELETE FROM users WHERE id = %s::uuid", (user_id,))


# ────────────────────────────────────────────────────────────────────────────
# W3-3：註冊自填證照鏡射投影
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_w3_3_register_certifications_mirrored(monkeypatch):
    """註冊含證照 → technician_certification 落庫且對該批 id 呼叫 mirror_rows。"""
    from services import auth_service

    calls: list[tuple[str, list]] = []

    async def _recorder(table, ids):
        calls.append((table, list(ids)))

    monkeypatch.setattr(auth_service, "mirror_rows", _recorder)

    email = f"uat2-cert-{uuid.uuid4().hex[:8]}@example.com"
    res = await auth_service.register_technician({
        "email": email,
        "name": "UAT2證照技師",
        "phone": "0987654321",
        "password": "Sup3rSecret!",
        "certifications": [
            {"cert_name": "乙級門鎖裝修", "brand": "Yale"},
        ],
    })
    tech_id = res["data"]["id"]
    user_id = res["data"]["user_id"]
    try:
        cur = await db_module._conn.execute(
            "SELECT id FROM technician_certification WHERE technician_id = %s::uuid",
            (tech_id,))
        cert_rows = await cur.fetchall()
        assert len(cert_rows) == 1, "證照應落庫"
        cert_ids = {str(r[0]) for r in cert_rows}

        cert_calls = [c for c in calls if c[0] == "technician_certification"]
        assert cert_calls, "註冊後應對 technician_certification 呼叫 mirror_rows（W3-3）"
        assert set(map(str, cert_calls[0][1])) == cert_ids
    finally:
        for tbl, col in (
            ("technician_certification", "technician_id"),
            ("technician_upload_token", "technician_id"),
            ("technician_kyc", "technician_id"),
            ("technicians", "id"),
        ):
            await db_module._conn.execute(
                f"DELETE FROM {tbl} WHERE {col} = %s::uuid", (tech_id,))
        await db_module._conn.execute(
            "DELETE FROM users WHERE id = %s::uuid", (user_id,))


# ────────────────────────────────────────────────────────────────────────────
# W1-1：月結去重（co-sign 已建結算不重複）
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_w1_1_monthly_batch_skips_cosigned_reconciliation():
    """已有（任何）settlement 引用的對帳單，月結不再建第二筆。"""
    from services import monthly_settlement_service

    assert await db_module._ensure_conn()
    tech_uuid = str(uuid.uuid4())  # saas.reconciliation.technician_id 無 FK
    approved_at = datetime(2031, 1, 15, tzinfo=timezone.utc)

    # 對帳單 A：co-sign 已建結算（monthly_batch_id NULL）→ 不得重複
    recon_a = str(uuid.uuid4())
    # 對帳單 B：無結算 → 正控制組，月結應建立
    recon_b = str(uuid.uuid4())
    for rid, payout in ((recon_a, 3825.0), (recon_b, 1000.0)):
        await db_module._conn.execute(
            "INSERT INTO saas.reconciliation "
            "  (id, tenant_id, technician_id, total_orders, total_revenue, "
            "   platform_fee, technician_payout, status, approved_at) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, 1, %s, 0, %s, 'approved', %s)",
            (rid, TID, tech_uuid, payout, payout, approved_at),
        )
    await db_module._conn.execute(
        "INSERT INTO saas.settlement "
        "  (tenant_id, reconciliation_id, technician_id, amount, status, monthly_batch_id) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 3825.0, 'pending', NULL)",
        (TID, recon_a, tech_uuid),
    )
    try:
        batch = await monthly_settlement_service.generate_monthly_batch(
            tenant_id=TID, period_year=2031, period_month=1, triggered_by="test",
        )
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM saas.settlement WHERE reconciliation_id = %s::uuid",
            (recon_a,))
        assert (await cur.fetchone())[0] == 1, "co-sign 已建結算不得重複（金額翻倍風險）"

        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM saas.settlement WHERE reconciliation_id = %s::uuid "
            "AND monthly_batch_id IS NOT NULL",
            (recon_b,))
        assert (await cur.fetchone())[0] == 1, "無結算的對帳單月結應正常建立"
    finally:
        for rid in (recon_a, recon_b):
            await db_module._conn.execute(
                "DELETE FROM saas.settlement WHERE reconciliation_id = %s::uuid", (rid,))
            await db_module._conn.execute(
                "DELETE FROM saas.reconciliation WHERE id = %s::uuid", (rid,))
        await db_module._conn.execute(
            "DELETE FROM saas.monthly_settlement_batch "
            "WHERE tenant_id = %s::uuid AND period_year = 2031 AND period_month = 1",
            (TID,))


# ────────────────────────────────────────────────────────────────────────────
# W1-2：對帳駁回端點
# ────────────────────────────────────────────────────────────────────────────


async def _mk_public_reconciliation() -> tuple[str, str, str]:
    """public.reconciliations pending 一筆（含 technicians FK）。回 (recon_id, tech_id, user_id)。"""
    tech_id, user_id = await _mk_technician("active")
    recon_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO reconciliations "
        "  (id, technician_id, period_start, period_end, total_orders, "
        "   total_revenue, platform_fee, technician_payout, status) "
        "VALUES (%s::uuid, %s::uuid, NOW() - INTERVAL '30 days', NOW(), "
        "        2, 5000, 1000, 4000, 'pending')",
        (recon_id, tech_id),
    )
    return recon_id, tech_id, user_id


async def _rm_public_reconciliation(recon_id: str, tech_id: str, user_id: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM settlements WHERE reconciliation_id = %s::uuid", (recon_id,))
    await db_module._conn.execute(
        "DELETE FROM reconciliations WHERE id = %s::uuid", (recon_id,))
    await _rm_technician(tech_id, user_id)


def _idem(headers: dict) -> dict:
    """每請求帶唯一 Idempotency-Key（idempotency_guard 對 POST 強制）。"""
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


@pytest.mark.asyncio
async def test_w1_2_reject_reconciliation_flow(client, admin_headers):
    """pending 駁回 → rejected＋審計欄位；重複駁回 409；駁回後 approve 409。"""
    recon_id, tech_id, user_id = await _mk_public_reconciliation()
    try:
        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}:reject",
            json={"reason": "金額與工單不符，退回重對"},
            headers=_idem(admin_headers),
        )
        assert r.status_code == 200, r.text
        recon = r.json()["reconciliation"]
        assert recon["status"] == "rejected"
        assert recon["reject_reason"] == "金額與工單不符，退回重對"
        assert recon["rejected_by"] == ADMIN_USER_ID
        assert recon["rejected_at"]

        # 狀態衝突：已駁回再駁 → 409（語意同 approve）
        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}:reject",
            json={"reason": "再駁一次"},
            headers=_idem(admin_headers),
        )
        assert r.status_code == 409, r.text
        assert r.json()["error_code"] == "STATE_CONFLICT"

        # 已駁回不可 approve
        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}/approve",
            json={}, headers=_idem(admin_headers),
        )
        assert r.status_code == 409, r.text
    finally:
        await _rm_public_reconciliation(recon_id, tech_id, user_id)


@pytest.mark.asyncio
async def test_w1_2_reject_requires_reason(client, admin_headers):
    """reason 缺/過短 → 422（≥3 字必填，已釘契約）；缺 Idempotency-Key → 400。"""
    recon_id, tech_id, user_id = await _mk_public_reconciliation()
    try:
        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}:reject",
            json={"reason": "駁"},
            headers=_idem(admin_headers),
        )
        assert r.status_code == 422, r.text

        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}:reject",
            json={}, headers=_idem(admin_headers),
        )
        assert r.status_code == 422, r.text

        # 語意同 approve：缺 Idempotency-Key → 400
        r = await client.post(
            f"/api/v1/accounting/reconciliations/{recon_id}:reject",
            json={"reason": "金額不符退回"}, headers=admin_headers,
        )
        assert r.status_code == 400, r.text
        assert r.json()["error_code"] == "MISSING_IDEMPOTENCY_KEY"

        # 未被駁回（仍 pending）
        cur = await db_module._conn.execute(
            "SELECT status FROM reconciliations WHERE id = %s::uuid", (recon_id,))
        assert (await cur.fetchone())[0] == "pending"
    finally:
        await _rm_public_reconciliation(recon_id, tech_id, user_id)


# ────────────────────────────────────────────────────────────────────────────
# W1-3：未收帳款口徑（結構性驗證）
# ────────────────────────────────────────────────────────────────────────────


def test_w1_3_outstanding_includes_issued():
    """未收帳款＝draft+issued（尚未收到的錢），非只算 draft。"""
    import inspect

    from services import revenue_service
    assert revenue_service._OUTSTANDING_STATUSES == ("draft", "issued")
    src = inspect.getsource(revenue_service._query_kpis)
    assert "IN ('draft','issued')" in src
    assert "FILTER (WHERE i.status = 'draft')" not in src


# ────────────────────────────────────────────────────────────────────────────
# W5-2：通知即時推播（fail-soft）
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_w5_2_push_notification_publishes_to_ws(monkeypatch):
    """push_notification 落庫後 publish 到 /realtime/notifications/{user_id}。"""
    from realtime import ws_hub
    from services import notification_service

    published: list[tuple[str, dict]] = []

    async def _record(channel, message):
        published.append((channel, message))
        return 1

    monkeypatch.setattr(ws_hub.hub, "publish", _record)

    notif = await notification_service.push_notification(
        {"target_type": "user", "target_id": ADMIN_USER_ID,
         "type": "system", "title": "UAT2 推播測試", "body": "hello"},
        tenant_id=TID,
    )
    try:
        assert published, "落庫後應 publish 到 WS hub"
        channel, message = published[0]
        assert channel == f"/realtime/notifications/{ADMIN_USER_ID}"
        assert message["type"] == "notification"
        assert message["payload"]["id"] == notif["id"]
        assert message["payload"]["title"] == "UAT2 推播測試"
    finally:
        await db_module._conn.execute(
            "DELETE FROM notifications WHERE id = %s::uuid", (notif["id"],))


@pytest.mark.asyncio
async def test_w5_2_publish_failure_does_not_break_persist(monkeypatch):
    """publish 炸掉 → 通知仍落庫、呼叫端不噴錯（fail-soft）。"""
    from realtime import ws_hub
    from services import notification_service

    async def _boom(channel, message):
        raise RuntimeError("WS hub down")

    monkeypatch.setattr(ws_hub.hub, "publish", _boom)

    notif = await notification_service.push_notification(
        {"target_type": "user", "target_id": ADMIN_USER_ID,
         "type": "system", "title": "UAT2 fail-soft", "body": ""},
        tenant_id=TID,
    )
    try:
        cur = await db_module._conn.execute(
            "SELECT 1 FROM notifications WHERE id = %s::uuid", (notif["id"],))
        assert await cur.fetchone(), "publish 失敗不可影響落庫"
    finally:
        await db_module._conn.execute(
            "DELETE FROM notifications WHERE id = %s::uuid", (notif["id"],))


# ────────────────────────────────────────────────────────────────────────────
# W5-3：工單自動通知帶 related_entity
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_w5_3_auto_notify_carries_related_entity():
    """_auto_notify 帶 wo_id → 通知列 related_entity 依已釘契約。"""
    from services import work_order_service

    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await work_order_service._auto_notify(
        TID, ADMIN_USER_ID, "work_order_assigned", "UAT2 跳轉測試", "b",
        wo_id=wo_id,
    )
    cur = await db_module._conn.execute(
        "SELECT id, related_entity FROM notifications "
        "WHERE user_id = %s::uuid AND title = 'UAT2 跳轉測試' "
        "ORDER BY created_at DESC LIMIT 1",
        (ADMIN_USER_ID,))
    row = await cur.fetchone()
    try:
        assert row is not None, "通知應落庫"
        rel = row[1]
        assert rel == {
            "type": "work_order", "id": wo_id, "url": f"/work-orders/{wo_id}",
        }, "related_entity 須符合已釘契約"
    finally:
        if row:
            await db_module._conn.execute(
                "DELETE FROM notifications WHERE id = %s::uuid", (str(row[0]),))


# ────────────────────────────────────────────────────────────────────────────
# W5-8：SLA 告警 WS 白名單
# ────────────────────────────────────────────────────────────────────────────


def test_w5_8_sla_alert_roles_include_cs_and_dispatcher():
    """最終白名單：admin / operations_manager / dispatcher / customer_service。"""
    import main as main_module

    assert main_module._SLA_ALERT_ROLES == {
        "admin", "operations_manager", "dispatcher", "customer_service",
    }


# ────────────────────────────────────────────────────────────────────────────
# W2-4：consumer track 語意
# ────────────────────────────────────────────────────────────────────────────


def _mock_track_payload(subject_id: str = "wo-uuid-0001"):
    payload = MagicMock()
    payload.subject_id = subject_id
    payload.purpose = "work_order_status"
    return payload


@pytest.mark.asyncio
async def test_w2_4_last_update_at_never_future_scheduled(client):
    """未完工：last_update_at＝最新事件時間（非未來的 scheduled_at）；scheduled_at 獨立欄位。"""
    record = {
        "work_order_id": str(uuid.uuid4()),
        "raw_status": "assigned",
        "public_status": "assigned",
        "scheduled_at": "2099-01-01T09:00:00+00:00",  # 未來預約時間
        "completed_at": None,
        "technician_name": "陳大文",
        "technician_phone": "0912345678",
        "updated_at": "2026-07-18T10:00:00+00:00",
        "last_event_at": "2026-07-18T11:30:00+00:00",
    }
    with (
        patch("routers.consumer_v2.verify_token", return_value=_mock_track_payload()),
        patch("services.work_order_service.get_public_status",
              new_callable=AsyncMock, return_value=record),
    ):
        resp = await client.get(f"/consumer/work-orders/{'a' * 40}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["last_update_at"] == "2026-07-18T11:30:00+00:00", \
        "last_update_at 必須是真實更新時間，不可拿未來 scheduled_at 充數"
    assert body["scheduled_at"] == "2099-01-01T09:00:00+00:00"


@pytest.mark.asyncio
async def test_w2_4_completed_uses_completed_at(client):
    """已完工：last_update_at＝completed_at。"""
    record = {
        "work_order_id": str(uuid.uuid4()),
        "raw_status": "completed",
        "public_status": "completed",
        "scheduled_at": "2026-07-10T09:00:00+00:00",
        "completed_at": "2026-07-15T14:00:00+00:00",
        "technician_name": None,
        "technician_phone": None,
        "updated_at": "2026-07-15T14:00:01+00:00",
        "last_event_at": "2026-07-15T13:59:00+00:00",
    }
    with (
        patch("routers.consumer_v2.verify_token", return_value=_mock_track_payload()),
        patch("services.work_order_service.get_public_status",
              new_callable=AsyncMock, return_value=record),
    ):
        resp = await client.get(f"/consumer/work-orders/{'a' * 40}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["last_update_at"] == "2026-07-15T14:00:00+00:00"


# ────────────────────────────────────────────────────────────────────────────
# W5-4：進線案件關聯欄
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_w5_4_intake_case_links_roundtrip():
    """建案帶 conversation_id/problem_card_id → API 回應帶出；未填者為 None。"""
    from services import intake_case_service

    conv_id, pc_id = str(uuid.uuid4()), str(uuid.uuid4())
    result = await intake_case_service.create_case(
        tenant_id=TID,
        source_channel="line",
        summary="UAT2 關聯測試",
        conversation_id=conv_id,
        problem_card_id=pc_id,
    )
    case = result["data"]
    try:
        assert case["conversation_id"] == conv_id
        assert case["problem_card_id"] == pc_id
        assert case["work_order_id"] is None

        got = await intake_case_service.get_case(tenant_id=TID, case_id=case["id"])
        assert got["data"]["conversation_id"] == conv_id
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.intake_case WHERE id = %s::uuid", (case["id"],))


def test_w5_4_line_auto_case_backfills_conversation():
    """LINE 自動建案路徑回填 conversation_id（結構性驗證）。"""
    import inspect

    from services import problem_card_service
    src = inspect.getsource(problem_card_service._ensure_line_case)
    assert "conversation_id=conv_id" in src
    assert "problem_card_id=pc_id" in src
