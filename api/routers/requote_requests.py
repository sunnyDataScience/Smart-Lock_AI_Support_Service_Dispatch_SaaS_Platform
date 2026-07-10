"""OHS requote command 端點(WBS 2.4.3/CR-0144)— 對齊 16_API_Spec.yaml:391。"""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from core.deps import require_internal_token
from services import requote_service

router = APIRouter()


class RequoteBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    work_order_id: str
    technician_id: str
    reason: str
    item_diffs: list = Field(default_factory=list)
    initiated_via: str = "technician_command"
    tenant_id: str | None = None  # 單品牌 stack 可省略(退 AGENT_TENANT_ID)


@router.post(
    "/internal/requote-requests",
    operation_id="submitRequoteRequest",
    summary="技師平台發起現場報價修正 command(ADR-027;冪等回放)",
    dependencies=[Depends(require_internal_token)],
    status_code=201,
)
async def submit_requote_request(body: RequoteBody, response: Response) -> dict:
    data, replayed = await requote_service.submit_requote(
        request_id=body.request_id, work_order_id=body.work_order_id,
        technician_id=body.technician_id, reason=body.reason,
        item_diffs=body.item_diffs, initiated_via=body.initiated_via,
        tenant_id=body.tenant_id,
    )
    if replayed:
        response.status_code = 200  # 冪等回放(非新建)
    return {"data": data, "error": None}
