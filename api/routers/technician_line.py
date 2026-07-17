"""CR-0169 師傅 LINE 推播 — 綁定端點 + 平台官方號 webhook + internal 通知入口。

- 綁定四端點:技師本人(TECH_ACTION_ROLES,users.id→technicians.id 解析)。
- webhook:LINE 平台呼叫;驗 X-Line-Signature(PLATFORM_LINE_CHANNEL_SECRET,
  base64(HMAC-SHA256(secret, raw_body)));訊息文字=6 位綁定碼 → 完成綁定並回覆。
- internal 兩端點:品牌 api 派單/建池單後 service-to-service 呼叫(internal
  token,fail-soft)——品牌 api 不碰平台 LINE 憑證(CIA §4 發送端歸屬)。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re

import core.db as db_module
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel

from core.deps import CurrentUser, TECH_ACTION_ROLES, require_internal_token, role_required
from core.errors import ApiError
from services import technician_line_service as tls

logger = logging.getLogger("api.technician_line")
router = APIRouter()

_BIND_CODE_RE = re.compile(r"^\s*(\d{6})\s*$")


async def _me_technician_id(user: CurrentUser) -> str:
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT id FROM technicians WHERE user_id = %s::uuid", (user.user_id,))
    row = await cur.fetchone()
    if not row:
        raise ApiError("FORBIDDEN", "無對應技師主檔", 403)
    return str(row[0])


# ── 技師本人:綁定管理 ────────────────────────────────────────────────────────

@router.post(
    "/technicians/me/line-bind-code",
    operation_id="issueTechnicianLineBindCode",
    summary="簽發 LINE 綁定碼(6 位,TTL 10 分鐘,舊碼作廢)",
    status_code=201,
)
async def issue_bind_code(
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
) -> dict:
    tid = await _me_technician_id(user)
    data = await tls.issue_bind_code(technician_id=tid)
    return {"data": data, "error": None}


@router.get(
    "/technicians/me/line-binding",
    operation_id="getTechnicianLineBinding",
    summary="查 LINE 綁定狀態(userId 遮蔽)",
)
async def get_binding(
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
) -> dict:
    tid = await _me_technician_id(user)
    return {"data": await tls.get_binding(technician_id=tid), "error": None}


class _PoolNotifyBody(BaseModel):
    notify_pool_new: bool


@router.patch(
    "/technicians/me/line-binding",
    operation_id="updateTechnicianLineBinding",
    summary="池內新單推播開關(HD-3=b)",
)
async def update_binding(
    body: _PoolNotifyBody,
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
) -> dict:
    tid = await _me_technician_id(user)
    await tls.set_pool_notify(technician_id=tid, enabled=body.notify_pool_new)
    return {"data": await tls.get_binding(technician_id=tid), "error": None}


@router.delete(
    "/technicians/me/line-binding",
    operation_id="deleteTechnicianLineBinding",
    summary="解除 LINE 綁定",
    status_code=204,
)
async def delete_binding(
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
) -> None:
    tid = await _me_technician_id(user)
    await tls.unbind(technician_id=tid)


# ── 平台官方號 webhook ────────────────────────────────────────────────────────

def _verify_line_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = os.getenv("PLATFORM_LINE_CHANNEL_SECRET", "")
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), signature)


@router.post(
    "/technicians/line-webhook",
    operation_id="technicianLineWebhook",
    summary="平台 LINE 官方號 webhook(綁定碼訊息)",
)
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None, alias="X-Line-Signature"),
) -> dict:
    raw = await request.body()
    if not _verify_line_signature(raw, x_line_signature):
        # 驗簽失敗一律 403(未配置 secret 時亦拒——避免裸端點)
        raise ApiError("FORBIDDEN", "invalid signature", 403)
    import json
    try:
        events = json.loads(raw.decode("utf-8")).get("events", [])
    except (ValueError, UnicodeDecodeError):
        return {"data": {"handled": 0}, "error": None}

    handled = 0
    for ev in events:
        if ev.get("type") != "message" or (ev.get("message") or {}).get("type") != "text":
            continue
        text = (ev["message"].get("text") or "")
        m = _BIND_CODE_RE.match(text)
        line_user_id = (ev.get("source") or {}).get("userId")
        reply_token = ev.get("replyToken")
        if not m or not line_user_id:
            continue
        result = await tls.bind_by_code(line_user_id=line_user_id, code=m.group(1))
        if result:
            handled += 1
            if reply_token:
                await tls.reply_text(
                    reply_token,
                    f"✅ 綁定完成,{result['name']} 師傅!之後派單通知會推播到這裡。")
        elif reply_token:
            await tls.reply_text(reply_token, "❌ 綁定碼無效或已過期,請回師傅站重新產生。")
    return {"data": {"handled": handled}, "error": None}


# ── internal:品牌 api 派單/建池單後通知(service-to-service)─────────────────

class _NotifyAssignBody(BaseModel):
    technician_id: str
    work_order: dict  # {id, document_number?, district?, brand?, model?} 最小摘要


@router.post(
    "/internal/technicians/notify-assign",
    operation_id="internalNotifyTechnicianAssign",
    summary="派單指派 LINE 推播(internal;fail-soft)",
    dependencies=[Depends(require_internal_token)],
)
async def internal_notify_assign(body: _NotifyAssignBody) -> dict:
    ok = await tls.notify_assignment(technician_id=body.technician_id, wo=body.work_order)
    return {"data": {"pushed": ok}, "error": None}


class _NotifyPoolBody(BaseModel):
    work_order: dict


@router.post(
    "/internal/technicians/notify-pool",
    operation_id="internalNotifyTechnicianPool",
    summary="搶單池新單 LINE 廣播(internal;開關過濾)",
    dependencies=[Depends(require_internal_token)],
)
async def internal_notify_pool(body: _NotifyPoolBody) -> dict:
    sent = await tls.notify_pool_new(wo=body.work_order)
    return {"data": {"pushed": sent}, "error": None}
