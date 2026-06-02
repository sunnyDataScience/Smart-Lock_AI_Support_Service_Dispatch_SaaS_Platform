"""Vouchers Void router — 紅字沖銷（Track B S7 / ADR-VCH-001/002 / CR-0004 §8）。

endpoint:
  POST /vouchers/{id}/void   → voidVoucher（flat path，平台級，KEEP_FLAT）

設計原則（HD-VCH-002/003）：
  - flat path 無 tenant prefix：keeper 平台級，voucher 自帶 tenant_id
  - require_keeper_role：X-Keeper-Role header + user.role 屬 platform admin 集合
  - Idempotency-Key 必填（idempotency_guard，寫操作 dedup）
  - append-only：service 層只 INSERT，從不 UPDATE saas.voucher
  - 201 created：回 reversal voucher
  - 409：已被沖銷（ALREADY_VOIDED）
  - 410：目標是反向分錄本身，不可再沖（ALREADY_REVERSED）

spec：openapi.yaml L829-852 voidVoucher — 已在 spec 定義，此 router 為 code 側實作。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_keeper_role
from core.idempotency import IdempotencyContext, idempotency_guard
from services import voucher_void_service as svc

logger = logging.getLogger("api.vouchers_void")

router = APIRouter()


class VoidVoucherBody(BaseModel):
    reason: str = Field(
        ...,
        description="沖銷原因",
        pattern="^(error_correction|customer_dispute|tax_adjust)$",
    )
    comment: str | None = Field(default=None, description="備註（選填）")


@router.post(
    "/vouchers/{id}/void",
    operation_id="voidVoucher",
    summary="傳票紅字沖銷（平台級 keeper，append-only 反向分錄）",
    status_code=201,
    tags=["M17 Voucher"],
    responses={
        201: {"description": "反向分錄 voucher 建立成功"},
        400: {"description": "缺 Idempotency-Key"},
        403: {"description": "缺 X-Keeper-Role 或角色不足"},
        404: {"description": "原傳票不存在"},
        409: {"description": "此傳票已被沖銷過"},
        410: {"description": "目標傳票本身是反向分錄，不可再沖"},
    },
)
async def void_voucher(
    id: str = Path(..., description="原傳票 UUID"),
    body: VoidVoucherBody = ...,
    user: CurrentUser = Depends(require_keeper_role),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> JSONResponse:
    """傳票紅字沖銷。

    - 建反向分錄（debit/credit 對調）+ voucher_void_event 事件記錄
    - 原傳票永遠不被修改（HD-VCH-002 append-only / BR-AUDIT-007）
    - hash chain：hash_prev = 原 voucher.hash_self（HD-VCH-001）
    """
    result = await svc.void_voucher(
        voucher_id=id,
        reason=body.reason,
        comment=body.comment,
        keeper_user_id=user.user_id,
    )

    if idem is not None:
        await idem.save(201, result)

    return JSONResponse(status_code=201, content=result)
