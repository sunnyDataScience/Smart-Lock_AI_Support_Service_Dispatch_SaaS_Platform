"""Media v2 router — tenant-scoped 媒體上傳 / 下載 / 列表（CR-0003 P2-W6 / BUILD_TENANT_SCOPED）。

spec 對齊（路徑無 /api/v1 前綴，frozen spec 定義）：
  POST  /tenants/{tenantId}/media
       → uploadMediaV2（上傳檔案 multipart，回傳 media_id + url）
  GET   /tenants/{tenantId}/media/{mediaId}
       → getMediaV2（下載檔案，含 tenant 隔離）
  GET   /tenants/{tenantId}/work-orders/{woId}/media
       → listMediaForWorkOrderV2（工單媒體列表，依用途與時間排序）
  GET   /tenants/{tenantId}/disputes/{disputeId}/media
       → listMediaForDisputeV2（爭議證據列表，含雙方上傳）

legacy 對映：
  POST /api/v1/media                       → POST /tenants/{tenantId}/media
  GET  /api/v1/media/{id}                  → GET  /tenants/{tenantId}/media/{mediaId}
  GET  /api/v1/work-orders/{id}/media      → GET  /tenants/{tenantId}/work-orders/{woId}/media
  GET  /api/v1/disputes/{id}/media         → GET  /tenants/{tenantId}/disputes/{disputeId}/media

設計原則：
  - require_tenant + cross-tenant guard（ADR-0030）
  - idempotency_guard 不套用 uploadMediaV2：multipart form-data 上傳會先消費 request stream，
    與 idempotency_guard 內部的 request.body() 呼叫衝突（"Stream consumed" RuntimeError）。
    上傳天然冪等（sha256 欄位 + media_id UUID 唯一），不需 key-based dedup。
  - 呼既有 media_service 函式；零業務邏輯重寫、不動 DB schema
  - 回傳型別：dict / Response（寬鬆 envelope，避免 float/None/pattern mismatch；W1 教訓）
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Path, Response, UploadFile

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from services import media_service

router = APIRouter()


_PURPOSE = Literal[
    "door_check_before",
    "door_check_after",
    "completion_before",
    "completion_after",
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
]


# ---------------------------------------------------------------------------
# POST /tenants/{tenantId}/media
# ---------------------------------------------------------------------------


@router.post(
    "/tenants/{tenantId}/media",
    operation_id="uploadMediaV2",
    summary="上傳檔案 v2（tenant-scoped multipart）— 回傳 media_id 與 url",
    tags=["Media"],
)
async def upload_media_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    file: UploadFile = File(...),
    purpose: _PURPOSE = Form(...),
    work_order_id: str | None = Form(default=None),
    dispute_id: str | None = Form(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    file_bytes = await file.read()
    return await media_service.upload_media(
        tenant_id=tenantId,
        uploader_user_id=user.user_id,
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        content_type=file.content_type,
        purpose=purpose,
        work_order_id=work_order_id,
        dispute_id=dispute_id,
    )


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/media/{mediaId}
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/media/{mediaId}",
    operation_id="getMediaV2",
    summary="下載媒體檔案 v2（tenant-scoped，含 tenant 隔離）",
    tags=["Media"],
)
async def get_media_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    mediaId: str = Path(..., description="媒體 UUID"),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    data, content_type, filename = await media_service.get_media(
        tenant_id=tenantId, media_id=mediaId
    )
    safe_name = filename.replace('"', "")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/work-orders/{woId}/media
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/work-orders/{woId}/media",
    operation_id="listMediaForWorkOrderV2",
    summary="列出工單所有相關媒體 v2（tenant-scoped，依用途與時間排序）",
    tags=["Media"],
)
async def list_media_for_work_order_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    woId: str = Path(..., description="工單 UUID"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await media_service.list_media_for_work_order(
        tenant_id=tenantId, work_order_id=woId
    )


# ---------------------------------------------------------------------------
# GET /tenants/{tenantId}/disputes/{disputeId}/media
# ---------------------------------------------------------------------------


@router.get(
    "/tenants/{tenantId}/disputes/{disputeId}/media",
    operation_id="listMediaForDisputeV2",
    summary="列出爭議所有相關證據 v2（tenant-scoped，含雙方上傳）",
    tags=["Media"],
)
async def list_media_for_dispute_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    disputeId: str = Path(..., description="爭議 UUID"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await media_service.list_media_for_dispute(
        tenant_id=tenantId, dispute_id=disputeId
    )
