"""CR-0160：報價列表卡階段脈絡＋空白報價送出防線（UAT 實測缺口）。

驗證面：①CR-0128 卡階段報價（work_order_id=NULL）在 GET /quotes 帶
problem_card 脈絡欄位（原本整列 NULL，前端呈全空列）；②0 品項且無總額的
報價 :submit/:send 一律 422 QUOTE_NO_LINES（原可一路 sent/accepted）；
③品項或總額擇一即放行（既有直插 total_amount 的流程不受影響）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

TID = "00000000-0000-0000-0000-000000000001"


async def _mk_pc_quote(total: float | None = None) -> tuple[str, str]:
    """建卡階段報價（無工單、無品項）；total=None 即空白報價。"""
    assert await db_module._ensure_conn()
    pid, qid = str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, tenant_id, brand, model, status, contact_phone) "
        "VALUES (%s::uuid, %s, 'Chatlock', 'A90', 'confirmed', '0912345678')", (pid, TID))
    await db_module._conn.execute(
        "INSERT INTO quote (id, tenant_id, problem_card_id, state, version, total_amount) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, 'draft', 1, %s)", (qid, TID, pid, total))
    return pid, qid


async def _cleanup(pid: str) -> None:
    await db_module._conn.execute(
        "DELETE FROM quote WHERE problem_card_id = %s::uuid", (pid,))
    await db_module._conn.execute(
        "DELETE FROM problem_cards WHERE id = %s::uuid", (pid,))


@pytest.mark.asyncio
async def test_list_carries_pc_context_for_stage_quotes(client, admin_headers):
    """卡階段報價列表項須帶 problem_card 脈絡（label／電話／版本），單號合法為 None。"""
    pid, qid = await _mk_pc_quote()
    try:
        r = await client.get(f"/tenants/{TID}/quotes", headers=admin_headers)
        assert r.status_code == 200
        item = next((x for x in r.json()["data"] if x["id"] == qid), None)
        assert item is not None, "卡階段報價應出現在列表"
        assert item["quote_number"] is None and item["work_order_number"] is None
        assert item["problem_card_id"] == pid
        assert item["problem_card_label"] == "Chatlock A90"
        assert item["contact_phone"] == "0912345678"
        assert item["version"] == 1
    finally:
        await _cleanup(pid)


@pytest.mark.asyncio
async def test_empty_quote_send_and_submit_blocked(client, admin_headers):
    """0 品項且無總額 → :send／:submit 422 QUOTE_NO_LINES（原缺口：可一路 sent）。"""
    pid, qid = await _mk_pc_quote(total=None)
    try:
        for action in ("send", "submit"):
            r = await client.post(
                f"/tenants/{TID}/quotes/{qid}:{action}", json={}, headers=admin_headers)
            assert r.status_code == 422, f"{action} 應 422，得 {r.status_code}"
            assert r.json().get("error_code") == "QUOTE_NO_LINES"
    finally:
        await _cleanup(pid)


@pytest.mark.asyncio
async def test_quote_with_total_still_sendable(client, admin_headers):
    """總額 >0（既有直插 total 流程）不受新 guard 影響，draft 直送成功。"""
    pid, qid = await _mk_pc_quote(total=800)
    try:
        r = await client.post(
            f"/tenants/{TID}/quotes/{qid}:send", json={}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["state"] == "sent"
    finally:
        await _cleanup(pid)
