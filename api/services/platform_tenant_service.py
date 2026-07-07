"""已開站租戶 registry 服務(CR-0118)。

CR-0114 platform console 只到「品牌**申請**審核」(開站前關卡);核准後的品牌並未
被登錄成營運中租戶,SuperAdmin 缺「我有哪幾家在營運、狀態如何、開站資訊」的正典
檢視面。此服務管理 `tenant` 表(平台庫)——平台視角的**跨品牌名冊**(與各品牌庫的
`saas.tenant`「該品牌自我描述那 1 筆」概念區隔:此處是名冊,那裡是該品牌自身)。

設計邊界(CR-0113 方案 A):SuperAdmin = 跨專案**外層 console**,**不進各品牌 DB 改
帳號**。故生命週期 status(active/suspended/terminated)為**平台層標示**;實際停站/
重啟走維運(gcloud / 各品牌後台),不在此服務。

單庫 fallback:tenant 住主連線 → 以 Schema_platform.sql 冪等建表(同 monitor_target)。
"""

from __future__ import annotations

import logging

import core.db as db_module
from core.errors import ApiError

logger = logging.getLogger("api.platform_tenant")

_SELECT_COLS = (
    "id, slug, company_name, contact_name, contact_email, contact_phone, "
    "status, plan, application_id, deploy_note, status_changed_at, status_changed_by, "
    "created_at, updated_at"
)

_VALID_STATUS = ("active", "suspended", "terminated")


async def _conn():
    try:
        return await db_module.require_platform_conn()
    except RuntimeError:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "slug": row[1],
        "company_name": row[2],
        "contact_name": row[3],
        "contact_email": row[4],
        "contact_phone": row[5],
        "status": row[6],
        "plan": row[7],
        "application_id": str(row[8]) if row[8] else None,
        "deploy_note": row[9],
        "status_changed_at": row[10].isoformat() if row[10] else None,
        "status_changed_by": str(row[11]) if row[11] else None,
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 查詢
# ─────────────────────────────────────────────────────────────────────────────

async def list_tenants(status: str | None = None) -> dict:
    conn = await _conn()
    if status:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM tenant WHERE status = %s ORDER BY created_at DESC",
            (status,),
        )
    else:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM tenant ORDER BY created_at DESC"
        )
    rows = await cur.fetchall()
    return {"data": [_row_to_dict(r) for r in rows], "message": None}


async def get_tenant(tenant_id: str) -> dict:
    conn = await _conn()
    cur = await conn.execute(
        f"SELECT {_SELECT_COLS} FROM tenant WHERE id = %s::uuid", (tenant_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "租戶不存在", 404)
    return {"data": _row_to_dict(row), "message": None}


# ─────────────────────────────────────────────────────────────────────────────
# 核准品牌申請連動(登錄租戶)
# ─────────────────────────────────────────────────────────────────────────────

async def create_from_application(app: dict) -> str | None:
    """核准品牌申請成功後登錄租戶(idempotent by slug)。回 tenant id;無 slug 回 None。

    由 brand_application_service.approve **fail-soft** 呼叫:登錄失敗不擋核准。
    """
    slug = (app.get("slug") or "").strip().lower()
    if not slug:
        return None
    conn = await _conn()
    cur = await conn.execute(
        "INSERT INTO tenant "
        "(slug, company_name, contact_name, contact_email, contact_phone, application_id) "
        "VALUES (%s, %s, %s, %s, %s, %s::uuid) "
        "ON CONFLICT (slug) DO NOTHING RETURNING id",
        (
            slug,
            app.get("company_name"),
            app.get("contact_name"),
            app.get("email"),
            app.get("phone"),
            app.get("id"),
        ),
    )
    row = await cur.fetchone()
    if row:
        logger.info("tenant 登錄 slug=%s from application=%s", slug, app.get("id"))
        return str(row[0])
    # slug 已存在(重複核准同代號)→ 回既有租戶 id
    cur2 = await conn.execute("SELECT id FROM tenant WHERE slug = %s", (slug,))
    r2 = await cur2.fetchone()
    return str(r2[0]) if r2 else None


# ─────────────────────────────────────────────────────────────────────────────
# 生命週期(平台層標示;CAS 轉移)
# ─────────────────────────────────────────────────────────────────────────────

async def _transition(
    *, tenant_id: str, from_status: str, to_status: str, actor_user_id: str
) -> dict:
    conn = await _conn()
    cur = await conn.execute(
        "UPDATE tenant SET status = %s, status_changed_at = NOW(), "
        "status_changed_by = %s::uuid, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = %s "
        f"RETURNING {_SELECT_COLS}",
        (to_status, actor_user_id, tenant_id, from_status),
    )
    row = await cur.fetchone()
    if not row:
        # CAS 失敗:區分 404(不存在)與 409(狀態不符)
        cur2 = await conn.execute("SELECT status FROM tenant WHERE id = %s::uuid", (tenant_id,))
        r2 = await cur2.fetchone()
        if not r2:
            raise ApiError("NOT_FOUND", "租戶不存在", 404)
        raise ApiError("STATE_CONFLICT", f"租戶目前狀態為 {r2[0]},無法執行此操作", 409)
    logger.info("tenant 狀態轉移 id=%s %s→%s by=%s", tenant_id, from_status, to_status, actor_user_id)
    return {"data": _row_to_dict(row), "message": None}


async def suspend(*, tenant_id: str, actor_user_id: str) -> dict:
    """停用租戶(平台層標示;active → suspended)。實際停站走維運。"""
    return await _transition(
        tenant_id=tenant_id, from_status="active", to_status="suspended",
        actor_user_id=actor_user_id,
    )


async def reactivate(*, tenant_id: str, actor_user_id: str) -> dict:
    """恢復租戶(suspended → active)。"""
    return await _transition(
        tenant_id=tenant_id, from_status="suspended", to_status="active",
        actor_user_id=actor_user_id,
    )
