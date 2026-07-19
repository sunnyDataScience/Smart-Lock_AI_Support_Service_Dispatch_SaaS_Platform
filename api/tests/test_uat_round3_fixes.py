"""UAT 第三輪修復回歸測試（docs/uat/uat-round3-report-20260719.md，api 分區）。

覆蓋：
  R3-3  對話訊息 metadata 原樣帶出（契約 1：至少 sender_role 可達）
  R3-6  Idempotency reserve-first（契約 3：併發同 key 恰一張工單＋另一發 409/回放；
        順序重放不變）＋ work_orders partial UNIQUE 兜底（migration 110）
  R3-7  工單列表 status 多值篩選（契約 2：可重複 query param 取聯集，單值向後相容）
  R3-9  KPI 匯出 format=pdf 產真 PDF（reportlab，同 legacy /reports/export 機制）
  R3-x  KPI avg_handle_minutes 算式修正（完工自動補 started_at==completed_at 灌 0）
  R3-x  補件 token 403（契約 4：UPLOAD_TOKEN_INVALID＋繁中訊息，不區分無效/過期）
  R3-x  inventory last_restock_at（契約 5：最近一筆 purchase 交易時間，ISO|null）
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID, seed_accepted_quote

import core.db as db_module

pytestmark = pytest.mark.component

TID = DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_confirmed_pc(display_name: str = "R3 測試客") -> tuple[str, str]:
    """user（台北地址→TP 公單）→ conv → confirmed PC。回 (pc_id, uid)。"""
    await db_module._ensure_conn()
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid,%s::uuid,%s,'0912000333','台北市中山區88號','line_user')",
        (uid, TID, display_name),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'active')",
        (cid, uid, "sess-" + pid[:12]),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status, intent) "
        "VALUES (%s::uuid,%s::uuid,'Yale','YDM7116','維修','normal','confirmed','repair')",
        (pid, cid),
    )
    return pid, uid


async def _cleanup_pc_user(uid: str, pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM invoices WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)",
        (pid,),
    )
    await db_module._conn.execute(
        "DELETE FROM work_order_events WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id=%s::uuid)",
        (pid,),
    )
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id=%s::uuid", (pid,)
    )
    await db_module._conn.execute(
        "DELETE FROM quote WHERE problem_card_id=%s::uuid", (pid,)
    )
    await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))


async def _cleanup_idem_key(key: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM idempotency_keys WHERE key=%s", (key,)
    )


# ---------------------------------------------------------------------------
# R3-3：對話訊息 metadata 原樣帶出（契約 1）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_3_message_metadata_passthrough(client, admin_headers):
    """接管人工訊息（metadata.sender_role=agent_human）經 v2 API 回傳仍帶 metadata。"""
    await db_module._ensure_conn()
    uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    idem_key = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, role) "
        "VALUES (%s::uuid,%s::uuid,'metadata 測試客','line_user')",
        (uid, TID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid,%s::uuid,%s,'escalated')",
        (cid, uid, "sess-meta-" + cid[:8]),
    )
    try:
        # 客服接管發訊 → 201 response 本體即應帶 metadata
        res = await client.post(
            f"/tenants/{TID}/conversations/{cid}/messages",
            headers={**admin_headers, "Idempotency-Key": idem_key},
            json={"content": "師傅五分鐘後到，請稍候"},
        )
        assert res.status_code == 201, res.text
        sent = res.json()
        assert sent.get("metadata"), "sendChatMessageV2 回應應帶 metadata"
        assert sent["metadata"]["sender_role"] == "agent_human"

        # 訊息列表也要帶（W5-1 端到端斷點就在這裡）
        res2 = await client.get(
            f"/tenants/{TID}/conversations/{cid}/messages",
            headers=admin_headers,
        )
        assert res2.status_code == 200, res2.text
        items = res2.json()["items"]
        target = next((m for m in items if m["id"] == sent["id"]), None)
        assert target is not None, "剛送出的訊息應出現在列表"
        assert target.get("metadata"), "列表項應帶 metadata（不可被序列化器剝掉）"
        assert target["metadata"]["sender_role"] == "agent_human"
    finally:
        await db_module._conn.execute(
            "DELETE FROM messages WHERE conversation_id=%s::uuid", (cid,)
        )
        await db_module._conn.execute(
            "DELETE FROM conversations WHERE id=%s::uuid", (cid,)
        )
        await db_module._conn.execute("DELETE FROM users WHERE id=%s::uuid", (uid,))
        await _cleanup_idem_key(idem_key)


# ---------------------------------------------------------------------------
# R3-6：Idempotency reserve-first（契約 3）＋ partial UNIQUE 兜底
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_6_concurrent_same_key_exactly_one_work_order(client, admin_headers):
    """併發 2 發同 key convert → 恰一張工單；另一發 409 IDEMPOTENCY_IN_PROGRESS 或回放。"""
    pid, uid = await _seed_confirmed_pc("併發冪等測試客")
    idem_key = str(uuid.uuid4())
    try:
        await seed_accepted_quote(pid, TID)
        headers = {**admin_headers, "Idempotency-Key": idem_key}
        body = {"problem_card_id": pid}

        r1, r2 = await asyncio.gather(
            client.post(f"/tenants/{TID}/work-orders", headers=headers, json=body),
            client.post(f"/tenants/{TID}/work-orders", headers=headers, json=body),
        )
        statuses = sorted([r1.status_code, r2.status_code])
        # 恰一發真正執行（201）；另一發 409（in_progress）或回放（201 same body）
        assert 201 in statuses, f"至少一發應 201：{statuses} / {r1.text} / {r2.text}"
        loser = r1 if r2.status_code == 201 else r2
        if loser.status_code == 409:
            assert loser.json()["error_code"] == "IDEMPOTENCY_IN_PROGRESS", loser.text
        else:
            assert loser.status_code == 201, f"回放應同 201：{loser.text}"

        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE problem_card_id=%s::uuid", (pid,)
        )
        assert (await cur.fetchone())[0] == 1, "同一張卡絕不可出現兩張工單"
    finally:
        await _cleanup_pc_user(uid, pid)
        await _cleanup_idem_key(idem_key)


@pytest.mark.asyncio
async def test_r3_6_sequential_replay_unchanged(client, admin_headers):
    """順序重放不變：同 key 重送回放同單；換 key 走 get-or-create 回 200 既有單。"""
    pid, uid = await _seed_confirmed_pc("順序冪等測試客")
    idem_key = str(uuid.uuid4())
    idem_key2 = str(uuid.uuid4())
    try:
        await seed_accepted_quote(pid, TID)
        headers = {**admin_headers, "Idempotency-Key": idem_key}
        body = {"problem_card_id": pid}

        r1 = await client.post(f"/tenants/{TID}/work-orders", headers=headers, json=body)
        assert r1.status_code == 201, r1.text
        wo_id = r1.json()["data"]["id"]

        # 同 key 重送 → 回放已存回應（同單、同 status）
        r2 = await client.post(f"/tenants/{TID}/work-orders", headers=headers, json=body)
        assert r2.status_code == 201, r2.text
        assert r2.json()["data"]["id"] == wo_id, "回放應回同一張工單"

        # 換 key（新請求）→ 服務層 get-or-create 回既有單（不建第二張；
        # HTTP status 沿用端點既有行為，回放語意以同單 id＋單數不變為準）
        r3 = await client.post(
            f"/tenants/{TID}/work-orders",
            headers={**admin_headers, "Idempotency-Key": idem_key2},
            json=body,
        )
        assert r3.status_code in (200, 201), r3.text
        assert r3.json()["data"]["id"] == wo_id

        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE problem_card_id=%s::uuid", (pid,)
        )
        assert (await cur.fetchone())[0] == 1
    finally:
        await _cleanup_pc_user(uid, pid)
        await _cleanup_idem_key(idem_key)
        await _cleanup_idem_key(idem_key2)


@pytest.mark.asyncio
async def test_r3_6_partial_unique_blocks_second_original_allows_reopen_child():
    """migration 110：partial UNIQUE 擋第二張「原始單」，但放行 reopen 子單。"""
    from psycopg import errors as pg_errors

    pid, uid = await _seed_confirmed_pc("UNIQUE 兜底測試客")
    try:
        await db_module._ensure_conn()
        wo1 = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, status, tenant_id) "
            "VALUES (%s::uuid,%s::uuid,'created',%s::uuid)",
            (wo1, pid, TID),
        )
        # 第二張原始單（parent/rework 皆 NULL）→ 必須被 UNIQUE 擋下
        with pytest.raises(pg_errors.UniqueViolation):
            await db_module._conn.execute(
                "INSERT INTO work_orders (id, problem_card_id, status, tenant_id) "
                "VALUES (%s::uuid,%s::uuid,'created',%s::uuid)",
                (str(uuid.uuid4()), pid, TID),
            )
        # reopen 子單（parent_work_order_id 指回原單）→ 合法，不可被擋
        wo_child = str(uuid.uuid4())
        await db_module._conn.execute(
            "INSERT INTO work_orders (id, problem_card_id, parent_work_order_id, status, tenant_id) "
            "VALUES (%s::uuid,%s::uuid,%s::uuid,'created',%s::uuid)",
            (wo_child, pid, wo1, TID),
        )
        cur = await db_module._conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE problem_card_id=%s::uuid", (pid,)
        )
        assert (await cur.fetchone())[0] == 2, "原始單 1＋reopen 子單 1"
    finally:
        await _cleanup_pc_user(uid, pid)


# ---------------------------------------------------------------------------
# R3-7：status 多值篩選（契約 2）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_7_status_multi_value_filter_service():
    """service 層：status list 取聯集；單值字串向後相容。"""
    from services import work_order_service as svc

    await db_module._ensure_conn()
    tid = str(uuid.uuid4())  # 隔離租戶，避免 scratch 既有工單干擾
    wo_ids = {}
    try:
        for st in ("assigned", "confirmed", "created"):
            wid = str(uuid.uuid4())
            wo_ids[st] = wid
            await db_module._conn.execute(
                "INSERT INTO work_orders (id, status, tenant_id, customer_name) "
                "VALUES (%s::uuid,%s,%s::uuid,'多值篩選測試')",
                (wid, st, tid),
            )

        page = await svc.list_orders(
            tenant_id=tid, cursor=None, limit=50, status=["assigned", "confirmed"]
        )
        got = {w["id"] for w in page["items"]}
        assert got == {wo_ids["assigned"], wo_ids["confirmed"]}, "多值應回兩狀態聯集"

        page_single = await svc.list_orders(
            tenant_id=tid, cursor=None, limit=50, status="assigned"
        )
        assert {w["id"] for w in page_single["items"]} == {wo_ids["assigned"]}, (
            "單值字串向後相容"
        )
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE tenant_id=%s::uuid", (tid,)
        )


@pytest.mark.asyncio
async def test_r3_7_status_multi_value_filter_http(client, admin_headers):
    """HTTP 層：status 可重複帶（FastAPI Query list）→ 200，回傳限於指定狀態。"""
    res = await client.get(
        f"/tenants/{TID}/work-orders?status=assigned&status=confirmed",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    # DB status assigned/confirmed → API 值 assigned/closed（_DB_STATUS_TO_API）
    assert all(w["status"] in {"assigned", "closed"} for w in items), (
        f"多值篩選回傳不可混入其他狀態：{[w['status'] for w in items]}"
    )


# ---------------------------------------------------------------------------
# R3-x：KPI avg_handle_minutes 算式修正
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_kpi_avg_handle_minutes_not_zero():
    """報告場景重現：兩筆完工 62/4 分（started_at 被完工自動補成==completed_at）
    → 平均應 ~33 分，不可為 0。"""
    from services import kpi_service

    await db_module._ensure_conn()
    tid = str(uuid.uuid4())  # 隔離租戶
    pc1, pc2 = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        for pc in (pc1, pc2):
            await db_module._conn.execute(
                "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
                "VALUES (%s::uuid,%s::uuid,'Yale','KPI-TEST','converted')",
                (pc, tid),
            )
        # 完工單：created_at 62/4 分鐘前；started_at==completed_at==NOW()
        # （complete_order 的 COALESCE(started_at, NOW()) 自動補行為）
        for pc, minutes in ((pc1, 62), (pc2, 4)):
            await db_module._conn.execute(
                "INSERT INTO work_orders "
                "  (id, problem_card_id, status, tenant_id, "
                "   created_at, started_at, completed_at) "
                "VALUES (%s::uuid,%s::uuid,'completed',%s::uuid, "
                "        NOW() - (%s * INTERVAL '1 minute'), NOW(), NOW())",
                (str(uuid.uuid4()), pc, tid, minutes),
            )

        report = await kpi_service.get_kpi_report(tenant_id=tid, period="7d")
        eff = report["technician_efficiency"]
        assert eff["completed_count"] == 2
        assert eff["avg_handle_minutes"] is not None
        assert 32.0 <= eff["avg_handle_minutes"] <= 34.0, (
            f"兩筆 62/4 分應平均 ~33，實得 {eff['avg_handle_minutes']}"
        )
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE tenant_id=%s::uuid", (tid,)
        )
        await db_module._conn.execute(
            "DELETE FROM problem_cards WHERE tenant_id=%s::uuid", (tid,)
        )


@pytest.mark.asyncio
async def test_r3_kpi_avg_uses_real_started_at_when_present():
    """有真到場紀錄（started_at 早於 completed_at）仍以 started_at 起算。"""
    from services import kpi_service

    await db_module._ensure_conn()
    tid = str(uuid.uuid4())
    pc = str(uuid.uuid4())
    try:
        await db_module._conn.execute(
            "INSERT INTO problem_cards (id, tenant_id, brand, model, status) "
            "VALUES (%s::uuid,%s::uuid,'Yale','KPI-TEST2','converted')",
            (pc, tid),
        )
        # created 120 分鐘前、到場 30 分鐘前、完工 NOW → 處理時長 30 分（非 120）
        await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (id, problem_card_id, status, tenant_id, created_at, started_at, completed_at) "
            "VALUES (%s::uuid,%s::uuid,'completed',%s::uuid, "
            "        NOW() - INTERVAL '120 minutes', NOW() - INTERVAL '30 minutes', NOW())",
            (str(uuid.uuid4()), pc, tid),
        )
        report = await kpi_service.get_kpi_report(tenant_id=tid, period="7d")
        avg = report["technician_efficiency"]["avg_handle_minutes"]
        assert avg is not None and 29.0 <= avg <= 31.0, f"應以真到場時間起算 ~30，實得 {avg}"
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE tenant_id=%s::uuid", (tid,)
        )
        await db_module._conn.execute(
            "DELETE FROM problem_cards WHERE tenant_id=%s::uuid", (tid,)
        )


# ---------------------------------------------------------------------------
# R3-9：KPI 匯出 format=pdf 產真 PDF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_9_export_v2_pdf_is_real_pdf(client, admin_headers):
    """v2 export format=pdf → application/pdf 且內容為 %PDF magic（非 CSV 掛羊頭）。"""
    res = await client.get(
        f"/tenants/{TID}/reports/export?report_type=kpi&format=pdf&period=30d",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content[:5] == b"%PDF-", "回傳內容必須是真 PDF（%PDF magic）"
    assert ".pdf" in res.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_r3_9_export_v2_csv_unchanged_and_bad_format_422(client, admin_headers):
    """format 缺省仍走 CSV（向後相容）；非法 format → 422。"""
    res = await client.get(
        f"/tenants/{TID}/reports/export?report_type=kpi&period=30d",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")

    res_bad = await client.get(
        f"/tenants/{TID}/reports/export?report_type=kpi&format=xlsx&period=30d",
        headers=admin_headers,
    )
    assert res_bad.status_code == 422, res_bad.text


# ---------------------------------------------------------------------------
# R3-x：補件 token 403（契約 4）
# ---------------------------------------------------------------------------

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_r3_upload_token_invalid_403_with_code(client):
    """token 解析失敗（不存在/格式亂掉）→ 403 UPLOAD_TOKEN_INVALID＋契約繁中訊息。"""
    for bogus in ("bad", "x" * 43):  # 過短格式亂 token / 合法長度但不存在
        res = await client.post(
            "/api/v1/technicians/registration-documents",
            data={"token": bogus, "doc_type": "id_front"},
            files={"file": ("id.png", _PNG_BYTES, "image/png")},
        )
        assert res.status_code == 403, f"token={bogus!r}: {res.status_code} {res.text}"
        body = res.json()
        assert body["error_code"] == "UPLOAD_TOKEN_INVALID", body
        assert "連結已失效" in body["message"], body
        assert "重新產生補件連結" in body["message"], body


# ---------------------------------------------------------------------------
# R3-x：inventory last_restock_at（契約 5）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_inventory_last_restock_at():
    """新品項 last_restock_at=null；restock（purchase 交易）後帶最近補貨時間。"""
    from services import inventory_v2_service as inv

    await db_module._ensure_conn()
    part_no = f"R3-TEST-{uuid.uuid4().hex[:8]}"
    item_id = None
    try:
        item = await inv.create_inventory_item_v2(
            tenant_id=TID, part_number=part_no, name="R3 最後補貨測試件",
            quantity_on_hand=1, reorder_point=0,
        )
        item_id = item["id"]
        assert item["last_restock_at"] is None, "尚未補貨過應為 null"

        result = await inv.restock_inventory_v2(
            tenant_id=TID, item_id=item_id, quantity=5, notes="R3 回歸測試補貨"
        )
        assert result["item"]["last_restock_at"] is not None, (
            "補貨（purchase）後應帶最近補貨時間"
        )

        # 列表項也要帶（前端渲染來源）
        page = await inv.list_inventory_items_v2(
            tenant_id=TID, cursor=None, limit=50, keyword=part_no
        )
        assert page["items"], "剛建的品項應可搜到"
        assert page["items"][0]["last_restock_at"] is not None
    finally:
        if item_id:
            await db_module._conn.execute(
                "DELETE FROM saas.inventory_transaction WHERE item_id=%s::uuid",
                (item_id,),
            )
            await db_module._conn.execute(
                "DELETE FROM saas.inventory_item WHERE id=%s::uuid", (item_id,)
            )
