"""Media router — 上傳 / 下載 / 列出工單相關媒體。

operationId 對齊 openapi.yaml：
  - uploadMedia          POST /media
  - getMedia             GET  /media/{id}
  - listMediaForWorkOrder GET /work-orders/{id}/media
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Path, Response, UploadFile

from core.deps import CurrentUser, require_tenant
from services import media_service

router = APIRouter()


_PURPOSE = Literal[
    "door_check_before",
    "door_check_after",
    "completion_before",
    "completion_during",
    "completion_after",
    "completion_signature",
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
]


@router.post(
    "/media",
    operation_id="uploadMedia",
    summary="上傳檔案（multipart）— 回傳 media_id 與 url",
)
async def upload_media(
    file: UploadFile = File(...),
    purpose: _PURPOSE = Form(...),
    work_order_id: str | None = Form(default=None),
    dispute_id: str | None = Form(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    file_bytes = await file.read()
    return await media_service.upload_media(
        tenant_id=user.tenant_id,
        uploader_user_id=user.user_id,
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        content_type=file.content_type,
        purpose=purpose,
        work_order_id=work_order_id,
        dispute_id=dispute_id,
    )


@router.get(
    "/media/{id}",
    operation_id="getMedia",
    summary="下載媒體檔案（含 tenant 隔離）",
)
async def get_media(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    data, content_type, filename = await media_service.get_media(
        tenant_id=user.tenant_id, media_id=id
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


@router.get(
    "/work-orders/{id}/media",
    operation_id="listMediaForWorkOrder",
    summary="列出該工單所有相關媒體（依用途與時間排序）",
)
async def list_media_for_work_order(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await media_service.list_media_for_work_order(
        tenant_id=user.tenant_id, work_order_id=id
    )


@router.get(
    "/disputes/{id}/media",
    operation_id="listMediaForDispute",
    summary="列出該爭議所有相關證據（含雙方上傳）",
)
async def list_media_for_dispute(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    return await media_service.list_media_for_dispute(
        tenant_id=user.tenant_id, dispute_id=id
    )
