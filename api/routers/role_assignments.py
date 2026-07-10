"""角色指派 SoD 雙簽 router(WBS 2.1.2 收尾/CR-0143)— 4 endpoints。

13_Security §3.1:「角色指派走 SoD 雙簽(saas.role_assignment)」——service+測試
早於 CR-0071 存在但無生產入口(CR-0038 型缺口),本 router 補接線。
流程:admin A 提案 → admin B(≠A,service 403 SOD_VIOLATION_RBAC + DB CHECK 雙防)
核准即套用 → users.role 變更。技師帳號不可經此流程(雙庫不變量,service 422)。
初次開帳的角色指派(員工申請核准/Admin 直建)不經此流程——SoD 管的是
既有帳號的角色**變更**(解讀記 CR-0143 §8-1,業主可否決)。
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from core.deps import CurrentUser, FULL_ACCESS_ROLES, role_required
from core.errors import ApiError
from services import role_assignment_service

router = APIRouter()

_ADMIN_GUARD = Depends(role_required(*FULL_ACCESS_ROLES))


def _guard_tenant(tenant_id: str, user: CurrentUser) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError("TENANT_MISMATCH", "path tenantId 與 token 不符", 403)


class ProposeBody(BaseModel):
    target_user_id: str
    to_role: str
    reason: str | None = Field(default=None, max_length=500)


class ReviewBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


@router.post(
    "/tenants/{tenantId}/role-assignments",
    operation_id="proposeRoleAssignment",
    summary="提案角色變更(SoD step-1;提案人=當前 admin)",
    status_code=201,
)
async def propose_role_assignment(
    tenantId: str, body: ProposeBody, user: CurrentUser = _ADMIN_GUARD,
) -> dict:
    _guard_tenant(tenantId, user)
    data = await role_assignment_service.propose_role_change(
        tenant_id=tenantId, target_user_id=body.target_user_id,
        to_role=body.to_role, proposer_id=user.user_id,
        proposer_role=user.role, reason=body.reason,
    )
    return {"data": data, "error": None}


@router.get(
    "/tenants/{tenantId}/role-assignments",
    operation_id="listRoleAssignments",
    summary="角色變更提案清單(?status=proposed 為待核佇列)",
)
async def list_role_assignments(
    tenantId: str,
    status: str | None = Query(default=None),
    user: CurrentUser = _ADMIN_GUARD,
) -> dict:
    _guard_tenant(tenantId, user)
    data = await role_assignment_service.list_role_assignments(
        tenant_id=tenantId, status=status)
    return {"data": data, "error": None}


@router.post(
    "/tenants/{tenantId}/role-assignments/{assignmentId}:approve",
    operation_id="approveRoleAssignment",
    summary="核准並套用(SoD step-2+3;核准人≠提案人否則 403)",
)
async def approve_role_assignment(
    tenantId: str, assignmentId: str, user: CurrentUser = _ADMIN_GUARD,
) -> dict:
    _guard_tenant(tenantId, user)
    await role_assignment_service.approve_role_change(
        tenant_id=tenantId, assignment_id=assignmentId,
        approver_id=user.user_id, approver_role=user.role,
    )
    # 核准即套用:approve 成功後 apply 為機械步驟;apply 失敗留 approved 可重試
    data = await role_assignment_service.apply_role_change(
        tenant_id=tenantId, assignment_id=assignmentId)
    return {"data": data, "error": None}


@router.post(
    "/tenants/{tenantId}/role-assignments/{assignmentId}:reject",
    operation_id="rejectRoleAssignment",
    summary="拒絕提案(擋壞提案不需雙人)",
)
async def reject_role_assignment(
    tenantId: str, assignmentId: str, body: ReviewBody | None = None,
    user: CurrentUser = _ADMIN_GUARD,
) -> dict:
    _guard_tenant(tenantId, user)
    data = await role_assignment_service.reject_role_change(
        tenant_id=tenantId, assignment_id=assignmentId,
        actor_id=user.user_id, actor_role=user.role,
        reason=body.reason if body else None,
    )
    return {"data": data, "error": None}
