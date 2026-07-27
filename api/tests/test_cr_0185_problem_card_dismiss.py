"""CR-0185：問題卡 `dismissed` 作廢終態。

LINE agent 轉真人會自動建草擬卡，誤判就產生垃圾卡，而此前**沒有乾淨的關閉途徑**：
標「已解決」會污染解決率**且會被 refinery 汲取成知識**（intake.py 只吃
status='resolved' AND knowledge_ready=TRUE），留 draft 則永遠佔住待確認佇列。

本檔守的是四類「漏改就讓修復自我廢除」的陷阱（皆為 0727 調查揪出）：
  1. `_DB_STATUS_TO_API` 沒加對映 → `_coerce_status` fallback 回 'draft'
     → 作廢卡在全站顯示成「待確認」，直接回到待確認佇列
  2. 三處 active 判定（＋partial unique index）沒排除 dismissed
     → 作廢卡永遠佔住該對話的唯一 active 名額，同對話再也開不了新卡
  3. 統計查詢沒排除 → 誤建卡壓低 PC→WO 轉換率、污染「熱門議題／熱門品牌」
  4. 沒把 conversation 交還 AI → 該 LINE 客人的 AI 永久靜音
     （0727 查到的 `14ef5e2f` 正是此成因）
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from services import problem_card_service as pcs

_MARK = "cr0185-dismiss-test"
_TENANT = "00000000-0000-0000-0000-000000000001"


# ── 純函式層（無 DB）────────────────────────────────────────────────────
def test_status_mapping_has_dismissed_and_is_not_resolved():
    """陷阱 1：對映缺漏會 fallback 回 draft；映射到 resolved 則會被 refinery 汲取。"""
    assert pcs._DB_STATUS_TO_API.get("dismissed") == "dismissed", (
        "缺 dismissed 對映 → _coerce_status fallback 回 'draft'，作廢卡回到待確認佇列"
    )
    assert pcs._coerce_status("dismissed") == "dismissed"
    assert pcs._DB_STATUS_TO_API["dismissed"] != "resolved", (
        "dismissed 不得映射為 resolved —— refinery 只吃 resolved，會把垃圾卡汲取成知識"
    )


def test_dismiss_transition_excludes_resolved():
    """已結案卡可能已被汲取成知識，不得回頭作廢。"""
    assert pcs._DISMISS_FROM == {"incomplete", "confirmed"}
    assert "resolved" not in pcs._DISMISS_FROM


def test_active_card_predicates_exclude_dismissed():
    """陷阱 2：三處 active 判定都必須排除 dismissed（含建卡查重／24h 冪等／併卡）。"""
    import inspect

    src = inspect.getsource(pcs)
    good = src.count("NOT IN ('resolved', 'escalated', 'dismissed')")
    stale = src.count("NOT IN ('resolved', 'escalated')")
    assert good == 3, f"應有 3 處已排除 dismissed 的 active 判定，實得 {good}"
    assert stale == 0, "仍有未排除 dismissed 的 active 判定 → 作廢卡會佔住對話唯一名額"


def test_stats_queries_exclude_dismissed():
    """陷阱 3：漏斗與熱門統計必須排除作廢卡。"""
    import inspect

    from services import dashboard_service, kpi_service

    kpi_src = inspect.getsource(kpi_service)
    assert "pc.status <> 'dismissed'" in kpi_src, (
        "kpi 漏斗第二階段未排除 dismissed → 誤建卡留在 PC→WO 轉換率分母"
    )
    dash_src = inspect.getsource(dashboard_service)
    assert dash_src.count("pc.status <> 'dismissed'") >= 2, (
        "hot_topics / top_brands 未排除 dismissed → 誤建卡的 category/brand 進熱門榜"
    )


# ── DB 行為層 ───────────────────────────────────────────────────────────
@pytest.fixture
async def _escalated_conv_with_card():
    """建一組「對話已 escalated + 一張 incomplete 草擬卡」，模擬誤判建卡現場。"""
    from core.db import _ensure_conn

    await _ensure_conn()
    user_id, conv_id, pc_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

    await db_module._conn.execute(
        "INSERT INTO users(id, tenant_id, display_name, role, is_active) "
        "VALUES (%s::uuid, %s::uuid, %s, 'line_user', TRUE)",
        (user_id, _TENANT, _MARK),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations(id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'escalated')",
        (conv_id, user_id, f"{_MARK}:{conv_id[:8]}"),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards(id, tenant_id, conversation_id, status, symptoms, source) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'incomplete', %s::jsonb, 'ai_line')",
        (pc_id, _TENANT, conv_id, '["' + _MARK + '"]'),
    )

    yield {"conv_id": conv_id, "pc_id": pc_id, "user_id": user_id}

    await db_module._conn.execute(
        "DELETE FROM problem_cards WHERE conversation_id = %s::uuid", (conv_id,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (conv_id,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest.mark.asyncio
async def test_dismiss_sets_terminal_state_and_records_trail(_escalated_conv_with_card):
    ctx = _escalated_conv_with_card
    card = await pcs.dismiss_card(
        tenant_id=_TENANT, pc_id=ctx["pc_id"], reason="AI 誤建：品牌型號皆空")

    assert card["status"] == "dismissed", "回傳狀態應為 dismissed（非 fallback 的 draft）"

    cur = await db_module._conn.execute(
        "SELECT status, dismissed_at, dismiss_reason, resolution_layer, knowledge_ready "
        "FROM problem_cards WHERE id = %s::uuid", (ctx["pc_id"],))
    status, dismissed_at, reason, layer, knowledge_ready = await cur.fetchone()
    assert status == "dismissed"
    assert dismissed_at is not None, "作廢軌跡欄 dismissed_at 未寫入"
    assert reason == "AI 誤建：品牌型號皆空"
    assert layer is None, "作廢不得寫 resolution_layer（作廢不是一種『解決』）"
    assert not knowledge_ready, "作廢不得觸發 Gate② → 避免變成知識來源"


@pytest.mark.asyncio
async def test_dismiss_returns_conversation_to_ai(_escalated_conv_with_card):
    """陷阱 4：不交還就讓該客人的 AI 永久靜音（0727 的 14ef5e2f 成因）。"""
    ctx = _escalated_conv_with_card
    await pcs.dismiss_card(tenant_id=_TENANT, pc_id=ctx["pc_id"], reason="重複進線")

    cur = await db_module._conn.execute(
        "SELECT status FROM conversations WHERE id = %s::uuid", (ctx["conv_id"],))
    (conv_status,) = await cur.fetchone()
    assert conv_status == "active", (
        f"對話未交還 AI（仍為 {conv_status}）→ 該 LINE 客人只會收到「已由真人專員接手」罐頭"
    )


@pytest.mark.asyncio
async def test_dismissed_card_frees_the_conversation_for_new_card(_escalated_conv_with_card):
    """陷阱 2 的 DB 端驗證：作廢後同一對話必須能再開新卡（partial unique index）。"""
    ctx = _escalated_conv_with_card
    await pcs.dismiss_card(tenant_id=_TENANT, pc_id=ctx["pc_id"], reason="誤建")

    new_pc = str(uuid.uuid4())
    # 若 index predicate 未排除 dismissed，這行會撞唯一約束
    await db_module._conn.execute(
        "INSERT INTO problem_cards(id, tenant_id, conversation_id, status, symptoms, source) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'incomplete', %s::jsonb, 'ai_line')",
        (new_pc, _TENANT, ctx["conv_id"], '["' + _MARK + '-2"]'),
    )
    cur = await db_module._conn.execute(
        "SELECT count(*) FROM problem_cards WHERE conversation_id = %s::uuid", (ctx["conv_id"],))
    (n,) = await cur.fetchone()
    assert n == 2, "作廢後應能為同一對話再建新卡（作廢卡不再佔 active 名額）"


@pytest.mark.asyncio
async def test_dismiss_rejects_resolved_card(_escalated_conv_with_card):
    """resolved → dismissed 必須 409（保護 refinery 知識來源可追溯性）。"""
    ctx = _escalated_conv_with_card
    await db_module._conn.execute(
        "UPDATE problem_cards SET status = 'resolved' WHERE id = %s::uuid", (ctx["pc_id"],))

    from core.errors import ApiError
    with pytest.raises(ApiError) as ei:
        await pcs.dismiss_card(tenant_id=_TENANT, pc_id=ctx["pc_id"])
    assert ei.value.status_code == 409
