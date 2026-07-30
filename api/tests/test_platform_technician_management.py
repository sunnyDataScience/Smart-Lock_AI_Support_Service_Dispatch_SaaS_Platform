"""CR-0114 §8 追補收尾：平台 console 師傅管理端點（建立/詳情/編輯/認證 CRUD）。

裁決 1 收斂後,師傅身分管理職權全歸平台方。本檔驗證 platform_technicians.py
新增的管理端點：
  - POST   /platform/technicians                              建立（onboard）
  - GET    /platform/technicians/{id}                         詳情（含 authorized_brands）
  - PATCH  /platform/technicians/{id}                         編輯（含 level）
  - GET/POST/PATCH/DELETE /platform/technicians/{id}/certifications[/{certId}]

全部 gate = require_platform_admin：品牌 admin token 應 403、無 token 應 401。
單庫 fallback：師傅住主連線;平台 token 由 fixture 直產。
"""

from __future__ import annotations

import uuid

import pytest

import core.db as db_module
from tests.conftest import seed_required_kyc_docs  # CR-0195 核准需文件齊全

pytestmark = pytest.mark.component

PLATFORM_TECH = "/api/v1/platform/technicians"


async def _cleanup(tech_id: str) -> None:
    await db_module._ensure_conn()
    await db_module._conn.execute(
        "DELETE FROM technician_certification WHERE technician_id=%s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM saas.technician_lifecycle_event WHERE technician_id=%s::uuid", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM users WHERE id=(SELECT user_id FROM technicians WHERE id=%s::uuid)", (tech_id,))
    await db_module._conn.execute(
        "DELETE FROM technicians WHERE id=%s::uuid", (tech_id,))


async def _create(client, platform_admin_headers) -> str:
    suffix = uuid.uuid4().hex[:8]
    res = await client.post(
        PLATFORM_TECH,
        headers=platform_admin_headers,
        json={
            "display_name": f"平台建立測試{suffix}",
            "coverage_areas": ["台北市", "新北市"],
            "phone": "0911223344",
            "email": f"plat-mgmt-{suffix}@example.com",
            "capabilities": ["Yale"],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


# ── 建立 ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_technician_requires_platform_admin(client, admin_headers):
    body = {"display_name": "不該建得成", "coverage_areas": ["台北市"]}
    res = await client.post(PLATFORM_TECH, json=body)
    assert res.status_code == 401, "無 token → 401"
    res = await client.post(PLATFORM_TECH, headers=admin_headers, json=body)
    assert res.status_code == 403, "品牌 admin 不可在平台建立師傅"


@pytest.mark.asyncio
async def test_create_technician_pending_and_detail(client, platform_admin_headers):
    tech_id = await _create(client, platform_admin_headers)
    try:
        # 詳情：身分域欄位 + 生命週期起始 pending_approval
        res = await client.get(f"{PLATFORM_TECH}/{tech_id}", headers=platform_admin_headers)
        assert res.status_code == 200, res.text
        d = res.json()["data"]
        assert d["status"] == "pending_approval"
        assert d["name"].startswith("平台建立測試")
        assert "Yale" in d["skills"]
        assert set(d["service_areas"]) >= {"台北市", "新北市"}
        assert "authorized_brands" in d  # 平台詳情特有（Technician schema 外）
    finally:
        await _cleanup(tech_id)


# ── 編輯 ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_technician_fields_and_level(client, platform_admin_headers):
    tech_id = await _create(client, platform_admin_headers)
    try:
        res = await client.patch(
            f"{PLATFORM_TECH}/{tech_id}",
            headers=platform_admin_headers,
            json={
                "display_name": "改名後",
                "capabilities": ["Dormakaba", "Kaadas"],
                "coverage_areas": ["台中市"],
                "level": "A",
            },
        )
        assert res.status_code == 200, res.text
        d = res.json()["data"]
        assert d["name"] == "改名後"
        assert d["level"] == "A"
        assert set(d["skills"]) == {"Dormakaba", "Kaadas"}
        assert d["service_areas"] == ["台中市"]
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_update_technician_requires_platform_admin(client, admin_headers):
    fake = str(uuid.uuid4())
    res = await client.patch(f"{PLATFORM_TECH}/{fake}", json={"display_name": "x"})
    assert res.status_code == 401
    res = await client.patch(
        f"{PLATFORM_TECH}/{fake}", headers=admin_headers, json={"display_name": "x"})
    assert res.status_code == 403


# ── 認證 CRUD ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_certification_crud(client, platform_admin_headers):
    tech_id = await _create(client, platform_admin_headers)
    base = f"{PLATFORM_TECH}/{tech_id}/certifications"
    try:
        # 新增
        res = await client.post(
            base, headers=platform_admin_headers,
            json={"cert_name": "電子鎖安裝認證", "brand": "Yale", "obtained_at": "2025-01-01"},
        )
        assert res.status_code == 201, res.text
        cert = res.json()["data"]
        cert_id = cert["id"]
        assert cert["cert_name"] == "電子鎖安裝認證"
        assert cert["status"] == "valid"  # 無到期日 → valid

        # 列表
        lst = await client.get(base, headers=platform_admin_headers)
        assert lst.status_code == 200
        assert any(c["id"] == cert_id for c in lst.json()["data"])

        # 編輯
        patch = await client.patch(
            f"{base}/{cert_id}", headers=platform_admin_headers,
            json={"cert_name": "電子鎖安裝認證（進階）", "brand": "Kaadas"},
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["data"]["cert_name"] == "電子鎖安裝認證（進階）"

        # 刪除
        dele = await client.delete(f"{base}/{cert_id}", headers=platform_admin_headers)
        assert dele.status_code == 200, dele.text
        lst2 = await client.get(base, headers=platform_admin_headers)
        assert all(c["id"] != cert_id for c in lst2.json()["data"])
    finally:
        await _cleanup(tech_id)


@pytest.mark.asyncio
async def test_certification_write_requires_platform_admin(client, admin_headers):
    fake = str(uuid.uuid4())
    base = f"{PLATFORM_TECH}/{fake}/certifications"
    res = await client.post(base, json={"cert_name": "x"})
    assert res.status_code == 401
    res = await client.post(base, headers=admin_headers, json={"cert_name": "x"})
    assert res.status_code == 403


# ── 建立→核准 全流程（管理 + 生命週期串接）─────────────────────────────────


@pytest.mark.asyncio
async def test_create_then_approve_flow(client, platform_admin_headers):
    tech_id = await _create(client, platform_admin_headers)
    try:
        await seed_required_kyc_docs(tech_id)  # CR-0195：本測試驗建檔→核准，非文件閘
        res = await client.post(
            f"{PLATFORM_TECH}/{tech_id}:onboard-approve",
            headers=platform_admin_headers, json={},
        )
        assert res.status_code == 200, res.text
        detail = await client.get(f"{PLATFORM_TECH}/{tech_id}", headers=platform_admin_headers)
        assert detail.json()["data"]["status"] == "active"
    finally:
        await _cleanup(tech_id)
