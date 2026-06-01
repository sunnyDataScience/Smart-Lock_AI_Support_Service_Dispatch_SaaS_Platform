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


# ─────────────────────────────────────────────────────────────────────────────
# Refund 三維 SoD + 5-tier (ADR-0040 v2 / BR-REFUND-006 / FR-0014)
# 對應 spec: saas.refund (docs/architecture/data/ddl-migration-001-init.sql:463)。
# tier 由伺服器端從 amount 推算（client 不傳）。待 generated.py 重生後移至 generated。
# ─────────────────────────────────────────────────────────────────────────────

_REFUND_CLASSES = ("product", "labor", "material", "travel", "inspection")


class RefundSodRequest(BaseModel):
    """POST /tenants/{tenantId}/refunds 的 request body。

    tier 不在 body — 伺服器端從 amount 推算（resolve_tier）。三維 SoD 行為人走
    X-Initiator / X-Approver / X-Executor headers（require_sod_actors），不在 body。
    """

    work_order_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0, description="退款金額（> 0），tier 由伺服器端推算")
    refund_class: str = Field(
        ..., description="product / labor / material / travel / inspection（必填）"
    )
    reason: str = Field(..., min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)


class RefundSodResult(BaseModel):
    """退款建立結果（對齊 saas.refund 欄位）。"""

    refund_id: str
    work_order_id: str | None = None
    amount: str  # decimal string with 2 decimals
    tier: str  # L1 / L2 / L3 / L4 / L5
    refund_class: str
    state: str  # pending / approved / executed / rejected
    initiator_user_id: str | None = None
    approver_user_ids: list[str] = Field(default_factory=list)
    executor_user_id: str | None = None
    audit_event_id: str | None = None


class RefundSodEnvelope(BaseModel):
    data: RefundSodResult


# ─────────────────────────────────────────────────────────────────────────────
# Warranty 5-mode (ADR-0044 v2 / FR-0015 / BR-WARRANTY-001..007)
# 對應 spec: openapi-smart-lock-saas.yaml DeviceWarranty / DeviceWarrantyPatch。
# 注意：warranty_mode enum 採 ADR-0044 v2 正典 6 值（覆蓋 spec 描述的舊 5 值），
# 待 spec 重生對齊後從 generated 取代。
# ─────────────────────────────────────────────────────────────────────────────

_WARRANTY_START_MODES = (
    "purchase_date",
    "install_date",
    "handover_date",
    "brand_warranty_date",
    "contract_date",
    "manual_override",
)
_WARRANTY_SCOPES = ("device", "component")
_COVERAGE_CLASSES = ("full", "parts_only", "labor_only", "expired")


class DeviceWarranty(BaseModel):
    """GET /tenants/{tenantId}/devices/{deviceId}/warranty 回應。"""

    device_id: str
    warranty_start_mode: str = Field(..., description="ADR-0044 v2 6-mode enum")
    warranty_start_date: str  # date isoformat
    warranty_end_date: str    # date isoformat
    warranty_period_months: int = Field(default=24)
    warranty_period_months_override: int | None = Field(default=None, le=60)
    warranty_scope: str = Field(default="device")
    warranty_inherit_from_site_group: bool = Field(default=True)
    coverage_class: str = Field(default="full")
    is_within_warranty: bool = Field(default=True)


class DeviceWarrantyEnvelope(BaseModel):
    data: DeviceWarranty


class DeviceWarrantyPatch(BaseModel):
    """PATCH .../warranty — manual_override only（走主管核可，回 202）。"""

    new_mode: str = Field(default="manual_override", description="本切片僅支援 manual_override")
    new_start_date: str | None = Field(default=None, description="manual_override 指定起算日 (date)")
    period_months_override: int | None = Field(
        default=None, ge=1, le=60,
        description="B2B override 上限 60 個月 (BR-WARRANTY-006)",
    )
    reason: str = Field(..., min_length=1, max_length=2000, description="manual_override 必填理由 + audit")
    contract_doc_id: str | None = Field(default=None, description="B2B override 合約 PDF doc id")


class WarrantyChangeRequestRef(BaseModel):
    """PATCH 202 回應 — ChangeRequest 串接標 TODO(P3)，先回 pending 佔位。"""

    change_request_id: str | None = None
    status: str = "pending_supervisor_approval"
    device_id: str
    requested_mode: str
