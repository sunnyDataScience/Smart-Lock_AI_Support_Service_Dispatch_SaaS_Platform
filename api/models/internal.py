"""內部 Pydantic models（OpenAPI 不該暴露的型別）。

也包含尚未由 datamodel-codegen 重生 generated.py 前的 transitional schemas，
這類型別應於下次 `./scripts/ci/generate-api-types.sh` + 後端 codegen 後，
從 generated.py 取代並移除此處的副本，避免兩處定義漂移。
"""

from __future__ import annotations

from pydantic import AnyUrl, BaseModel, Field


class JwtClaims(BaseModel):
    sub: str
    role: str
    tenant_id: str
    type: str
    iat: int
    exp: int
    jti: str


class SendChatMessageRequest(BaseModel):
    """客服接管後發送訊息的 request body（OpenAPI: SendChatMessageRequest）。

    對應 POST /api/v1/conversations/{id}/messages（operationId: sendChatMessage）。
    待 generated.py 重生後可從 internal 移到 generated。
    """

    content: str = Field(..., min_length=1, max_length=5000)
    media_uri: AnyUrl | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Cancellation 6-stage v2 (ADR-0102 / FR-0052)
# 對應 spec: openapi-smart-lock-saas.yaml CancellationRequest / CancellationResult。
# 待 generated.py 由新 spec (docs/architecture/api/) 重生後移至 generated。
# ─────────────────────────────────────────────────────────────────────────────

_INITIATOR_ROLES = ("customer", "customer_service", "technician", "system_auto")


class CancellationRequest(BaseModel):
    """POST /tenants/{tenantId}/work-orders/{woId}/cancel 的 request body。"""

    reason_code: str = Field(..., min_length=1, max_length=64,
                             description="from cancellation_reason_codes config lookup (ADR-0102 §B)")
    initiator_role: str = Field(..., description="customer / customer_service / technician / system_auto")
    goodwill_waiver: bool = Field(default=False, description="CS override → fee = 0 + audit")
    evidence_ids: list[str] = Field(default_factory=list)
    distance_km: float | None = Field(default=None, ge=0, description="影響 S3/S4 車馬費試算")
    note: str | None = Field(default=None, max_length=2000)


class CancellationResult(BaseModel):
    """取消結果（CancellationResult）。"""

    work_order_id: str
    cancellation_stage: str  # S1 / S1_5 / S2 / S3 / S4 / S5
    customer_fee: float
    travel_fee: float
    technician_penalty: float | None = None
    reason_code: str
    audit_event_id: str


class CancellationEnvelope(BaseModel):
    data: CancellationResult
