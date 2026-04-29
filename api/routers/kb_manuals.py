"""Knowledge Base Manuals router — listManuals + deleteManual + uploadManual。

operationId 對齊 openapi.yaml：
  listManuals, deleteManual, uploadManual

uploadManual 只建立 metadata（status='processing'），實際 PDF 解析 / 切 chunks /
向量化由 pipeline 模組接管。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile
from fastapi.responses import JSONResponse

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import Manual, ManualPage
from services import manual_service

router = APIRouter()


@router.get(
    "/knowledge-base/manuals",
    operation_id="listManuals",
    summary="手冊列表（cursor 分頁）",
    response_model=ManualPage,
)
async def list_manuals(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    brand: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await manual_service.list_manuals(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        brand=brand,
    )
    return {
        "items": [Manual(**m).model_dump(mode="json") for m in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/knowledge-base/manuals/upload",
    operation_id="uploadManual",
    summary="上傳產品手冊（multipart） — 建立 metadata 後背景處理",
    status_code=202,
)
async def upload_manual(
    file: UploadFile = File(...),
    brand: str = Form(...),
    title: str = Form(...),
    model: str | None = Form(default=None),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> JSONResponse:
    file_bytes = await file.read()
    manual = await manual_service.upload_manual(
        tenant_id=user.tenant_id,
        uploader_user_id=user.user_id,
        filename=file.filename or "manual.pdf",
        content_type=file.content_type,
        file_bytes=file_bytes,
        brand=brand,
        title=title,
        model=model,
    )
    payload = {"data": Manual(**manual).model_dump(mode="json")}
    if idem is not None:
        await idem.save(202, payload)
    return JSONResponse(status_code=202, content=payload)


@router.delete(
    "/knowledge-base/manuals/{id}",
    operation_id="deleteManual",
    summary="刪除手冊（連同 chunks 透過 FK CASCADE 一併移除）",
    status_code=204,
    response_class=Response,
)
async def delete_manual(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    await manual_service.delete_manual(tenant_id=user.tenant_id, manual_id=id)
    return Response(status_code=204)
