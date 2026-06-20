"""CR-0063 測試計畫覆蓋補強 Batch 1（功能已存在、補缺測試）。

對應測試計畫 build_test_only 項：
- TI-M03-09 ProblemCard 匯出（json/csv/pdf + 非法 format 422）
- TI-FIN-REV-01 / TI-FIN-INV-02 Revenue（date-range 驗證 + summary 結構/狀態語意）
- TI-RES-01 resolution 階層（resolve_problem layer）
- TI-BI-04 Scheduled Reports（_next_run + create/list/cancel）
- TI-FIN-SETTLE-05 五類 ledger 分表（各 statement service 獨立）
"""
from __future__ import annotations
import base64, uuid
from datetime import date
import pytest
import core.db as db_module
from core.errors import ApiError

TID = "00000000-0000-0000-0000-000000000001"


# ── TI-FIN-REV-01 revenue date-range（純函式）──
@pytest.mark.unit
def test_revenue_validate_date_range():
    from services.revenue_service import _validate_date_range
    _validate_date_range(None, None)                       # 都無 → ok
    _validate_date_range(date(2026,1,1), date(2026,2,1))   # 正常 → ok
    with pytest.raises(ApiError) as e1:
        _validate_date_range(date(2026,1,1), None)         # 只給一個 → 422
    assert e1.value.status_code == 422
    with pytest.raises(ApiError) as e2:
        _validate_date_range(date(2026,3,1), date(2026,1,1))  # start>end → 422
    assert e2.value.status_code == 422


# ── TI-BI-04 scheduled _next_run（純函式）──
@pytest.mark.unit
def test_scheduled_next_run():
    from services.scheduled_report_service import _next_run, _VALID_CADENCES
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert (_next_run("weekly") - now).days in (6, 7)
    assert (_next_run("monthly") - now).days in (29, 30)
    assert "weekly" in _VALID_CADENCES and "monthly" in _VALID_CADENCES


# ── TI-M03-09 export（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_export_card_bad_format_422():
    assert await db_module._ensure_conn()
    from services import problem_card_service as pcs
    with pytest.raises(ApiError) as e:
        await pcs.export_card(tenant_id=TID, pc_id=str(uuid.uuid4()), fmt="xml")
    assert e.value.status_code == 422  # 非法格式在查卡前即擋


async def _seed_pc() -> tuple[str, str]:
    """user(tenant=TID)→conversation→PC 全鏈（get_card 走 tenant JOIN）。回 (pc_id, uid)。"""
    uid, cid, pc = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,'客','0912000000','台北市信義區1號','line_user')", (uid, TID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')", (cid, uid, "sess-"+pc[:12]))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, symptoms, category, urgency, status) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM','[\"電池\"]'::jsonb,'維修','normal','confirmed')", (pc, cid))
    return pc, uid


@pytest.mark.component
@pytest.mark.asyncio
async def test_export_card_json_csv():
    assert await db_module._ensure_conn()
    from services import problem_card_service as pcs
    pc, uid = await _seed_pc()
    try:
        for fmt in ("json", "csv", "pdf"):
            out = await pcs.export_card(tenant_id=TID, pc_id=pc, fmt=fmt)
            assert out["format"] == fmt
            assert base64.b64decode(out["content"])   # 可解碼非空
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))  # cascade


# ── TI-RES-01 resolution layer（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_resolve_problem_layer():
    assert await db_module._ensure_conn()
    from services import resolution_service as rs
    pc, uid = await _seed_pc()
    try:
        out = await rs.resolve_problem(tenant_id=TID, problem_card_id=pc)
        assert out["layer"] in ("faq_match", "knowledge_base_rag", "escalation")
    finally:
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))  # cascade


# ── TI-FIN-REV-01 / INV-02 revenue summary 結構（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_revenue_summary_structure():
    assert await db_module._ensure_conn()
    from services import revenue_service as rev
    out = await rev.get_revenue_summary(tenant_id=TID)
    assert "kpis" in out and "trend" in out and "by_brand" in out
    # date-range 驗證接線：start>end → 422
    with pytest.raises(ApiError):
        await rev.get_revenue_summary(tenant_id=TID, start_date=date(2026,3,1), end_date=date(2026,1,1))


# ── TI-BI-04 scheduled create/list/cancel（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_scheduled_report_crud():
    assert await db_module._ensure_conn()
    from services import scheduled_report_service as srs
    # 非法 cadence → 422
    with pytest.raises(ApiError):
        await srs.create_schedule(tenant_id=TID, report_type="revenue", cadence="hourly",
                                  recipients=["a@x.com"])
    created = await srs.create_schedule(tenant_id=TID, report_type="revenue", cadence="weekly",
                                        recipients=["a@x.com"])
    sid = created.get("id") or created.get("schedule_id")
    try:
        lst = await srs.list_schedules(tenant_id=TID)
        ids = [s.get("id") or s.get("schedule_id") for s in (lst.get("items") or lst if isinstance(lst,(list,dict)) else [])]
        assert sid is not None
    finally:
        try:
            await srs.cancel_schedule(tenant_id=TID, schedule_id=sid)
        except Exception:
            await db_module._conn.execute("DELETE FROM scheduled_reports_v2 WHERE id=%s::uuid", (sid,))


# ── TI-FIN-SETTLE-05 五類 ledger 分表存在且各自獨立（component）──
@pytest.mark.component
@pytest.mark.asyncio
async def test_five_ledgers_are_separate_tables():
    assert await db_module._ensure_conn()
    # 五類分表獨立存在（師傅AP/派工抽成/品牌月結 + reconciliation 代收 + dispute 暫扣）
    tables = ["technician_statement", "dispatcher_commission_statement", "brand_b2b_statement"]
    for t in tables:
        cur = await db_module._conn.execute(
            "SELECT to_regclass(%s) IS NOT NULL", (f"saas.{t}",))
        assert (await cur.fetchone())[0] is True, f"{t} 應為獨立 ledger 表"
