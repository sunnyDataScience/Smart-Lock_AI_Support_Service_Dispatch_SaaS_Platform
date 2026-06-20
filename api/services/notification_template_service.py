"""通知模板核准 service（CR-0072 / TI-NOTIF-03 / BR-M16-03）。

對客 templated 訊息（報價/付款/派工/延遲/完工/RMA/退款）須主管核准後才可發送。
核准 gate：create → pending_approval；approve（主管 + 四眼：建立者≠核准者）→ approved；
send_from_template 僅 approved 可發（否則 TEMPLATE_NOT_APPROVED 409）。

註：CR-0062 _auto_notify 的「內部員工事件 alert」非對客 templated 訊息，走 push_notification
直發不受本 gate；本服務只管對客文案模板。
"""

from __future__ import annotations

import logging
import uuid

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services.role_service import RBAC_ADMIN_ROLES

logger = logging.getLogger("api.notification_template_service")

_VALID_TYPES = {"quote", "payment", "dispatch", "delay", "completion", "rma", "refund"}
# 主管核准角色：RBAC admin + 營運主管
APPROVER_ROLES = frozenset(RBAC_ADMIN_ROLES | {"operations_manager", "operations_director"})
# 角色可見的 audience 分層
_STAFF_SEE_ALL = frozenset(RBAC_ADMIN_ROLES | {"operations_manager", "operations_director"})
_ACCOUNTING_ROLES = frozenset({"accounting", "reviewer", "auditor"})

_SELECT = ("id, tenant_id, template_type, locale, audience_role, title, body_template, "
           "status, created_by, approved_by, approved_at")


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]), "tenant_id": str(row[1]) if row[1] else None,
        "template_type": row[2], "locale": row[3], "audience_role": row[4],
        "title": row[5], "body_template": row[6], "status": row[7],
        "created_by": str(row[8]) if row[8] else None,
        "approved_by": str(row[9]) if row[9] else None,
        "approved_at": row[10].isoformat() if row[10] else None,
    }


def _visible_audiences(role: str | None) -> set[str] | None:
    """回該角色可見的 audience 集合；None = 全可見。"""
    r = (role or "").lower()
    if r in _STAFF_SEE_ALL:
        return None
    if r in _ACCOUNTING_ROLES:
        return {"customer", "brand", "accounting"}
    return {"customer", "brand"}   # 一般 staff/外部：不看 internal/accounting


async def create_template(
    *, tenant_id: str | None, template_type: str, title: str, body_template: str,
    created_by: str, audience_role: str = "customer", locale: str = "zh-Hant",
) -> dict:
    """建模板，status 強制 pending_approval（建立者不可自我核准）。"""
    if template_type not in _VALID_TYPES:
        raise ApiError("VALIDATION_ERROR", f"template_type must be one of {sorted(_VALID_TYPES)}", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "INSERT INTO notification_template "
        "  (tenant_id, template_type, locale, audience_role, title, body_template, status, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'pending_approval', %s::uuid) "
        f"RETURNING {_SELECT}",
        (tenant_id, template_type, locale, audience_role, title, body_template, created_by))
    return _row_to_dict(await cur.fetchone())


async def approve_template(
    *, template_id: str, approver_id: str, approver_role: str, decision: str = "approve",
) -> dict:
    """核准 gate：APPROVER_ROLES + 四眼（建立者≠核准者）+ 防重複核准。"""
    if approver_role not in APPROVER_ROLES:
        raise ApiError("FORBIDDEN", "approver must be a supervisor/admin role", 403)
    if decision not in ("approve", "reject"):
        raise ApiError("VALIDATION_ERROR", "decision must be 'approve' or 'reject'", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, created_by FROM notification_template WHERE id=%s::uuid", (template_id,))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "template not found", 404)
    status, created_by = row[0], row[1]
    if status != "pending_approval":
        raise ApiError("INVALID_STATE", f"template already decided: {status}", 409)
    # 四眼：建立者不可自我核准
    if created_by and str(created_by) == str(approver_id):
        raise ApiError("SOD_VIOLATION", "creator cannot approve own template (four-eyes)", 403)
    new_status = "approved" if decision == "approve" else "rejected"
    upd = await db_module._conn.execute(
        "UPDATE notification_template SET status=%s, approved_by=%s::uuid, approved_at=NOW(), "
        "  updated_at=NOW() WHERE id=%s::uuid AND status='pending_approval' "
        f"RETURNING {_SELECT}",
        (new_status, approver_id, template_id))
    out = await upd.fetchone()
    if not out:
        raise ApiError("INVALID_STATE", "concurrent state change", 409)
    return _row_to_dict(out)


async def send_from_template(
    *, tenant_id: str, template_id: str, target_user_id: str, context: dict | None = None,
) -> dict:
    """核准 gate enforcement：僅 approved 可發。套 context 算最終文字 → INSERT notifications（帶 template_id）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT status, template_type, title, body_template FROM notification_template "
        "WHERE id=%s::uuid", (template_id,))
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "template not found", 404)
    status, ttype, title, body_tpl = row
    if status != "approved":
        raise ApiError("TEMPLATE_NOT_APPROVED", "template must be approved before sending", 409)
    ctx = context or {}
    try:
        body = body_tpl.format_map({**{k: "" for k in ()}, **ctx}) if "{" in body_tpl else body_tpl
    except (KeyError, ValueError):
        body = body_tpl   # context 缺鍵 → 原樣（不阻斷發送）
    notif_id = str(uuid.uuid4())
    ncur = await db_module._conn.execute(
        "INSERT INTO notifications (id, tenant_id, user_id, type, severity, title, body, source, template_id) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'info', %s, %s, 'template', %s::uuid) "
        "RETURNING id, type, title, template_id",
        (notif_id, tenant_id, target_user_id, ttype, title, body, template_id))
    out = await ncur.fetchone()
    return {"notification_id": str(out[0]), "type": out[1], "title": out[2],
            "template_id": str(out[3]) if out[3] else None}


async def list_templates(*, tenant_id: str | None = None, requester_role: str | None = None) -> dict:
    """列模板（角色可見性分層：internal/accounting 模板僅對應角色可見）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    visible = _visible_audiences(requester_role)
    sql = f"SELECT {_SELECT} FROM notification_template WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) "
    params: list = [tenant_id]
    if visible is not None:
        sql += "AND audience_role = ANY(%s) "
        params.append(list(visible))
    sql += "ORDER BY template_type"
    cur = await db_module._conn.execute(sql, params)
    return {"items": [_row_to_dict(r) for r in await cur.fetchall()]}
