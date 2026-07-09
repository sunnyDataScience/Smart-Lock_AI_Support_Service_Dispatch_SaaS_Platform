"""AI Governance Trace v2 router — FR-0050 MVP 3 endpoints。

1. POST /tenants/{tid}/ai-governance/traces           寫 trace row（agent runtime 呼）
2. GET  /tenants/{tid}/ai-governance/traces           列 trace (多 filter)
3. GET  /tenants/{tid}/ai-governance/traces/summary   聚合 summary 給 dashboard
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
from core.errors import ApiError
from services import ai_governance_trace_service as svc

logger = logging.getLogger("api.ai_governance_trace_v2")

router = APIRouter()


def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)


class TraceBody(BaseModel):
    decision_type: str
    action_summary: str
    conversation_id: str | None = None
    work_order_id: str | None = None
    agent_session_id: str | None = None
    prd_source: str | None = None
    charter_rule: str | None = None
    owner_decision_ref: str | None = None
    input_payload: dict | None = None
    output_payload: dict | None = None
    guardrail_triggered: str | None = None
    guardrail_action: str | None = None
    agent_version: str | None = None


@router.post(
    "/tenants/{tenantId}/ai-governance/traces",
    operation_id="logAiDecisionTrace",
    summary="agent runtime 寫 AI decision trace row",
    response_model=dict,
    status_code=201,
)
async def log_trace(
    body: TraceBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId, write=True)
    result = await svc.log_decision(
        tenant_id=tenantId,
        **body.model_dump(exclude_none=False),
    )
    return {"data": result}


@router.get(
    "/tenants/{tenantId}/ai-governance/traces",
    operation_id="listAiDecisionTraces",
    summary="列 AI decision traces (filter by type/conversation/wo/source/rule/date)",
    response_model=dict,
)
async def list_traces(
    tenantId: str = Path(...),
    decision_type: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    work_order_id: str | None = Query(default=None),
    prd_source: str | None = Query(default=None),
    charter_rule: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.list_traces(
        tenant_id=tenantId,
        decision_type=decision_type,
        conversation_id=conversation_id,
        work_order_id=work_order_id,
        prd_source=prd_source,
        charter_rule=charter_rule,
        start_date=start_date, end_date=end_date,
        limit=limit,
    )


@router.get(
    "/tenants/{tenantId}/ai-governance/traces/summary",
    operation_id="getAiGovernanceTraceSummary",
    summary="聚合 summary 給 AI governance dashboard",
    response_model=dict,
)
async def get_summary(
    tenantId: str = Path(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _guard_tenant(user, tenantId)
    return await svc.get_trace_summary(
        tenant_id=tenantId,
        start_date=start_date, end_date=end_date,
    )
