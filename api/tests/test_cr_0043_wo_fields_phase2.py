"""CR-0043 公單欄位補完 Phase 2 測試。

兩層：
- 純函式（無 DB）：_map_service_category（修死欄 bug）、_wo_row_to_dict 35 欄映射（客名/電話 + 052 五欄）
- component（真 DB，需 migration 052）：
    * create_from_problem_card 真寫 service_category（不再 NULL）
    * update_wo_fields PATCH 設欄位 + enum 驗證 422（補寫入路徑稀薄）
    * reopen_order 建子單連回 parent（BR-M05-02）+ reason 必填
    * completion_status 六段推進（accept→complete→confirm）
    * 三段免責完工 gate（config require_consents 開 → 422）
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

import core.db as db_module
from core.errors import ApiError
from services import work_order_service as svc

TID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# 純函式：service_category 映射（HD-1）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pc_cat, expected", [
    ("安裝", "install"),
    ("新機安裝", "install"),
    ("Install new lock", "install"),
    ("保內維修", "warranty_in"),
    ("保外", "warranty_out"),
    ("warranty_out", "warranty_out"),
    ("維修", "repair"),
    ("電池故障", "repair"),
    ("", "repair"),
    (None, "repair"),
])
def test_map_service_category(pc_cat, expected):
    assert svc._map_service_category(pc_cat) == expected


# ---------------------------------------------------------------------------
# 純函式：_wo_row_to_dict 35 欄（CR-0043 index 28+）
# ---------------------------------------------------------------------------
def _row_35() -> tuple:
    now = datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc)
    return (
        uuid.uuid4(), uuid.uuid4(), None, "assigned", "high",
        "新北市板橋區文化路1號", "Yale", "YDM-4109", None, None, None, None,
        now, now, "PB-000123",
        "repair", "電池故障", "SN-1", "木門", "45mm", True, "out_warranty",
        date(2024, 1, 1), "INV-1", "pending_photos", "原因", uuid.uuid4(), 1280.5,
        # CR-0043 index 28+
        "王小明",                 # 28 customer_name
        "0912345678",            # 29 customer_phone
        "特力屋",                 # 30 dealer
        date(2025, 5, 1),        # 31 install_date
        "outdoor_covered",       # 32 rain_exposure
        True,                    # 33 special_door_surcharge
        "credit_card",           # 34 payment_method
    )


def test_wo_row_to_dict_phase2_fields():
    out = svc._wo_row_to_dict(_row_35())
    assert out["customer_name"] == "王小明"
    assert out["customer_phone"] == "0912345678"
    assert out["dealer"] == "特力屋"
    assert out["install_date"] == "2025-05-01"
    assert out["rain_exposure"] == "outdoor_covered"
    assert out["special_door_surcharge"] is True
    assert out["payment_method"] == "credit_card"


def test_wo_row_to_dict_legacy_28col_backward_compat():
    """舊 28 欄 row（無 052 欄）仍可序列化，不輸出新鍵、不爆。"""
    legacy = _row_35()[:28]
    out = svc._wo_row_to_dict(legacy)
    assert "customer_name" not in out
    assert "payment_method" not in out
    assert out["service_category"] == "repair"  # 既有欄仍在


# ===========================================================================
# component（真 DB）
# ===========================================================================
pytest_component = pytest.mark.component


async def _seed_confirmed_pc(*, category: str = "安裝") -> tuple[str, str]:
    """建 user(tenant=TID)→conversation→confirmed PC 鏈，回 (pc_id, user_id)。"""
    uid, cid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, display_name, phone, address, role) "
        "VALUES (%s::uuid, %s::uuid, '測試客戶', '0912000000', '台北市信義區忠孝東路1號', 'line_user')",
        (uid, TID),
    )
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id, status) "
        "VALUES (%s::uuid, %s::uuid, %s, 'active')",
        (cid, uid, "sess-" + pid[:12]),
    )
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, brand, model, category, urgency, status) "
        "VALUES (%s::uuid, %s::uuid, 'Yale', 'YDM-4109', %s, 'normal', 'confirmed')",
        (pid, cid, category),
    )
    return pid, uid


async def _cleanup(user_id: str, pc_id: str) -> None:
    # work_orders → problem_cards 為 ON DELETE RESTRICT，須先刪 WO（含 reopen 子單，同 pc）
    await db_module._conn.execute(
        "DELETE FROM work_order_consents WHERE work_order_id IN "
        "(SELECT id FROM work_orders WHERE problem_card_id = %s::uuid)", (pc_id,)
    )
    await db_module._conn.execute(
        "DELETE FROM work_orders WHERE problem_card_id = %s::uuid", (pc_id,)
    )
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (user_id,))


@pytest_component
@pytest.mark.asyncio
async def test_create_writes_service_category():
    """修死欄 bug：category=安裝 → service_category=install（不再 NULL）+ 客名接回。"""
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc(category="安裝")
    try:
        wo, created = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        assert created is True
        assert wo["service_category"] == "install"
        assert wo["customer_name"] == "測試客戶"
        assert wo["customer_phone"] == "0912000000"
    finally:
        await _cleanup(uid, pid)


@pytest_component
@pytest.mark.asyncio
async def test_update_wo_fields_sets_and_validates():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        wid = wo["id"]
        # 設多欄
        out = await svc.update_wo_fields(
            tenant_id=TID, wo_id=wid,
            fields={"payment_method": "cash", "rain_exposure": "indoor",
                    "serial_number": "SN-XYZ", "dealer": "特力屋", "special_door_surcharge": True},
        )
        assert out["payment_method"] == "cash"
        assert out["rain_exposure"] == "indoor"
        assert out["serial_number"] == "SN-XYZ"
        assert out["special_door_surcharge"] is True
        # bad enum → 422
        with pytest.raises(ApiError) as ei:
            await svc.update_wo_fields(tenant_id=TID, wo_id=wid, fields={"payment_method": "bitcoin"})
        assert ei.value.status_code == 422
        # 無可設欄位 → 422
        with pytest.raises(ApiError) as ei2:
            await svc.update_wo_fields(tenant_id=TID, wo_id=wid, fields={"not_a_field": "x"})
        assert ei2.value.status_code == 422
    finally:
        await _cleanup(uid, pid)


@pytest_component
@pytest.mark.asyncio
async def test_reopen_creates_child_with_parent():
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        parent, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        child = await svc.reopen_order(
            tenant_id=TID, wo_id=parent["id"], reason="客戶回報同問題復發，返修",
        )
        assert child["parent_work_order_id"] == parent["id"]
        assert child["status"] == parent["status"]  # 子單同為新建狀態（DB created → API inquiring）
        assert child["id"] != parent["id"]
        # reason 必填
        with pytest.raises(ApiError) as ei:
            await svc.reopen_order(tenant_id=TID, wo_id=parent["id"], reason="  ")
        assert ei.value.status_code == 422
    finally:
        await _cleanup(uid, pid)


@pytest_component
@pytest.mark.asyncio
async def test_completion_status_progression():
    """Tier②：completion_status 不再死欄 — accept→pending_report,
    complete(override)→pending_customer_confirm, confirm→closed。"""
    assert await db_module._ensure_conn()
    pid, uid = await _seed_confirmed_pc()
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        wid = wo["id"]
        # 強制進 in_progress（略過 assign/accept/arrival 細節）
        await db_module._conn.execute(
            "UPDATE work_orders SET status='in_progress' WHERE id=%s::uuid", (wid,)
        )
        done = await svc.complete_order(
            tenant_id=TID, wo_id=wid, summary="完工",
            is_override=True, actor_role="admin", override_reason="測試 override",
        )
        assert done["status"] == "completed"
        assert done["completion_status"] == "pending_customer_confirm"
        confirmed = await svc.confirm_order(tenant_id=TID, wo_id=wid, rating=5)
        assert confirmed["completion_status"] == "closed"
    finally:
        await _cleanup(uid, pid)


@pytest_component
@pytest.mark.asyncio
async def test_consent_gate_blocks_when_required(monkeypatch):
    """Tier④：config require_consents=on 時，缺三段免責 → 422；補齊 → 放行。"""
    assert await db_module._ensure_conn()
    from services import config_m18_service

    async def _fake_cfg(*, namespace, key="default"):
        if namespace == "completion_policy":
            return {"require_consents": True, "require_signature": False, "min_photos": 0}
        return None
    monkeypatch.setattr(config_m18_service, "read_global_value", _fake_cfg)

    # category=維修 → service_category=repair，避開 install 的 serial gate 先觸發
    pid, uid = await _seed_confirmed_pc(category="維修")
    try:
        wo, _ = await svc.create_from_problem_card(tenant_id=TID, pc_id=pid)
        wid = wo["id"]
        # 缺免責 → 422
        with pytest.raises(ApiError) as ei:
            await svc._enforce_completion_gate(
                wo_id=wid, summary="x", photo_evidence_ids=[], signature_evidence_id=None,
                is_override=False, override_reason=None, actor_role=None,
            )
        assert ei.value.error_code == "CONSENTS_REQUIRED"
        # 補三段 accepted → 放行
        for ct in ("new_installation", "lock_destruction", "personal_data"):
            await db_module._conn.execute(
                "INSERT INTO work_order_consents (work_order_id, consent_type, accepted, accepted_at) "
                "VALUES (%s::uuid, %s, TRUE, now())", (wid, ct),
            )
        out = await svc._enforce_completion_gate(
            wo_id=wid, summary="完工", photo_evidence_ids=[], signature_evidence_id=None,
            is_override=False, override_reason=None, actor_role=None,
        )
        assert out == "完工"
    finally:
        await _cleanup(uid, pid)
