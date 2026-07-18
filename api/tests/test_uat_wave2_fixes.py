"""UAT 第二波修復（2026-07-18）。

- P2-5：tech surface 缺 GET /api/v1/technicians/me/commission-statements → 404。
  補端點（讀 R4 technician_commission_projection 月彙總；空資料回空 items 200）。
- P2-8：problem_cards.location 欄早已落庫（create 有收）但 get/list 不回傳；
  轉工單時卡上服務地址也不作 fallback。修 _PC_SELECT 接回 + convert fallback。
- P2-9：bind_quotes_to_work_order 把「所有版本」報價（含 rejected）品項都回填
  work_order_id → 工單詳情費用明細混入被拒品項、總計失真。修為只計已同意
  （accepted / 急件補審 retrospective_audit_only / 後台手動 quote_id NULL）品項。
- P3：KPI 漏斗各階段各自依 created_at 計數 → 工單數可＞對話數 → 前端轉換率
  300%。修為 conversation cohort 計數（遞減鏈，恆 ≤ 100%）。
- CORS：未捕捉例外的 500 由 ServerErrorMiddleware 產生（CORSMiddleware 外側）
  → 不帶 Access-Control-Allow-Origin。修為通用 Exception handler 補 header。

（P1-4 案件池排除已指派＋接單前隱私遮蔽的測試在 test_pool_claim_accept.py。）
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

import core.db as db_module
from services import kpi_service
from services import problem_card_service as pc_svc
from services import quote_service
from services import technician_commission_service as commission_svc
from services import work_order_service as wo_svc
from tests.conftest import DEFAULT_TENANT_ID, _make_token, seed_accepted_quote

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


# ── 共用 seed helpers ────────────────────────────────────────────────────────


async def _mk_user_conv(*, address: str | None = None) -> tuple[str, str]:
    """user → conversation。回 (user_id, conversation_id)。"""
    assert await db_module._ensure_conn()
    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, 'UAT二波測試客', '0912000111', %s, 'customer')",
        (uid, TID, address),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')",
        (cid, uid, f"sess-{cid[:12]}"),
    )
    return uid, cid


async def _cleanup_chain(uid: str, cid: str) -> None:
    """依 conversation 反查 pc/wo 全鏈清理。"""
    await db_module._conn.execute(
        "DELETE FROM quote_line_items WHERE quote_id IN "
        "(SELECT q.id FROM quote q JOIN problem_cards pc ON q.problem_card_id = pc.id "
        " WHERE pc.conversation_id = %s::uuid)",
        (cid,),
    )
    await db_module._conn.execute(
        "DELETE FROM quote WHERE problem_card_id IN "
        "(SELECT id FROM problem_cards WHERE conversation_id = %s::uuid)",
        (cid,),
    )
    sub = ("(SELECT wo.id FROM work_orders wo JOIN problem_cards pc "
           "ON wo.problem_card_id = pc.id WHERE pc.conversation_id = %s::uuid)")
    for tbl in ("work_order_events", "dispatch_logs", "invoices"):
        await db_module._conn.execute(
            f"DELETE FROM {tbl} WHERE work_order_id IN {sub}", (cid,)
        )
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id IN "
        "(SELECT id FROM problem_cards WHERE conversation_id = %s::uuid)",
        (cid,),
    )
    await db_module._conn.execute(
        "DELETE FROM problem_cards WHERE conversation_id = %s::uuid", (cid,)
    )
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


# ── P2-8：problem_cards.location 接回 + 轉工單地址 fallback ──────────────────


@pytest.mark.asyncio
async def test_pc_location_returned_and_used_as_convert_fallback():
    uid, cid = await _mk_user_conv(address=None)  # user profile 無地址
    location = "台北市大安區和平東路100號"
    try:
        card = await pc_svc.create_card(
            tenant_id=TID,
            conversation_id=cid,
            brand="Yale",
            model="YDM7220",
            symptom="門鎖沒電",
            urgency="medium",
            location=location,
        )
        # get/list 回傳 location（修前：落庫但 response 永遠沒有）
        assert card["location"] == location
        got = await pc_svc.get_card(tenant_id=TID, pc_id=card["id"])
        assert got["location"] == location

        # 轉工單：caller 未帶地址、user profile 無地址 → 帶卡上 location（修前 422）
        await db_module._conn.execute(
            "UPDATE problem_cards SET status='confirmed' WHERE id = %s::uuid",
            (card["id"],),
        )
        await seed_accepted_quote(card["id"], TID)
        wo, created = await wo_svc.create_from_problem_card(
            tenant_id=TID, pc_id=card["id"],
        )
        assert created is True
        assert wo["address"] == location
    finally:
        await _cleanup_chain(uid, cid)


# ── P2-9：費用明細只計已同意報價品項、總計不回 null ──────────────────────────


async def _mk_quote(pid: str, wid: str, state: str, version: int) -> str:
    row = await (await db_module._conn.execute(
        "INSERT INTO quote (problem_card_id, work_order_id, state, tenant_id, version) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s) RETURNING id",
        (pid, wid, state, TID, version),
    )).fetchone()
    return str(row[0])


async def _mk_line(wid: str, quote_id: str | None, name: str, price: float) -> None:
    await db_module._conn.execute(
        "INSERT INTO quote_line_items "
        "  (quote_id, work_order_id, tenant_id, item_name, category, "
        "   unit_price, quantity, customer_price, is_mock) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'labor', 0, 1, %s, TRUE)",
        (quote_id, wid, TID, name, price),
    )


@pytest.mark.asyncio
async def test_billing_items_exclude_rejected_quote_items():
    uid, cid = await _mk_user_conv(address="台北市信義區1號")
    pid, wid = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid, %s, %s::uuid, 'Yale', 'A90', 'confirmed')",
            (pid, TID, cid),
        )
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, "
            "customer_name, problem_type, tenant_id) "
            "VALUES (%s::uuid, %s::uuid, 'in_progress', '台北市信義區1號', '客', '維修', %s::uuid)",
            (wid, pid, TID),
        )
        q_accepted = await _mk_quote(pid, wid, "accepted", 1)
        q_rejected = await _mk_quote(pid, wid, "rejected", 2)
        await _mk_line(wid, q_accepted, "更換鎖芯", 2000)
        await _mk_line(wid, q_rejected, "被拒品項不應入帳", 9999)
        await _mk_line(wid, None, "後台手動拆項", 500)  # CR-0027 manual，維持入帳

        out = await quote_service.list_line_items(
            tenant_id=TID, work_order_id=wid, include_cost=False,
        )
        names = [i["item_name"] for i in out["items"]]
        assert "更換鎖芯" in names
        assert "後台手動拆項" in names
        assert "被拒品項不應入帳" not in names  # 修前：rejected 品項混入
        # 總計 = 只計可入帳品項，且不為 null（修前：customer_final_amount 未算過回 null）
        assert out["customer_final_amount"] == "2500.00"
    finally:
        await _cleanup_chain(uid, cid)


# ── P2-5：技師本人佣金對帳單端點 ─────────────────────────────────────────────


async def _seed_tech_user() -> tuple[str, str]:
    uid, tech_id = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, email, display_name, phone, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, '對帳單測試技師', '0912222333', 'technician', true)",
        (uid, TID, f"uat-comm-{uid[:8]}@example.com"),
    )
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status, online_state) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '對帳單測試技師', '0912222333', 'active', 'available')",
        (tech_id, TID, uid),
    )
    return uid, tech_id


async def _cleanup_tech_user(uid: str, tech_id: str, settlement_ids: list[str]) -> None:
    for sid in settlement_ids:
        await db_module._conn.execute(
            "DELETE FROM technician_commission_projection WHERE settlement_id = %s::uuid",
            (sid,),
        )
    await db_module._conn.execute("DELETE FROM technicians WHERE id = %s::uuid", (tech_id,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_my_commission_statements_empty_returns_200(client):
    """無佣金資料 → 200 空 items（修前：端點不存在 → 404）。"""
    assert await db_module._ensure_conn()
    from realtime import event_consumer
    await event_consumer.ensure_schema()  # 投影表 IF NOT EXISTS（單庫 fallback）
    uid, tech_id = await _seed_tech_user()
    try:
        token = _make_token(user_id=uid, role="technician")
        res = await client.get(
            "/api/v1/technicians/me/commission-statements",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TID},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["items"] == []
    finally:
        await _cleanup_tech_user(uid, tech_id, [])


@pytest.mark.asyncio
async def test_my_commission_statements_monthly_aggregation(client):
    assert await db_module._ensure_conn()
    from realtime import event_consumer
    await event_consumer.ensure_schema()
    uid, tech_id = await _seed_tech_user()
    sids = [str(uuid.uuid4()) for _ in range(3)]
    try:
        rows = [
            (sids[0], "1500.00", "2026-06-15T10:00:00+08:00"),
            (sids[1], "500.00", "2026-06-20T10:00:00+08:00"),
            (sids[2], "800.00", "2026-05-03T10:00:00+08:00"),
        ]
        for sid, amount, accrued in rows:
            await db_module._conn.execute(
                "INSERT INTO technician_commission_projection "
                "  (settlement_id, tenant_id, technician_id, amount, currency, accrued_at) "
                "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'TWD', %s::timestamptz)",
                (sid, TID, tech_id, amount, accrued),
            )
        token = _make_token(user_id=uid, role="technician")
        res = await client.get(
            "/api/v1/technicians/me/commission-statements",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TID},
        )
        assert res.status_code == 200, res.text
        items = res.json()["data"]["items"]
        assert [i["period"] for i in items] == ["2026-06", "2026-05"]  # 新在前
        assert items[0]["commission_amount"] == "2000.00"
        assert items[1]["commission_amount"] == "800.00"
        for i in items:  # 每項至少 period / gross / commission / status
            assert {"period", "gross_amount", "commission_amount", "status"} <= set(i)
        # admin 角色打技師 me 端點 → 403（role gate）
        admin_token = _make_token(user_id=str(uuid.uuid4()), role="admin")
        res403 = await client.get(
            "/api/v1/technicians/me/commission-statements",
            headers={"Authorization": f"Bearer {admin_token}", "X-Tenant-ID": TID},
        )
        assert res403.status_code == 403
    finally:
        await _cleanup_tech_user(uid, tech_id, sids)


@pytest.mark.asyncio
async def test_my_commission_statements_service_no_technician_row():
    """user 無 technicians 對應列 → 空 items（不 raise）。"""
    assert await db_module._ensure_conn()
    out = await commission_svc.list_my_commission_statements(
        tenant_id=TID, user_id=str(uuid.uuid4()),
    )
    assert out == {"items": []}


# ── P3：KPI 漏斗 cohort 化（轉換率恆 ≤ 100%）────────────────────────────────


@pytest.mark.asyncio
async def test_kpi_funnel_monotonic_and_cohort_scoped():
    assert await db_module._ensure_conn()

    async def _funnel() -> dict:
        return await kpi_service._funnel_counts(TID, "30 days", None, None)

    before = await _funnel()

    # 期間外對話（60 天前）+ 期間內建立的工單：舊算法會計入工單卻不計對話
    # → 工單數可超過對話數（300% 假轉換率根源）；cohort 化後兩者皆不計。
    uid, cid = await _mk_user_conv(address="台北市信義區1號")
    pid, wid = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "UPDATE conversations SET created_at = NOW() - INTERVAL '60 days' "
            "WHERE id = %s::uuid",
            (cid,),
        )
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
            "VALUES (%s::uuid, %s, %s::uuid, 'Yale', 'A90', 'confirmed')",
            (pid, TID, cid),
        )
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, customer_address, "
            "customer_name, problem_type, tenant_id) "
            "VALUES (%s::uuid, %s::uuid, 'completed', '台北市信義區1號', '客', '維修', %s::uuid)",
            (wid, pid, TID),
        )
        after_outside = await _funnel()
        assert after_outside == before  # 期間外 cohort 完全不影響漏斗

        # 期間內對話推進到完工 → 每一階段 +1，且鏈嚴格遞減（≤ 前一階段）
        uid2, cid2 = await _mk_user_conv(address="台北市信義區2號")
        pid2, wid2 = str(uuid.uuid4()), str(uuid.uuid4())
        try:
            await db_module._conn.execute(
                "INSERT INTO problem_cards (id, tenant_id, conversation_id, brand, model, status) "
                "VALUES (%s::uuid, %s, %s::uuid, 'Yale', 'A90', 'confirmed')",
                (pid2, TID, cid2),
            )
            await db_module._conn.execute(
                "INSERT INTO work_orders (id, problem_card_id, status, customer_address, "
                "customer_name, problem_type, tenant_id) "
                "VALUES (%s::uuid, %s::uuid, 'completed', '台北市信義區2號', '客', '維修', %s::uuid)",
                (wid2, pid2, TID),
            )
            after = await _funnel()
            for key in ("conversations", "problem_cards", "work_orders",
                        "dispatched", "completed"):
                assert after[key] == before[key] + 1
            # 遞減鏈 → 以首階段為分母的百分比恆 ≤ 100%
            assert (after["conversations"] >= after["problem_cards"]
                    >= after["work_orders"] >= after["dispatched"]
                    >= after["completed"])
        finally:
            await _cleanup_chain(uid2, cid2)
    finally:
        await _cleanup_chain(uid, cid)


# ── 500 回應帶 CORS headers（未捕捉例外路徑）────────────────────────────────


@pytest.mark.asyncio
async def test_unhandled_500_response_has_cors_headers(app):
    import main as main_module

    origins = list(getattr(main_module, "_cors_origins", []) or [])
    if not origins or origins == ["*"]:
        pytest.skip("CORS 白名單未配置具體 origin，無法驗證 echo")
    origin = origins[0]

    path = "/__uat_wave2_boom"
    if not any(getattr(r, "path", "") == path for r in app.router.routes):
        async def _boom():
            raise RuntimeError("uat-wave2-boom")

        app.add_api_route(path, _boom, methods=["GET"])

    # raise_app_exceptions=False → 取得 ServerErrorMiddleware 產生的 500 回應
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as c:
        res = await c.get(path, headers={"Origin": origin})

    assert res.status_code == 500
    body = res.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    # 修前：500 路徑在 CORSMiddleware 外側 → 無此 header，瀏覽器只報 CORS 錯
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("access-control-allow-credentials") == "true"

    # 非白名單 origin 不 echo（維持 CORS 拒絕語意）
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as c:
        res_evil = await c.get(path, headers={"Origin": "https://evil.example.com"})
    assert res_evil.status_code == 500
    assert "access-control-allow-origin" not in res_evil.headers
