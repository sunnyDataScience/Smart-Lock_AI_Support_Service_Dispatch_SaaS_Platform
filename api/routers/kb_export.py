"""KB Export router — startKbExport / getKbExport（+ 內部 download 路徑）

operationId 對齊 openapi.yaml：
  startKbExport (POST /knowledge-base/export)
  getKbExport   (GET  /knowledge-base/export/{job_id})

額外提供 GET /knowledge-base/export/{job_id}/download 供 download_url
直接命中（不對外 operationId，僅作為 KbExportJob.download_url 的目標）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import Response

from core.deps import CurrentUser, require_tenant
from core.idempotency import IdempotencyContext, idempotency_guard
from models.generated import KbExportJob, KbExportRequest
from services import kb_export_service

router = APIRouter()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.post(
    "/knowledge-base/export",
    operation_id="startKbExport",
    summary="啟動向量索引匯出（同 process 同步生成 JSONL）",
    status_code=202,
    response_model=KbExportJob,
)
async def start_kb_export(
    request: Request,
    body: KbExportRequest | None = None,
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    scope = "all"
    brand: str | None = None
    if body is not None:
        scope_val = body.scope.value if body.scope and hasattr(body.scope, "value") else body.scope
        scope = scope_val or "all"
        brand = body.brand
    job = await kb_export_service.start_export(
        tenant_id=user.tenant_id, scope=scope, brand=brand,
    )
    payload = kb_export_service._job_to_response(job, base_url=_base_url(request))
    if idem is not None:
        await idem.save(202, payload)
    return payload


@router.get(
    "/knowledge-base/export/{job_id}",
    operation_id="getKbExport",
    summary="查詢匯出任務狀態",
    response_model=KbExportJob,
)
async def get_kb_export(
    request: Request,
    job_id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    job = await kb_export_service.get_export(
        tenant_id=user.tenant_id, job_id=job_id,
    )
    return kb_export_service._job_to_response(job, base_url=_base_url(request))


@router.get(
    "/knowledge-base/export/{job_id}/download",
    summary="下載匯出 JSONL（KbExportJob.download_url 目標）",
    include_in_schema=False,
)
async def download_kb_export(
    job_id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    content, filename = await kb_export_service.download_export(
        tenant_id=user.tenant_id, job_id=job_id,
    )
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
