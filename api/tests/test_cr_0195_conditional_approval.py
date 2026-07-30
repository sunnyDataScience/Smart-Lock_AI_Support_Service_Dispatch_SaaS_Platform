"""CR-0195 條件式核准（業主 2026-07-30 裁決選項 3）。

背景：核准端原本對 KYC 文件**零檢查**（technician_lifecycle_service.py:221-230
全鏈不查 technician_registration_document），實測 6 個 active 技師 100% 零文件——
業主問的「能否先上工後補件」其實已經在發生，只是無人察覺、也無法事後查誰沒補。

本 CR 讓「核准時文件未齊」從隱形變成**明示且可稽核**：
- 文件齊 → 行為完全不變
- 文件不齊 + 未帶 conditional → 422 KYC_DOCUMENTS_INCOMPLETE（帶缺哪幾種）
- 文件不齊 + conditional + reason(≥10 字) → 核准，落 onboarding_approved_conditional 事件

裁決對照（§8）：
- D1(a) 齊全判準 = id_front + id_back 皆有
- D2(a) 條件式核准的技師**派工資格不打折**，就是一般 active——所以本檔有一條
  負向測試釘住「status 仍是 active」，避免日後有人以為可以偷偷加狀態值
  （加了就會踩 dispatch_service.py:186 的 fail-open 黑名單）
- D3(a) 不設補件期限，故無 kyc_docs_completed 事件
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module

pytestmark = pytest.mark.component

PLATFORM_TECH = "/api/v1/platform/technicians"


async def _cleanup(tech_id: str) -> None:
    await db_module._ensure_conn()
    for sql in (
        "DELETE FROM technician_registration_document WHERE technician_id=%s::uuid",
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid",
        "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)",
        "DELETE FROM technicians WHERE id=%s::uuid",
    ):
        await db_module._conn.execute(sql, (tech_id,))


async def _new_pending(client, headers) -> str:
    suffix = uuid.uuid4().hex[:8]
    res = await client.post(
        PLATFORM_TECH, headers=headers,
        json={"display_name": f"條件核准測試{suffix}", "coverage_areas": ["台北市"],
              "phone": "0911223344", "email": f"cond-{suffix}@example.com"},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _add_doc(tech_id: str, doc_type: str) -> None:
    """直接塞一列文件 metadata（不走上傳端點——本檔標的是核准閘，不是上傳）。"""
    await db_module._ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT tenant_id FROM technicians WHERE id=%s::uuid", (tech_id,))
    tenant_id = (await cur.fetchone())[0]
    await db_module._conn.execute(
        "INSERT INTO technician_registration_document "
        "  (id, technician_id, tenant_id, doc_type, filename, content_type, "
        "   size_bytes, storage_path, sha256) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), tech_id, str(tenant_id), doc_type, f"{doc_type}.png",
         "image/png", 100, f"kyc-registration/{tech_id}/{doc_type}.png",
         uuid.uuid4().hex * 2),
    )


async def _last_event(tech_id: str) -> tuple[str, str]:
    await db_module._ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT event_type, reason FROM saas.technician_lifecycle_event "
        "WHERE technician_id=%s::uuid ORDER BY created_at DESC LIMIT 1",
        (tech_id,),
    )
    row = await cur.fetchone()
    return (row[0], row[1]) if row else ("", "")


# ── 文件齊全：行為完全不變 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_with_complete_docs_unchanged(client, platform_admin_headers):
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        await _add_doc(tech_id, "id_front")
        await _add_doc(tech_id, "id_back")
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers, json={},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["new_status"] == "active"
        event_type, _ = await _last_event(tech_id)
        assert event_type == "onboarding_approved", "齊全時不該落 conditional 事件"
    finally:
        await _cleanup(tech_id)


# ── 文件不齊：必須顯式承認 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_without_docs_is_blocked(client, platform_admin_headers):
    """這是本 CR 的核心：原本會**靜默核准**，現在必須顯式承認。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers, json={},
        )
        assert res.status_code == 422, res.text
        body = res.json()
        assert body["error_code"] == "KYC_DOCUMENTS_INCOMPLETE"
        # 必須告訴審核者缺什麼，否則他只會看到一個擋路的錯誤而不知道要補哪份
        assert "id_front" in body["message"] and "id_back" in body["message"]
        # 且技師必須**還在 pending**——擋下就是擋下，不可半套
        detail = await client.get(f"{PLATFORM_TECH}/{tech_id}", headers=platform_admin_headers)
        assert detail.json()["data"]["status"] == "pending_approval"
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_partial_docs_still_blocked(client, platform_admin_headers):
    """只有正面沒有反面 → 仍算不齊（D1(a) 兩面都要）。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        await _add_doc(tech_id, "id_front")
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers, json={},
        )
        assert res.status_code == 422, res.text
        assert "id_back" in res.json()["message"]
        assert "id_front" not in res.json()["message"], "已上傳的不該列進缺件清單"
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_conditional_requires_substantive_reason(client, platform_admin_headers):
    """帶了 conditional 但理由敷衍 → 仍擋。理由是要留給稽核看的，不是打勾。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        for bad in (None, "", "急"):
            res = await client.post(
                f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
                headers=platform_admin_headers,
                json={"conditional": True, "conditional_reason": bad},
            )
            assert res.status_code == 422, f"reason={bad!r} 應被擋：{res.text}"
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_conditional_approval_succeeds_and_is_auditable(
    client, platform_admin_headers
):
    """業主的情境：師傅不夠、急著要人 → 可以放行，但這個決定必須留下痕跡。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers,
            json={"conditional": True,
                  "conditional_reason": "颱風災後急件人力不足，先上工兩週內補件"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["new_status"] == "active"

        event_type, reason = await _last_event(tech_id)
        assert event_type == "onboarding_approved_conditional"
        assert "id_front" in reason and "id_back" in reason, "稽核要看得出當時缺什麼"
        assert "颱風災後急件人力不足" in reason, "稽核要看得出當時的理由"
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_conditional_technician_is_plain_active(client, platform_admin_headers):
    """D2(a) 負向釘樁：條件式核准的技師**就是一般 active**，派工資格不打折。

    這條看似多餘，但它擋的是未來有人「順手」加一個 active_pending_docs 狀態值——
    那會踩 dispatch_service.py:186 的 fail-open 黑名單（漏改＝未驗證技師直接進
    派工候選集），成本比本 CR 高一個數量級。要改請走新的 CIA。
    """
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers,
            json={"conditional": True, "conditional_reason": "人力吃緊先放行，後補件"},
        )
        detail = await client.get(f"{PLATFORM_TECH}/{tech_id}", headers=platform_admin_headers)
        assert detail.json()["data"]["status"] == "active", "不得是任何新狀態值"
    finally:
        await _cleanup(tech_id)


# ── S3 可視性：查得到誰沒補 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_exposes_kyc_docs_complete(client, platform_admin_headers):
    """沒有這個欄位，條件式核准就只是把漏洞制度化——平台端仍不知道誰還沒補。"""
    incomplete = await _new_pending(client, platform_admin_headers)
    complete = await _new_pending(client, platform_admin_headers)
    try:
        await _add_doc(complete, "id_front")
        await _add_doc(complete, "id_back")
        res = await client.get(PLATFORM_TECH, headers=platform_admin_headers)
        assert res.status_code == 200, res.text
        by_id = {r["id"]: r for r in res.json()["data"]}
        assert by_id[incomplete]["kyc_docs_complete"] is False
        assert by_id[complete]["kyc_docs_complete"] is True
    finally:
        await _cleanup(incomplete)
        await _cleanup(complete)


# ── S1 解封補件通道 ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_active_technician_can_still_get_upload_link(
    client, platform_admin_headers
):
    """核准後仍簽得出補件連結——這正是業主回報的那個 409。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers,
            json={"conditional": True, "conditional_reason": "人力吃緊先放行，後補件"},
        )
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:issue-upload-token",
            headers=platform_admin_headers,
        )
        assert res.status_code == 200, f"active 應可簽補件 token，實得：{res.text}"
        assert res.json()["data"].get("token")
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_terminated_technician_cannot_get_upload_link(
    client, platform_admin_headers
):
    """放寬只到 active——終態技師補件無意義，仍須擋（不是全面拆閘）。"""
    tech_id = await _new_pending(client, platform_admin_headers)
    try:
        await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers,
            json={"conditional": True, "conditional_reason": "人力吃緊先放行，後補件"},
        )
        await client.post(
            f"{PLATFORM_TECH}/{tech_id}:terminate",
            headers=platform_admin_headers,
            json={"reason": "測試終止"},
        )
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:issue-upload-token",
            headers=platform_admin_headers,
        )
        assert res.status_code == 409, f"terminated 仍應擋，實得：{res.text}"
    finally:
        await _cleanup(tech_id)
