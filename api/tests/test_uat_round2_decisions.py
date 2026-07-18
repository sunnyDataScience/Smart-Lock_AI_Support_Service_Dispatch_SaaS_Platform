"""UAT-0718 二輪裁決項回歸測試（component，需 migration 109 + scratch DB）。

- W1-6 拆帳規則 CRUD（業主裁決）：全循環（POST→409→GET→PATCH→DELETE→復活）
  + 欄位驗證邊界（base_payout ≥ 0 / 加成率 0~1 / effective ≤ expiry / rule_id 唯一）
  + 審計硬性落庫（audit_events：payout_rule.created/updated/deleted，before/after 快照）
  + RBAC（technician 403、customer_service 遮蔽 base_payout）
- N2 派工前置閘：缺 problem_type 的工單（含手建卡型態——problem_card 無 conversation 鏈）
  PATCH /fields 補 problem_type 後可過 DISPATCH_PRECONDITION 閘
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from core.errors import ApiError
from tests.conftest import DEFAULT_TENANT_ID

TID = DEFAULT_TENANT_ID

pytestmark = pytest.mark.component


def _idem() -> dict:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _purge_rule(rule_id: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM technician_payout_rule WHERE rule_id = %s", (rule_id,)
    )


async def _audit_rows(rule_id: str) -> list[tuple]:
    cur = await db_module._conn.execute(
        "SELECT action, actor_id, payload FROM audit_events "
        "WHERE event_type = 'financial_action' AND target_type = 'technician_payout_rule' "
        "  AND payload->>'rule_id' = %s ORDER BY created_at",
        (rule_id,),
    )
    return await cur.fetchall()


# ---------------------------------------------------------------------------
# W1-6 拆帳規則 CRUD 全循環 + 審計
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payout_rule_crud_lifecycle_with_audit(client, admin_headers):
    rule_id = f"E2E-PAY-{uuid.uuid4().hex[:6]}"
    body = {
        "rule_id": rule_id,
        "service_code": "SVC-E2E-001",
        "service_name": "測試拆帳服務",
        "level_id": "LV-A",
        "base_payout": 500,
        "night_surcharge_pct": 0.2,
        "urgent_surcharge_pct": 0.15,
        "effective_date": "2026-08-01",
        "expiry_date": "2027-08-01",
    }
    try:
        # Create → 201；寫入即租戶確認值（is_mock=FALSE + accepted）
        r = await client.post(
            f"/tenants/{TID}/payout-rules", json=body,
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 201, r.text
        cur = await db_module._conn.execute(
            "SELECT is_mock, decision_status, tenant_id, deleted_at "
            "FROM technician_payout_rule WHERE rule_id = %s", (rule_id,)
        )
        row = await cur.fetchone()
        assert row is not None
        assert row[0] is False
        assert row[1] == "accepted"
        assert str(row[2]) == TID
        assert row[3] is None

        # 重複 rule_id → 409 友善錯誤
        r = await client.post(
            f"/tenants/{TID}/payout-rules", json=body,
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "CODE_TAKEN"

        # GET 列表出現 + 生效日不再「—」（W1-6：effective_date 回傳）
        r = await client.get(
            f"/tenants/{TID}/payout-rules?service_code=SVC-E2E-001", headers=admin_headers
        )
        assert r.status_code == 200
        items = r.json()["data"]
        mine = next(i for i in items if i["rule_id"] == rule_id)
        assert mine["effective_date"] == "2026-08-01"
        assert mine["expiry_date"] == "2027-08-01"
        assert mine["base_payout"] == "500.00"  # admin 可見內部成本

        # PATCH（含生效日可編）→ 200
        r = await client.patch(
            f"/tenants/{TID}/payout-rules/{rule_id}",
            json={"base_payout": 650, "effective_date": "2026-09-01"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        cur = await db_module._conn.execute(
            "SELECT base_payout, effective_date, updated_at FROM technician_payout_rule "
            "WHERE rule_id = %s", (rule_id,)
        )
        row = await cur.fetchone()
        assert float(row[0]) == 650.0
        assert row[1].isoformat() == "2026-09-01"
        assert row[2] is not None  # 編輯留痕

        # DELETE（停用/軟刪）→ 200；列表消失、DB 列還在
        r = await client.delete(
            f"/tenants/{TID}/payout-rules/{rule_id}", headers=admin_headers
        )
        assert r.status_code == 200, r.text
        r = await client.get(
            f"/tenants/{TID}/payout-rules?service_code=SVC-E2E-001", headers=admin_headers
        )
        assert not any(i["rule_id"] == rule_id for i in r.json()["data"])
        cur = await db_module._conn.execute(
            "SELECT deleted_at FROM technician_payout_rule WHERE rule_id = %s", (rule_id,)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] is not None

        # 刪後再刪 → 404
        r = await client.delete(
            f"/tenants/{TID}/payout-rules/{rule_id}", headers=admin_headers
        )
        assert r.status_code == 404

        # 軟刪後同 rule_id 可重建（復活；唯一性只看未刪列）
        r = await client.post(
            f"/tenants/{TID}/payout-rules", json=body,
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 201, r.text

        # 審計硬性落庫：created ×2（含復活）+ updated + deleted，各含 before/after
        rows = await _audit_rows(rule_id)
        actions = [a for (a, _actor, _p) in rows]
        assert actions == [
            "payout_rule.created", "payout_rule.updated",
            "payout_rule.deleted", "payout_rule.created",
        ]
        for action, actor, payload in rows:
            assert actor is not None  # actor 必記
            assert payload["rule_id"] == rule_id
        created_payload = rows[0][2]
        assert created_payload["before"] is None
        assert created_payload["after"]["base_payout"] == 500
        updated_payload = rows[1][2]
        assert updated_payload["before"]["base_payout"] == 500.0
        assert updated_payload["after"]["base_payout"] == 650.0
        deleted_payload = rows[2][2]
        assert deleted_payload["before"]["base_payout"] == 650.0
        assert deleted_payload["after"] is None
    finally:
        await _purge_rule(rule_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override, msg_part",
    [
        ({"service_code": None}, "service_code"),          # 必填缺漏
        ({"base_payout": -100}, "base_payout"),            # 成本不可為負
        ({"night_surcharge_pct": 1.5}, "night_surcharge_pct"),  # 比例超出 0~1
        ({"urgent_surcharge_pct": -0.1}, "urgent_surcharge_pct"),
        ({"effective_date": "2027-01-01", "expiry_date": "2026-01-01"}, "effective_date"),
        ({"effective_date": "not-a-date"}, "effective_date"),
    ],
)
async def test_payout_rule_create_validation_422(client, admin_headers, override, msg_part):
    rule_id = f"E2E-VAL-{uuid.uuid4().hex[:6]}"
    body = {
        "rule_id": rule_id, "service_code": "SVC-E2E-002", "level_id": "LV-B",
        "base_payout": 300, **override,
    }
    body = {k: v for k, v in body.items() if v is not None}
    try:
        r = await client.post(
            f"/tenants/{TID}/payout-rules", json=body,
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 422, r.text
        assert msg_part in r.json()["message"]
        # 422 不得留任何寫入與稽核（硬性稽核=同交易，驗證失敗前置擋下）
        cur = await db_module._conn.execute(
            "SELECT 1 FROM technician_payout_rule WHERE rule_id = %s", (rule_id,)
        )
        assert await cur.fetchone() is None
        assert await _audit_rows(rule_id) == []
    finally:
        await _purge_rule(rule_id)


@pytest.mark.asyncio
async def test_payout_rule_patch_merged_date_check_422(client, admin_headers):
    """只改 effective_date 也不可越過既有 expiry_date（合併後檢查）。"""
    rule_id = f"E2E-DATE-{uuid.uuid4().hex[:6]}"
    try:
        r = await client.post(
            f"/tenants/{TID}/payout-rules",
            json={"rule_id": rule_id, "service_code": "SVC-E2E-003", "level_id": "LV-C",
                  "base_payout": 200, "expiry_date": "2026-12-31"},
            headers={**admin_headers, **_idem()},
        )
        assert r.status_code == 201, r.text
        r = await client.patch(
            f"/tenants/{TID}/payout-rules/{rule_id}",
            json={"effective_date": "2027-06-01"},
            headers=admin_headers,
        )
        assert r.status_code == 422
        # 空 body → 422 沒有可更新欄位
        r = await client.patch(
            f"/tenants/{TID}/payout-rules/{rule_id}", json={}, headers=admin_headers,
        )
        assert r.status_code == 422
        # 不存在 → 404
        r = await client.patch(
            f"/tenants/{TID}/payout-rules/NO-SUCH-RULE",
            json={"base_payout": 1}, headers=admin_headers,
        )
        assert r.status_code == 404
    finally:
        await _purge_rule(rule_id)


@pytest.mark.asyncio
async def test_payout_rule_write_rbac(client, technician_headers, customer_service_headers):
    """OPS_ROLES 之外角色寫入 403（對齊 quote_catalog CRUD 權限）。"""
    body = {"rule_id": "E2E-RBAC-X", "service_code": "SVC-X", "level_id": "LV-A",
            "base_payout": 100}
    for headers in (technician_headers, customer_service_headers):
        r = await client.post(
            f"/tenants/{TID}/payout-rules", json=body, headers={**headers, **_idem()},
        )
        assert r.status_code == 403
        r = await client.patch(
            f"/tenants/{TID}/payout-rules/PAY-SVC-RES-001-A",
            json={"base_payout": 1}, headers=headers,
        )
        assert r.status_code == 403
        r = await client.delete(
            f"/tenants/{TID}/payout-rules/PAY-SVC-RES-001-A", headers=headers,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# N2：缺 problem_type 的工單（手建卡型態）PATCH 補上後可過派工閘
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_problem_type_unblocks_dispatch_gate(client, admin_headers):
    """派工閘要求 brand/model/address/problem_type；PATCH 白名單補 problem_type 後，
    缺欄單（含手建卡：problem_card 無 conversation 鏈、wo.tenant_id 有值）有路過閘。"""
    from services import work_order_service as svc

    assert await db_module._ensure_conn()
    pc_id = str(uuid.uuid4())
    wo_id = str(uuid.uuid4())
    # 手建卡：problem_cards.conversation_id = NULL（電話進線）
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, 'Yale', 'YDM-4109', '其他', 'normal', 'confirmed')",
        (pc_id,),
    )
    # 工單缺 problem_type；tenant_id 直掛（手建卡鏈）
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_address, "
        "                         brand, model, tenant_id) "
        "VALUES (%s::uuid, %s::uuid, 'created', '台北市信義區測試路1號', "
        "        'Yale', 'YDM-4109', %s::uuid)",
        (wo_id, pc_id, TID),
    )
    try:
        # 修前：閘擋下（缺 問題類型）
        with pytest.raises(ApiError) as ei:
            await svc._assert_dispatch_ready(wo_id)
        assert ei.value.status_code == 422
        assert "問題類型" in ei.value.message

        # PATCH /fields 補 problem_type（N2：白名單新開欄位）
        r = await client.patch(
            f"/tenants/{TID}/work-orders/{wo_id}/fields",
            json={"problem_type": "感應失效"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["problem_type"] == "感應失效"

        # DB 真落庫（原 inner-join UPDATE 對手建卡鏈會靜默 0 列——回歸驗證）
        cur = await db_module._conn.execute(
            "SELECT problem_type FROM work_orders WHERE id = %s::uuid", (wo_id,)
        )
        assert (await cur.fetchone())[0] == "感應失效"

        # 修後：派工前置閘放行
        await svc._assert_dispatch_ready(wo_id)
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_orders WHERE id = %s::uuid", (wo_id,)
        )
        await db_module._conn.execute(
            "DELETE FROM problem_cards WHERE id = %s::uuid", (pc_id,)
        )
