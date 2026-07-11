"""CR-0117 師傅端首頁假資料接線測試（component，真 DB）。

覆蓋五條新接的資料管線：
  S1 報價 send/accept → work_orders.estimated_price 回寫（原死欄位）
  S2 dashboard recent_feedback 含「只給星不留言」評價（原 feedback IS NOT NULL 濾光）
  S3 rollup_technician_stats：work_orders 聚合回寫 technicians.rating/completed_orders
  S4 generate_statement 省略金額 → 依 CR-0106 佣金口徑自動計算；
     statement_generate_cron.run_once 對上月完工技師冪等補產 draft
  （S5 為前端判準修正，走 tsc + Playwright，不在本檔）

注意：本套件會建立/刪除測試資料 —— 請在隔離測試庫跑（POSTGRES_URI 指向 scratch DB），
不要對業主 UAT 中的 5433 主庫執行（見 memory reference_pytest_pollutes_uat_db）。
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

import core.db as db_module
from core.db import _ensure_conn
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


# ── 共用 seed helpers ───────────────────────────────────────────────


async def _seed_customer_chain() -> dict:
    """user→conversation→problem_card→work_order(created)。回 id dict。"""
    await _ensure_conn()  # ASGITransport 不跑 lifespan，_conn 為 lazy init
    ids = {
        "uid": str(uuid.uuid4()),
        "cid": str(uuid.uuid4()),
        "pcid": str(uuid.uuid4()),
        "woid": str(uuid.uuid4()),
    }
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')",
        (ids["uid"], DEFAULT_TENANT_ID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)",
        (ids["cid"], ids["uid"], f"sess-{ids['uid'][:8]}"),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status, brand, model, category) "
        "VALUES (%s::uuid, %s::uuid, 'confirmed', 'Yale', 'YDM-4109', '電池')",
        (ids["pcid"], ids["cid"]),
    )
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_name, customer_address, "
        "  brand, model, problem_type, service_category, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'created', '測試客戶', '台北市測試路1號', "
        "  'Yale', 'YDM-4109', '電池故障', 'repair', %s::uuid)",
        (ids["woid"], ids["pcid"], DEFAULT_TENANT_ID),
    )
    return ids


async def _seed_technician(level: str = "B") -> dict:
    """user(role=technician)+technicians 列。回 {tuid, tid}。"""
    await _ensure_conn()  # 同上：lazy init
    ids = {"tuid": str(uuid.uuid4()), "tid": str(uuid.uuid4())}
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, 'technician', TRUE)",
        (ids["tuid"], DEFAULT_TENANT_ID),
    )
    await db_module._conn.execute(
        "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status, level) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'CR0117測試技師', '0900117117', 'active', %s)",
        (ids["tid"], DEFAULT_TENANT_ID, ids["tuid"], level),
    )
    return ids


async def _cleanup(table_id_pairs: list[tuple[str, str, str]]) -> None:
    """依序 DELETE（呼叫端自排 FK 順序）。tuple = (table, id_col, id)。"""
    for table, col, val in table_id_pairs:
        await db_module._conn.execute(
            f"DELETE FROM {table} WHERE {col} = %s::uuid", (val,)
        )


async def _add_line_direct(
    quote_id: str, wo_id: str, *, name: str, price: float, qty: int,
    service_code: str | None = None,
) -> None:
    """直插 quote_line_items + 重算 quote.total_amount。

    不走 add_line()（其價格綁 CR-0034 catalog 的 service/material code，測試自訂
    價會被 catalog 覆蓋/擋下）；_recompute_total 為真實 service 函式，總額口徑一致。"""
    from services.quote_engine_service import _recompute_total

    await db_module._conn.execute(
        "INSERT INTO quote_line_items (quote_id, work_order_id, tenant_id, item_name, "
        "  category, customer_price, quantity, service_code) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'labor', %s, %s, %s)",
        (quote_id, wo_id, DEFAULT_TENANT_ID, name, price, qty, service_code),
    )
    await _recompute_total(quote_id)


# ── S1：報價 send/accept → estimated_price ──────────────────────────


@pytest.mark.asyncio
async def test_quote_accept_writes_estimated_price(client):
    from services import quote_engine_service as q

    ids = await _seed_customer_chain()
    quote = await q.create_quote(
        tenant_id=DEFAULT_TENANT_ID, work_order_id=ids["woid"], created_by=None,
    )
    qid = quote["id"]
    try:
        await _add_line_direct(qid, ids["woid"], name="更換電池模組", price=1200, qty=2)
        # 直接把狀態放到 sent（繞過 send 的 LINE 推播/凍結快照旁路），單測 accept 主路徑
        await db_module._conn.execute(
            "UPDATE quote SET state = 'sent' WHERE id = %s::uuid", (qid,)
        )
        await q.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="accept")

        cur = await db_module._conn.execute(
            "SELECT estimated_price FROM work_orders WHERE id = %s::uuid", (ids["woid"],)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is not None, "accept 後 estimated_price 應寫入"
        assert float(row[0]) == pytest.approx(2400.0)  # 1200 × 2
    finally:
        await _cleanup([
            ("quote_line_items", "quote_id", qid),
            # pricing_rule_snapshot 自 098 起 content-addressable+append-only(CR-0149),不清
            ("invoices", "work_order_id", ids["woid"]),
            ("quote", "id", qid),
            ("work_orders", "id", ids["woid"]),
            ("problem_cards", "id", ids["pcid"]),
            ("conversations", "id", ids["cid"]),
            ("users", "id", ids["uid"]),
        ])


@pytest.mark.asyncio
async def test_quote_send_writes_estimated_price(client):
    """send（送客戶、價格已凍結）當下就回寫 —— sla_monitor quote_expiring 依
    estimated_price 非空判定「已報價待確認」，accept 才寫會讓告警永不起算。"""
    from services import quote_engine_service as q

    ids = await _seed_customer_chain()
    quote = await q.create_quote(
        tenant_id=DEFAULT_TENANT_ID, work_order_id=ids["woid"], created_by=None,
    )
    qid = quote["id"]
    try:
        await _add_line_direct(qid, ids["woid"], name="開鎖服務", price=800, qty=1)
        try:
            await q.transition(tenant_id=DEFAULT_TENANT_ID, quote_id=qid, action="send")
        except Exception:
            # send 的下游旁路（view token / LINE outbox / 對話註記）在測試環境可能缺
            # 依賴 —— estimated_price 回寫在狀態轉換當下已完成，旁路失敗不影響本測試點。
            pass

        cur = await db_module._conn.execute(
            "SELECT estimated_price FROM work_orders WHERE id = %s::uuid", (ids["woid"],)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is not None, "send 後 estimated_price 應寫入"
        assert float(row[0]) == pytest.approx(800.0)
    finally:
        await _cleanup([
            ("quote_line_items", "quote_id", qid),
            # pricing_rule_snapshot 自 098 起 content-addressable+append-only(CR-0149),不清
            ("quote", "id", qid),
            ("work_orders", "id", ids["woid"]),
            ("problem_cards", "id", ids["pcid"]),
            ("conversations", "id", ids["cid"]),
            ("users", "id", ids["uid"]),
        ])


# ── S2：recent_feedback 含只給星的評價 ──────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_recent_feedback_includes_star_only(client):
    from services import technician_service

    tech = await _seed_technician()
    wo_id = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_name, tenant_id, technician_id, "
        "  rating, feedback, completed_at) "
        "VALUES (%s::uuid, 'confirmed', '星星客戶', %s::uuid, %s::uuid, 5, NULL, NOW())",
        (wo_id, DEFAULT_TENANT_ID, tech["tid"]),
    )
    try:
        summary = await technician_service.get_my_dashboard_summary(
            tenant_id=DEFAULT_TENANT_ID, user_id=tech["tuid"],
        )
        assert summary["avg_rating"] == pytest.approx(5.0)
        assert summary["rating_count"] == 1
        # 關鍵：feedback=NULL 的評分要出現在 recent_feedback（先前被 feedback IS NOT NULL 濾掉）
        assert len(summary["recent_feedback"]) == 1
        assert summary["recent_feedback"][0]["rating"] == 5
        assert summary["recent_feedback"][0]["feedback"] is None
    finally:
        await _cleanup([
            ("work_orders", "id", wo_id),
            ("technicians", "id", tech["tid"]),
            ("users", "id", tech["tuid"]),
        ])


# ── S3：rollup_technician_stats ─────────────────────────────────────


@pytest.mark.asyncio
async def test_rollup_technician_stats_writes_aggregates(client):
    from services import technician_service

    tech = await _seed_technician()
    wo1, wo2 = str(uuid.uuid4()), str(uuid.uuid4())
    # 一張完工有評分、一張完工無評分
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_name, tenant_id, technician_id, rating, completed_at) "
        "VALUES (%s::uuid, 'confirmed', '客A', %s::uuid, %s::uuid, 4, NOW())",
        (wo1, DEFAULT_TENANT_ID, tech["tid"]),
    )
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_name, tenant_id, technician_id, completed_at) "
        "VALUES (%s::uuid, 'completed', '客B', %s::uuid, %s::uuid, NOW())",
        (wo2, DEFAULT_TENANT_ID, tech["tid"]),
    )
    try:
        await technician_service.rollup_technician_stats(
            tenant_id=DEFAULT_TENANT_ID, technician_id=tech["tid"],
        )
        cur = await db_module._conn.execute(
            "SELECT rating, completed_orders FROM technicians WHERE id = %s::uuid",
            (tech["tid"],),
        )
        row = await cur.fetchone()
        assert float(row[0]) == pytest.approx(4.0)  # AVG(4)
        assert int(row[1]) == 2  # 兩張皆有 completed_at
    finally:
        await _cleanup([
            ("work_orders", "id", wo1),
            ("work_orders", "id", wo2),
            ("technicians", "id", tech["tid"]),
            ("users", "id", tech["tuid"]),
        ])


@pytest.mark.asyncio
async def test_rollup_safe_wrapper_tolerates_missing_wo(client):
    """_rollup_tech_stats_safe 對不存在的工單靜默返回（fail-soft 不 raise）。"""
    from services.work_order_service import _rollup_tech_stats_safe

    await _rollup_tech_stats_safe(DEFAULT_TENANT_ID, str(uuid.uuid4()))  # 不應 raise


# ── S4：月結自動計算 + cron ─────────────────────────────────────────


async def _seed_completed_wo_with_payout(
    tech_id: str, *, completed_at_sql: str, service_code: str,
) -> dict:
    """完工工單（completion_status=completed）+ 報價明細（帶 service_code）+ 對應費率。"""
    ids = {"woid": str(uuid.uuid4()), "qid": str(uuid.uuid4())}
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, status, customer_name, tenant_id, technician_id, "
        "  completion_status, completed_at) "
        f"VALUES (%s::uuid, 'completed', '月結客戶', %s::uuid, %s::uuid, 'completed', {completed_at_sql})",
        (ids["woid"], DEFAULT_TENANT_ID, tech_id),
    )
    await db_module._conn.execute(
        "INSERT INTO quote (id, work_order_id, state, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'accepted', %s::uuid)",
        (ids["qid"], ids["woid"], DEFAULT_TENANT_ID),
    )
    await db_module._conn.execute(
        "INSERT INTO quote_line_items (quote_id, work_order_id, tenant_id, item_name, "
        "  category, customer_price, quantity, service_code) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, '月結測試服務', 'labor', 1500, 2, %s)",
        (ids["qid"], ids["woid"], DEFAULT_TENANT_ID, service_code),
    )
    # 費率（level B → LV-B）：base_payout 700/次（rule_id NOT NULL 無 default → 自給）
    await db_module._conn.execute(
        "INSERT INTO technician_payout_rule (rule_id, service_code, service_name, level_id, base_payout) "
        "VALUES (%s, %s, '月結測試服務', 'LV-B', 700) "
        "ON CONFLICT DO NOTHING",
        (f"PR-{service_code}", service_code),
    )
    return ids


@pytest.mark.asyncio
async def test_generate_statement_auto_computes_gross(client):
    from services import technician_statement_service as svc

    tech = await _seed_technician(level="B")
    svc_code = f"T0117-{uuid.uuid4().hex[:6]}"
    seeded = await _seed_completed_wo_with_payout(
        tech["tid"],
        completed_at_sql="date_trunc('month', CURRENT_DATE) - INTERVAL '10 days'",  # 上個月
        service_code=svc_code,
    )
    today = date.today()
    py, pm = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    try:
        stmt = await svc.generate_statement(
            tenant_id=DEFAULT_TENANT_ID,
            technician_id=tech["tid"],
            period_year=py, period_month=pm,
            # gross/completed 皆省略 → 自動依佣金口徑計算
        )
        assert float(stmt["gross_amount"]) == pytest.approx(1400.0)  # 700 × qty2
        assert stmt["total_completed_orders"] == 1
        assert float(stmt["net_amount"]) == pytest.approx(1400.0)  # 扣項 0
        # 顯式帶值 = 人工覆寫（冪等：同期已存在 → 回 existing，不覆蓋）
        again = await svc.generate_statement(
            tenant_id=DEFAULT_TENANT_ID, technician_id=tech["tid"],
            period_year=py, period_month=pm, gross_amount=999.0,
        )
        assert again["id"] == stmt["id"]
        assert float(again["gross_amount"]) == pytest.approx(1400.0)
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.technician_statement WHERE technician_id = %s::uuid",
            (tech["tid"],),
        )
        await db_module._conn.execute(
            "DELETE FROM technician_payout_rule WHERE service_code = %s", (svc_code,)
        )
        await _cleanup([
            ("quote_line_items", "quote_id", seeded["qid"]),
            ("quote", "id", seeded["qid"]),
            ("work_orders", "id", seeded["woid"]),
            ("technicians", "id", tech["tid"]),
            ("users", "id", tech["tuid"]),
        ])


@pytest.mark.asyncio
async def test_statement_generate_cron_idempotent(client):
    from realtime.statement_generate_cron import worker

    tech = await _seed_technician(level="B")
    svc_code = f"T0117C-{uuid.uuid4().hex[:6]}"
    seeded = await _seed_completed_wo_with_payout(
        tech["tid"],
        completed_at_sql="date_trunc('month', CURRENT_DATE) - INTERVAL '10 days'",
        service_code=svc_code,
    )
    try:
        first = await worker.run_once()
        assert first.get("generated", 0) >= 1
        # 該技師該期 statement 已存在
        cur = await db_module._conn.execute(
            "SELECT status, gross_amount FROM saas.technician_statement "
            "WHERE technician_id = %s::uuid", (tech["tid"],),
        )
        row = await cur.fetchone()
        assert row is not None and row[0] == "draft"
        assert float(row[1]) == pytest.approx(1400.0)
        # 冪等：第二輪不重複產（NOT EXISTS 濾掉）
        second = await worker.run_once()
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM saas.technician_statement WHERE technician_id = %s::uuid",
            (tech["tid"],),
        )
        assert int((await cur.fetchone())[0]) == 1
        assert second.get("errors", 0) == 0
    finally:
        await db_module._conn.execute(
            "DELETE FROM saas.technician_statement WHERE technician_id = %s::uuid",
            (tech["tid"],),
        )
        await db_module._conn.execute(
            "DELETE FROM technician_payout_rule WHERE service_code = %s", (svc_code,)
        )
        await _cleanup([
            ("quote_line_items", "quote_id", seeded["qid"]),
            ("quote", "id", seeded["qid"]),
            ("work_orders", "id", seeded["woid"]),
            ("technicians", "id", tech["tid"]),
            ("users", "id", tech["tuid"]),
        ])


# ── S5：熔斷技師擋派工（review 後補的伺服器端 guard）─────────────────


@pytest.mark.asyncio
async def test_assign_blocks_circuit_breaker_open_tech(client):
    """online_state=circuit_breaker_open → 409 TECHNICIAN_CIRCUIT_BREAKER_OPEN；
    主管帶 override_reason 放行（沿用報價 gate 安全閥模式）。先前此錯誤碼後端從不
    raise、前端 409 處理為死碼。"""
    from core.errors import ApiError
    from services import work_order_service as wos

    ids = await _seed_customer_chain()
    tech = await _seed_technician()
    qid = str(uuid.uuid4())
    await db_module._conn.execute(
        "UPDATE technicians SET online_state = 'circuit_breaker_open' WHERE id = %s::uuid",
        (tech["tid"],),
    )
    # 報價 gate 前置：已同意報價（隔離出熔斷 gate 本身）
    await db_module._conn.execute(
        "INSERT INTO quote (id, work_order_id, state, tenant_id, total_amount) "
        "VALUES (%s::uuid, %s::uuid, 'accepted', %s::uuid, 500)",
        (qid, ids["woid"], DEFAULT_TENANT_ID),
    )
    try:
        with pytest.raises(ApiError) as e:
            await wos.assign_order(
                tenant_id=DEFAULT_TENANT_ID, wo_id=ids["woid"],
                technician_id=tech["tid"], reason_code="MANUAL",
                actor_role="dispatcher",
            )
        assert e.value.error_code == "TECHNICIAN_CIRCUIT_BREAKER_OPEN"
        assert e.value.status_code == 409
        # 主管 override → 放行
        result = await wos.assign_order(
            tenant_id=DEFAULT_TENANT_ID, wo_id=ids["woid"],
            technician_id=tech["tid"], reason_code="MANUAL",
            actor_role="admin", override_reason="急修：熔斷技師為區域唯一可到場人力",
        )
        assert result["status"] == "assigned"
    finally:
        await _cleanup([
            ("quote", "id", qid),
            # CR-0165 F9：assign_order 現會寫 dispatch_logs（FK 無 CASCADE）→ 先刪子列
            ("dispatch_logs", "work_order_id", ids["woid"]),
            ("work_orders", "id", ids["woid"]),
            ("problem_cards", "id", ids["pcid"]),
            ("conversations", "id", ids["cid"]),
            ("users", "id", ids["uid"]),
            ("technicians", "id", tech["tid"]),
            ("users", "id", tech["tuid"]),
        ])


def test_previous_month_and_bounds_pure():
    from realtime.statement_generate_cron import _month_bounds, _previous_month

    assert _previous_month(date(2026, 7, 6)) == (2026, 6)
    assert _previous_month(date(2026, 1, 15)) == (2025, 12)
    assert _month_bounds(2026, 6) == (date(2026, 6, 1), date(2026, 7, 1))
    assert _month_bounds(2025, 12) == (date(2025, 12, 1), date(2026, 1, 1))
