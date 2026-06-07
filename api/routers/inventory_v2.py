"""Inventory v2 router — per-tenant 庫存端點（FR-0007 / CR-0004 §8 / ADR-0052 / ADR-0053）。

6 endpoints:
  1. GET  /tenants/{tenantId}/inventory/items                        → listInventoryItemsV2
  2. GET  /tenants/{tenantId}/inventory/items/{itemId}               → getInventoryItemV2
  3. POST /tenants/{tenantId}/inventory/items                        → createInventoryItemV2
  4. POST /tenants/{tenantId}/inventory/items/{itemId}:consume       → consumeMaterialV2
  5. POST /tenants/{tenantId}/inventory/items/{itemId}:return        → returnMaterialV2
  6. POST /tenants/{tenantId}/inventory/items/{itemId}:restock       → restockInventoryV2

per-tenant 獨立倉（HD-INV-01）：所有端點 require_tenant + cross-tenant guard（ADR-0030）。

consume（FR-0007 AC-05）：
  transaction + SELECT FOR UPDATE → 庫存充足檢查（409 INSUFFICIENT_INVENTORY）
  → serial_required 檢查（422 SERIAL_REQUIRED）→ 扣庫存 → ledger（consume）
  → reorder 低於 reorder_point → logger.info「InventoryBelowReorderPoint」

ADR-0052 status 注意：
  owner enum = platform/brand/locksmith（業主授權按 Decision(推薦) 值開發）。

ADR-0053 serial_required：
  consume 時 serial_required=true 且未帶 serial → 422。
  「缺 serial 擋 WO complete」是跨模組 gate，本波次不改 work_order_service（follow-up）。

HD-INV-03 語意注意：
  material-request（work_orders_ops_v2.recordMaterialRequestV2）是「缺料回報」；
  :consume 是「領料扣庫存」（FR-0007）；兩者語意整合留 owner 確認 + follow-up CR。
  本波次不動 work-orders material-request。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import inventory_v2_service as svc

logger = logging.getLogger("api.inventory_v2")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request body models
# ─────────────────────────────────────────────────────────────────────────────


class CreateInventoryItemBody(BaseModel):
    part_number: str = Field(..., min_length=1, description="零件編號（tenant 內唯一）")
    name: str = Field(..., min_length=1, description="品項名稱")
    category: str | None = Field(default=None, description="分類（選填）")
    unit_cost: float | None = Field(default=None, ge=0, description="單價（選填）")
    quantity_on_hand: int = Field(default=0, ge=0, description="初始庫存量")
    reorder_point: int = Field(default=0, ge=0, description="安全庫存量（低於此值觸發補貨通知）")
    supplier: str | None = Field(default=None, description="供應商（選填）")
    owner: str = Field(
        default="platform",
        description="所有者：platform / brand / locksmith（ADR-0052）",
    )
    serial_required: bool = Field(
        default=False,
        description="是否強制序號（ADR-0053；主鎖+高價零件 True）",
    )


class ConsumeMaterialBody(BaseModel):
    quantity: int = Field(..., gt=0, description="領料數量（必須 > 0）")
    work_order_id: str | None = Field(default=None, description="關聯工單 UUID（選填）")
    technician_id: str | None = Field(default=None, description="技師 UUID（選填）")
    serial: str | None = Field(
        default=None,
        description="序號（ADR-0053：serial_required=true 時必填）",
    )


class ReturnMaterialBody(BaseModel):
    quantity: int = Field(..., gt=0, description="還料數量（必須 > 0）")
    work_order_id: str | None = Field(default=None, description="關聯工單 UUID（選填）")
    technician_id: str | None = Field(default=None, description="技師 UUID（選填）")
    notes: str | None = Field(default=None, description="備註（選填）")


class RestockInventoryBody(BaseModel):
    quantity: int = Field(..., gt=0, description="補貨數量（必須 > 0）")
    supplier: str | None = Field(default=None, description="供應商（選填，補貨時更新）")
    notes: str | None = Field(default=None, description="備註（選填）")


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /tenants/{tenantId}/inventory/items
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/inventory/items",
    operation_id="listInventoryItemsV2",
    summary="列庫存品項（tenant-scoped v2，cursor 分頁）",
    response_model=dict,
)
async def list_inventory_items_v2(
    tenantId: str = Path(...),
    stock_status: str | None = Query(
        default=None,
        description="out_of_stock | low_stock | in_stock",
    ),
    category: str | None = Query(default=None, description="分類過濾"),
    owner: str | None = Query(
        default=None,
        description="platform | brand | locksmith（ADR-0052）",
    ),
    cursor: str | None = Query(default=None, description="上頁末 cursor（opaque base64）"),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    return await svc.list_inventory_items_v2(
        tenant_id=tenantId,
        cursor=cursor,
        limit=limit,
        stock_status=stock_status,
        category=category,
        owner=owner,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenantId}/inventory/items/{itemId}
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tenants/{tenantId}/inventory/items/{itemId}",
    operation_id="getInventoryItemV2",
    summary="取單筆庫存品項（tenant-scoped v2）",
    response_model=dict,
)
async def get_inventory_item_v2(
    tenantId: str = Path(...),
    itemId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    item = await svc.get_inventory_item_v2(tenant_id=tenantId, item_id=itemId)
    return {"data": item}


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /tenants/{tenantId}/inventory/items
#    庫管建品項（Idempotency-Key）
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/inventory/items",
    operation_id="createInventoryItemV2",
    summary="建立庫存品項（tenant-scoped v2）",
    status_code=201,
    response_model=dict,
)
async def create_inventory_item_v2(
    body: CreateInventoryItemBody,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    item = await svc.create_inventory_item_v2(
        tenant_id=tenantId,
        part_number=body.part_number,
        name=body.name,
        category=body.category,
        unit_cost=body.unit_cost,
        quantity_on_hand=body.quantity_on_hand,
        reorder_point=body.reorder_point,
        supplier=body.supplier,
        owner=body.owner,
        serial_required=body.serial_required,
    )

    payload = {"data": item}
    if idem is not None:
        await idem.save(201, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /tenants/{tenantId}/inventory/items/{itemId}:consume
#    FR-0007 main flow：領料扣庫存（transaction + FOR UPDATE）
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/inventory/items/{itemId}:consume",
    operation_id="consumeMaterialV2",
    summary="領料扣庫存（FR-0007，transaction + FOR UPDATE）",
    response_model=dict,
)
async def consume_material_v2(
    body: ConsumeMaterialBody,
    tenantId: str = Path(...),
    itemId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """FR-0007 AC-05：
    BEGIN → SELECT FOR UPDATE → 庫存充足（否則 409）→ serial 必填（否則 422）
    → UPDATE quantity -= N → INSERT transaction(consume) → COMMIT
    → 若扣後 qty < reorder → logger.info InventoryBelowReorderPoint（Phase II 通知）
    """
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.consume_material_v2(
        tenant_id=tenantId,
        item_id=itemId,
        quantity=body.quantity,
        work_order_id=body.work_order_id,
        technician_id=body.technician_id,
        serial=body.serial,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST /tenants/{tenantId}/inventory/items/{itemId}:return
#    還料：transaction + quantity_on_hand += quantity + INSERT transaction(return)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/inventory/items/{itemId}:return",
    operation_id="returnMaterialV2",
    summary="還料歸庫（transaction + FOR UPDATE）",
    response_model=dict,
)
async def return_material_v2(
    body: ReturnMaterialBody,
    tenantId: str = Path(...),
    itemId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.return_material_v2(
        tenant_id=tenantId,
        item_id=itemId,
        quantity=body.quantity,
        work_order_id=body.work_order_id,
        technician_id=body.technician_id,
        notes=body.notes,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 6. POST /tenants/{tenantId}/inventory/items/{itemId}:restock
#    補貨：transaction + quantity_on_hand += quantity + INSERT transaction(purchase)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/tenants/{tenantId}/inventory/items/{itemId}:restock",
    operation_id="restockInventoryV2",
    summary="補貨入庫（transaction + FOR UPDATE）",
    response_model=dict,
)
async def restock_inventory_v2(
    body: RestockInventoryBody,
    tenantId: str = Path(...),
    itemId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )

    result = await svc.restock_inventory_v2(
        tenant_id=tenantId,
        item_id=itemId,
        quantity=body.quantity,
        supplier=body.supplier,
        notes=body.notes,
    )

    payload = {"data": result}
    if idem is not None:
        await idem.save(200, payload)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 7. PATCH /tenants/{tenantId}/inventory/items/{itemId}
# ─────────────────────────────────────────────────────────────────────────────

class UpdateInventoryItemBody(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None)
    unit_cost: float | None = Field(default=None, ge=0)
    reorder_point: int | None = Field(default=None, ge=0)
    supplier: str | None = Field(default=None)
    owner: str | None = Field(default=None, description="platform/brand/locksmith")
    serial_required: bool | None = Field(default=None)


@router.patch(
    "/tenants/{tenantId}/inventory/items/{itemId}",
    operation_id="updateInventoryItemV2",
    summary="部分更新物料品項 (不動 quantity_on_hand)",
    response_model=dict,
)
async def update_inventory_item_v2(
    body: UpdateInventoryItemBody,
    tenantId: str = Path(...),
    itemId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    result = await svc.update_inventory_item_v2(
        tenant_id=tenantId, item_id=itemId, patch=patch,
    )
    return {"data": result}


# ─────────────────────────────────────────────────────────────────────────────
# 8. GET /tenants/{tenantId}/inventory/transactions
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/tenants/{tenantId}/inventory/transactions",
    operation_id="listInventoryTransactionsV2",
    summary="物料異動紀錄 (ledger) — 可選 item_id / transaction_type filter",
    response_model=dict,
)
async def list_inventory_transactions_v2(
    tenantId: str = Path(...),
    item_id: str | None = Query(default=None, description="只回此 item 的異動"),
    transaction_type: str | None = Query(
        default=None,
        description="purchase / consume / return / adjust",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
    return await svc.list_inventory_transactions_v2(
        tenant_id=tenantId,
        item_id=item_id,
        transaction_type=transaction_type,
        limit=limit,
    )
