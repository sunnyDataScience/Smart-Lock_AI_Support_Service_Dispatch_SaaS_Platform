"""SC-13～SC-19 整合測試計畫代跑（2026-07-31）發現的三個缺陷。

三個缺陷都不是「寫錯」，而是**規格與實作對撞**或**守衛漏掛**，各自的來源：

1. **工單列表未依角色收斂 scope**（TC-DISPATCH-05 / TC-PLT-SURFACE-01）
   `GET /api/v1/work-orders`（v1）與 `GET /tenants/{tid}/work-orders`（v2）都只有
   `Depends(require_tenant)`，沒有任何角色判斷，`technician_id` 只是「可選過濾參數」。
   實測：技師 token 拿到的回應與品牌 admin **位元組完全相同**（4 筆 / 4966 bytes），
   含未指派給他的工單與 customer_name / customer_phone。
   TC-DISPATCH-05 明文要求「投影僅含…該技師派工」。
   修法不是回 403（師傅站正常功能就是讀這支），而是**依角色強制收斂**：
   role=technician → 一律以本人的 technicians.id 過濾，且**忽略**client 傳來的
   technician_id（否則改個參數就能看別人的單）。

2. **對帳閘門在投影未啟用時真空通過**（TC-EXC-06）
   `event_reconcile_service.reconcile_commission` 在 `KAFKA_BOOTSTRAP` 未設時回
   `{"skipped": True, "gate_pass": True}`——`monthly_settlement_service` 註解寫著
   「fail-open by design，單庫/無事件不誤擋」。但「無法驗證」不等於「驗證通過」：
   一旦 `reconcile_gate_enforce` 被打開（業主明示要求對帳把關），Kafka 沒開反而
   靜默放行，閘門形同虛設。改為 `gate_pass=False` + 明確 reason。
   **爆炸半徑僅限已開啟 enforce 的租戶**（該 config 預設 off）。

3. **品牌授權 fail-open**（TC-DISPATCH-06）
   規格明文「無授權資料時 fail-closed **不得** fail-open」，實作卻在該品牌查無
   授權列時回 None，且 auto-match 與手動指派**都選擇不阻擋**（原註解：「該品牌無
   授權資料 → 不阻擋」）。且本機 seed 上這是**唯一會走到的分支**：所有工單 brand
   都是 Chatlock，而 technician_brand_authorization 沒有任何 Chatlock 列。
   → 品牌授權閘門對真實資料完全沒有作用。
   改為 fail-closed，但保留既有的主管 override_reason 安全閥（與報價 gate 同一機制）。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ─────────────────────────────────────────────────────────────────────────
# 缺陷 1：工單列表未依角色收斂 scope
# ─────────────────────────────────────────────────────────────────────────


async def _seed_two_technicians_with_orders() -> tuple[str, str, str, str, str]:
    """建兩名技師、各一張問題卡與工單，回 (userA, techA, techB, woA, woB)。

    woB 指派給技師 B —— 技師 A 不該看得到它。
    每張工單各自一張問題卡（work_orders.problem_card_id 有唯一約束）。

    所有查詢都帶 technician_id 過濾：scratch 庫存有髒資料（某列 problem_card_id
    是字串 'None'），不過濾的話 admin 對照組會在 pydantic 驗證炸掉，紅得與本次
    要驗的東西無關。
    """
    assert await db_module._ensure_conn(), "測試需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    tech_a, tech_b = str(uuid.uuid4()), str(uuid.uuid4())
    wo_a, wo_b = str(uuid.uuid4()), str(uuid.uuid4())

    for uid, name in ((user_a, "scope-a"), (user_b, "scope-b")):
        await conn.execute(
            "INSERT INTO users (id, tenant_id, email, password_hash, role, is_active) "
            "VALUES (%s::uuid, %s::uuid, %s, 'x', 'technician', TRUE) "
            "ON CONFLICT (id) DO NOTHING",
            (uid, DEFAULT_TENANT_ID, f"{name}-{uid[:8]}@example.com"),
        )
    for tid, uid, name in ((tech_a, user_a, "範圍測試甲"), (tech_b, user_b, "範圍測試乙")):
        await conn.execute(
            "INSERT INTO technicians (id, tenant_id, user_id, name, phone, status) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'active') "
            "ON CONFLICT (id) DO NOTHING",
            (tid, DEFAULT_TENANT_ID, uid, name, f"09{tid[:8]}"),
        )
    for wid, tid in ((wo_a, tech_a), (wo_b, tech_b)):
        pc = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO problem_cards (id, tenant_id, source, knowledge_ready, brand) "
            "VALUES (%s::uuid, %s::uuid, 'manual', FALSE, 'Chatlock') "
            "ON CONFLICT (id) DO NOTHING",
            (pc, DEFAULT_TENANT_ID),
        )
        await conn.execute(
            "INSERT INTO work_orders (id, tenant_id, technician_id, problem_card_id, status, brand) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'assigned', 'Chatlock') "
            "ON CONFLICT (id) DO NOTHING",
            (wid, DEFAULT_TENANT_ID, tid, pc),
        )
    return user_a, tech_a, tech_b, wo_a, wo_b


def _tech_headers(user_id: str) -> dict[str, str]:
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=user_id, role="technician", tenant_id=DEFAULT_TENANT_ID, token_type="access"
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": DEFAULT_TENANT_ID}


async def test_v1_admin_can_see_other_technicians_orders(client, admin_headers):
    """對照組：admin 帶 technician_id=B 看得到 B 的單。

    沒有這條，下面兩條測試就算「技師看不到」也可能只是資料沒建起來。
    """
    _user_a, _tech_a, tech_b, _wo_a, wo_b = await _seed_two_technicians_with_orders()
    r = await client.get(
        f"/api/v1/work-orders?limit=100&technician_id={tech_b}", headers=admin_headers
    )
    assert r.status_code == 200
    assert wo_b in {w["id"] for w in r.json()["items"]}


async def test_v1_technician_cannot_see_other_technicians_orders(client):
    """技師把 technician_id 換成別人的，仍不得撈到別人的單（參數竄改）。"""
    user_a, _tech_a, tech_b, _wo_a, wo_b = await _seed_two_technicians_with_orders()
    r = await client.get(
        f"/api/v1/work-orders?limit=100&technician_id={tech_b}", headers=_tech_headers(user_a)
    )
    assert r.status_code == 200
    assert wo_b not in {w["id"] for w in r.json()["items"]}, (
        "傳別人的 technician_id 不得繞過 scope（TC-DISPATCH-05）"
    )


async def test_v1_technician_sees_own_orders(client):
    """收斂之後技師仍看得到自己的單 —— 確認修正沒有把師傅站功能一起關掉。"""
    user_a, tech_a, _tech_b, wo_a, _wo_b = await _seed_two_technicians_with_orders()
    r = await client.get(
        f"/api/v1/work-orders?limit=100&technician_id={tech_a}", headers=_tech_headers(user_a)
    )
    assert r.status_code == 200
    assert wo_a in {w["id"] for w in r.json()["items"]}


async def test_v2_technician_cannot_see_other_technicians_orders(client):
    """v2（/tenants/{tid}/work-orders）同語意 —— 師傅站實際打的是這支。"""
    user_a, _tech_a, tech_b, _wo_a, wo_b = await _seed_two_technicians_with_orders()
    r = await client.get(
        f"/tenants/{DEFAULT_TENANT_ID}/work-orders?limit=100&technician_id={tech_b}",
        headers=_tech_headers(user_a),
    )
    assert r.status_code == 200
    assert wo_b not in {w["id"] for w in r.json()["items"]}, "v2 也必須收斂 scope"


# ─────────────────────────────────────────────────────────────────────────
# 缺陷 2：對帳閘門在投影未啟用時真空通過
# ─────────────────────────────────────────────────────────────────────────


async def test_reconcile_gate_skipped_is_not_a_pass(monkeypatch):
    """Kafka 未啟用＝無法驗證，不得回報 gate_pass=True。"""
    from services import event_reconcile_service

    monkeypatch.setattr("core.event_bus.enabled", lambda: False)
    result = await event_reconcile_service.reconcile_commission(tenant_id=DEFAULT_TENANT_ID)

    assert result["skipped"] is True, "仍應標記 skipped（呼叫端要能分辨『沒跑』與『跑了不過』）"
    assert result["gate_pass"] is not True, (
        "無法驗證 ≠ 驗證通過：skipped 時回 gate_pass=True 會讓 reconcile_gate_enforce 形同虛設"
    )
    assert result.get("reason"), "必須說明為什麼略過，否則呼叫端無從診斷"


async def test_settlement_gate_blocks_when_projection_unavailable(monkeypatch):
    """enforce 打開 + 投影未啟用 → 應阻結算（而非靜默放行）。

    enforce 預設 off，所以這條只影響「明示要求對帳把關」的租戶。
    """
    from core.errors import ApiError
    from services import monthly_settlement_service

    monkeypatch.setattr("core.event_bus.enabled", lambda: False)

    async def _cfg_enforced(*_a, **_k):
        return {"reconcile_gate_enforce": True}

    monkeypatch.setattr(
        "services.config_m18_service.read_global_value", _cfg_enforced, raising=False
    )

    with pytest.raises(ApiError) as exc:
        await monthly_settlement_service._assert_reconcile_gate(tenant_id=DEFAULT_TENANT_ID)
    assert exc.value.status_code in (409, 422)


# ─────────────────────────────────────────────────────────────────────────
# 缺陷 3：品牌授權 fail-open
# ─────────────────────────────────────────────────────────────────────────


def _enforce(monkeypatch, on: bool):
    """切換 M18 開關 dispatch_policy.brand_auth_enforce（CR-0197 D1(c)）。"""
    async def _cfg(*_a, **_k):
        return {"brand_auth_enforce": on}
    monkeypatch.setattr("services.config_m18_service.read_global_value", _cfg)


async def test_brand_gate_off_by_default_preserves_legacy_behaviour(monkeypatch):
    """**預設 off**：維持 CR-0060 以來的行為（無授權資料回 None＝不阻擋）。

    這條比 fail-closed 那條更重要——它釘住「業主還沒開閘門之前，派工不會被打斷」。
    prod 的授權表只有 CR-0060 的 is_mock seed，硬性 fail-closed 會擋掉
    Chatlock/Dormakaba 等實際在用品牌的自動派工。
    """
    from services import dispatch_service

    assert await db_module._ensure_conn(), "測試需要真實 DB 連線（scratch 庫）"
    _enforce(monkeypatch, False)
    unknown_brand = f"NoSuchBrand-{uuid.uuid4().hex[:8]}"
    assert await dispatch_service._brand_authorized_ids(unknown_brand) is None


async def test_brand_gate_falls_back_to_off_when_config_unreadable(monkeypatch):
    """config 讀不到時視為未啟用——default-off 開關讀取失敗不該變成擋人。"""
    from services import dispatch_service

    assert await db_module._ensure_conn()

    async def _boom(*_a, **_k):
        raise RuntimeError("config store down")

    monkeypatch.setattr("services.config_m18_service.read_global_value", _boom)
    assert await dispatch_service.brand_auth_enforced() is False
    assert await dispatch_service._brand_authorized_ids(f"X-{uuid.uuid4().hex[:6]}") is None


async def test_brand_without_authorization_data_is_fail_closed(monkeypatch):
    """該品牌無任何授權列 → 不得回 None（None 會讓兩個呼叫端一起放行）。

    TC-DISPATCH-06：「無授權資料時不得 fail-open」。
    """
    from services import dispatch_service

    assert await db_module._ensure_conn(), "測試需要真實 DB 連線（scratch 庫）"
    _enforce(monkeypatch, True)
    unknown_brand = f"NoSuchBrand-{uuid.uuid4().hex[:8]}"
    ids = await dispatch_service._brand_authorized_ids(unknown_brand)
    assert ids is not None, "無授權資料應回空集合（＝誰都不符），不是 None（＝不判斷）"
    assert ids == set()


async def test_manual_assign_blocked_when_brand_has_no_authorization(monkeypatch):
    """手動指派：品牌無授權資料時應擋下，不再靜默放行。"""
    from core.errors import ApiError
    from services import work_order_service

    assert await db_module._ensure_conn(), "測試需要真實 DB 連線（scratch 庫）"
    _enforce(monkeypatch, True)
    conn = db_module._conn
    wo_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO work_orders (id, tenant_id, status, brand) "
        "VALUES (%s::uuid, %s::uuid, 'created', %s) ON CONFLICT (id) DO NOTHING",
        (wo_id, DEFAULT_TENANT_ID, f"NoAuth-{uuid.uuid4().hex[:8]}"),
    )
    with pytest.raises(ApiError) as exc:
        await work_order_service._assert_brand_authorized(
            wo_id, str(uuid.uuid4()), actor_role="dispatcher", override_reason=None
        )
    assert exc.value.status_code == 403


async def test_manual_assign_override_still_works_for_supervisor(monkeypatch):
    """安全閥不可一起關掉：主管帶 override_reason 仍可強制派工（沿用報價 gate 機制）。

    fail-closed 若沒有這條，品牌尚未建授權名單時會整個派不出去。
    """
    from services import work_order_service

    assert await db_module._ensure_conn(), "測試需要真實 DB 連線（scratch 庫）"
    conn = db_module._conn
    wo_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO work_orders (id, tenant_id, status, brand) "
        "VALUES (%s::uuid, %s::uuid, 'created', %s) ON CONFLICT (id) DO NOTHING",
        (wo_id, DEFAULT_TENANT_ID, f"NoAuth-{uuid.uuid4().hex[:8]}"),
    )
    # 不 raise 即通過
    await work_order_service._assert_brand_authorized(
        wo_id, str(uuid.uuid4()), actor_role="admin", override_reason="品牌授權名單尚未建立，主管核准先派"
    )
