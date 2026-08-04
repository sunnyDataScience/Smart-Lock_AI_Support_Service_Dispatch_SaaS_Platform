# TC-ONSITE-06 — 客戶不在現場的例外流程分流

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，異常框架與取消分流相關 38 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 22:05（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/exception_service.py:17-102`、`api/routers/exception_cases_v2.py:24-67`、`api/services/work_order_service.py:1727-1775`、`:2061-2075`、`:3179-3203`、`api/services/cancellation_service.py:73-76`、`:214-220`、`api/routers/cancellation.py:35-58`、`api/routers/work_orders_ops_v2.py:165-190`、`:421-445`、`api/core/deps.py:299-304`、`web/tech-portal/src/app/my-orders/[id]/delay/page.tsx:19-79`、`web/tech-portal/src/app/my-orders/[id]/reschedule/page.tsx:319-328` |
| 優先級 / 路徑類型 | P1 / 例外 |
| 事實結論 | 例外流程的**分流骨架齊備**：`exception_service._EXCEPTION_TYPES` 含 `no_show` 與 `customer_absent`（`:19`），`_RETURN_PATHS` 含 `reschedule` 與 `cancel`（`:25-28`）；high/critical 異常會設 `work_orders.high_risk_hold` 並在完工前 422 擋下（`work_order_service.py:1764-1765`、`:2061-2075`）；取消側有 `customer_not_onsite` reason code 且強制 `gps`＋`timestamp` 存證（`cancellation_service.py:73-76`、`:214-220`）。落差在「師傅回報」這一步：開立異常案件的端點 RBAC 為 `admin/operations_manager/dispatcher/customer_service`（`exception_cases_v2.py:24-26`），**不含 `technician`**；技師端 UI 也沒有「客戶未到場」的回報入口，最接近的是延誤通知的下拉選項「客戶尚未到場」，其後端只寫一筆 `delay` 事件、不建異常、不設 hold。 |

**TC 原文**｜前置：客戶不在現場｜步驟：師傅回報客戶未到場｜判定基準：工單轉入例外流程（改期/取消分流）；不得直接結案｜需求：FR-API-18｜旅程：SC-06、SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 回報客戶未到場 | `CustomerAbsentReported` | 技師可回報 | `exception_cases_v2.py:54-57` | RBAC 不含 `technician` → 403 |
| 技師 | 送延誤通知（理由=客戶尚未到場） | `DelayNotified` | — | `work_order_service.py:3195-3203` | 寫 `delay` 事件；狀態不變、無 hold |
| 後台 | 開 `customer_absent` 異常 | `ExceptionOpened` | high/critical → hold | `exception_service.py:97-101` | `UPDATE work_orders SET high_risk_hold = TRUE` |
| 系統 | 擋結案 | `CompletionBlocked(422)` | hold 時不可完工 | `work_order_service.py:2061-2075` | 422 `HIGH_RISK_HOLD`；含 override 路徑亦擋 |
| 後台 | resolve 選 return_path | `ExceptionResolved` | reschedule／cancel 分流 | `exception_service.py:25-28` | 9 個 return_path 記錄＋解除 hold |
| 技師/後台 | 改期 | `RescheduleRequested` | 技師可改期 | `work_orders_ops_v2.py:175` | `_tech_or_admin`，技師可 |
| 後台 | 取消（S3 客戶未到場） | `WorkOrderCancelled` | 須帶存證 | `cancellation_service.py:311-313` | 缺 evidence → 422 `EVIDENCE_MISSING` |

---

## 走查紀錄

### 步驟 1 — 例外類型與分流路徑

- **動作**：讀 `exception_service` 常數
- **預期**：有「客戶未到場」類型與改期／取消分流
- **實際**：一致

`api/services/exception_service.py:17-29`

```python
# 對齊 generated.py ExceptionType / Status / Severity + BR-M15-01 return_path
_EXCEPTION_TYPES = {
    "no_show", "customer_absent", "scope_change_rejected", "material_shortage",
    "delay_severe", "appearance_refused", "payment_failed", "quality_complaint",
    "schedule_conflict", "other",
}
_SEVERITIES = {"low", "medium", "high", "critical"}
_HIGH_RISK = {"high", "critical"}
_RETURN_PATHS = {
    "continue", "requote", "reschedule", "reassign", "new_wo",
    "cancel", "refund", "rma", "dispute",
}
```

### 步驟 2 — 「師傅回報」的權限

- **動作**：讀開立異常端點的 RBAC
- **預期**：技師可回報
- **實際**：技師不在白名單

`api/routers/exception_cases_v2.py:24-26`

```python
_resolve_roles = role_required(
    "admin", "operations_manager", "dispatcher", "customer_service"
)
```

`api/routers/exception_cases_v2.py:47-59`

```python
@router.post(
    "/tenants/{tenantId}/exception-cases",
    operation_id="openExceptionCase",
    summary="開立異常案件 v2（M15 control tower；high/critical + WO → high_risk_hold）",
    status_code=201,
    tags=["M15 Exception"],
)
async def open_exception_case(
    body: _OpenExceptionRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(_resolve_roles),
) -> dict:
```

對照角色常數：`api/core/deps.py:299-304`

```python
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
...
TECH_ACTION_ROLES: tuple[str, ...] = BACKOFFICE_ROLES + ("technician",)
```

即該端點用的是不含 technician 的集合。

- TC 步驟：**師傅**回報客戶未到場
- 程式碼：technician 呼叫 `openExceptionCase` 會被 `role_required` 擋為 403；能開異常的是後台四角色

此處僅並陳，不裁定。

### 步驟 3 — 技師端 UI 最接近的入口

- **動作**：讀技師端工單頁的 subflow CTA 與延誤頁
- **預期**：有「客戶未到場」回報
- **實際**：六個 CTA 中無此項；延誤頁有同名理由選項但走 `notify-delay`

技師端工單頁的 subflow 連結共六個（`web/tech-portal/src/app/my-orders/[id]/page.tsx:566-602`）：`reschedule` / `delay` / `scope-change` / `material-request` / `door-check` / `signature`。

延誤頁的理由選項：`web/tech-portal/src/app/my-orders/[id]/delay/page.tsx:19-41`

```tsx
type ReasonKey =
  | "previousOrder"
  | "traffic"
  | "customerNotArrived"
  | "materialNotArrived"
  | "other";
...
const REASON_TO_API: Record<ReasonKey, string> = {
  previousOrder: "前一單延長",
  traffic: "塞車 / 路況",
  customerNotArrived: "客戶尚未到場",
  materialNotArrived: "材料尚未到貨",
  other: "其他",
};
```

送出目標：`web/tech-portal/src/app/my-orders/[id]/delay/page.tsx:74-80`

```tsx
      await api.post(tenantPath(`/work-orders/${encodeURIComponent(id)}/notify-delay`), {
        delay_minutes: delayMinutes,
        reason: REASON_TO_API[reasonKey],
        reason_text: reasonKey === "other" ? reasonText.trim() : undefined,
        notify,
      });
```

後端行為：`api/services/work_order_service.py:3188-3203`

```python
    """記錄延遲通知（T7）。實際 LINE/SMS 推送由通知服務處理（此處僅留紀錄）。"""
    if delay_minutes < 5 or delay_minutes > 300:
        raise ApiError(
            "VALIDATION_ERROR",
            "delay_minutes must be between 5 and 300",
            422,
        )
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason,
        "reason_text": reason_text,
        "notify": notify,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id, wo_id=wo_id, tag="DELAY", payload=payload
    )
```

`_append_subflow_event`（`:2851-2887`）只寫事件＋bump `updated_at`＋推 WS，不建 `exception_case`、不設 `high_risk_hold`、不改 `status`。

技師端改期頁另有 `?from=no_show` 的提示分支：`web/tech-portal/src/app/my-orders/[id]/reschedule/page.tsx:319-328`

```tsx
      {fromHint && (
        ...
          {fromHint === "delay"
            ? ...
            : fromHint === "no_show"
              ? ...
```

`no_show` 在 `web/tech-portal/src` 中的命中僅此一處，**找不到**產生該 query 參數的連結來源。

### 步驟 4 — 「不得直接結案」的實際閘門

- **動作**：讀完工路徑上的 hold 檢查
- **預期**：例外未處理不可結案
- **實際**：一致（前提是異常已被開立且 severity 為 high/critical）

`api/services/exception_service.py:97-101`

```python
    if severity in _HIGH_RISK and work_order_id:
        await conn.execute(
            "UPDATE work_orders SET high_risk_hold = TRUE, updated_at = NOW() WHERE id = %s::uuid",
            (work_order_id,),
        )
```

`api/services/work_order_service.py:1764-1765`

```python
    # CR-0041 / BR-M15-03：high_risk_hold 擋完工（含 override，須先 resolve 異常解除 hold）
    await _assert_not_high_risk_hold(wo_id)
```

`api/services/work_order_service.py:2061-2075`

```python
async def _assert_not_high_risk_hold(wo_id: str) -> None:
    """CR-0041 BR-M15-03：high_risk_hold 旗標為 TRUE → 擋派工/完工（422）。
    ...
        "SELECT high_risk_hold FROM work_orders WHERE id = %s::uuid",
    ...
            "工單處於高風險暫停（high_risk_hold）；須先處理對應異常案件才能繼續（BR-M15-03）",
```

`open_exception` 的 `severity` 預設為 `"medium"`（`exception_service.py:69`、`exception_cases_v2.py:37`），medium 不設 hold。即：以預設嚴重度開 `customer_absent` 異常時，完工仍可進行。

### 步驟 5 — 改期／取消兩條分流的實際可用性

- **動作**：讀兩條分流端點的角色與前置
- **預期**：兩條皆可走
- **實際**：改期技師可自行發動；取消僅後台角色

改期：`api/routers/work_orders_ops_v2.py:55`、`:175`

```python
_tech_or_admin = role_required("technician", "admin", "operations_manager")
```

```python
    user: CurrentUser = Depends(_tech_or_admin),
```

多時段改約提案（`:427-434`）同樣使用 `_tech_or_admin`；service 層另限 `proposed_by_role` 三值（`work_order_service.py:3380-3385`）。

取消：`api/routers/cancellation.py:35-58`

```python
@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/cancel",
    operation_id="cancelWorkOrder6Stage",
    ...
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
```

`customer_not_onsite` reason code 與其存證要求：`api/services/cancellation_service.py:73-76`

```python
        "customer_not_onsite": {
            "stage": "S3", "fee_type": "travel_plus_cancel", "initiator": "customer",
            "technician_penalty": False, "evidence_required": ["gps", "timestamp"],
        },
```

`api/services/cancellation_service.py:214-220`

```python
def ensure_evidence(reason_entry: dict, evidence_ids: list[str] | None) -> None:
    """reason_code 要求 evidence 時必須提供（BR-M08-01）→ 否則 422 EVIDENCE_MISSING。"""
    required = reason_entry.get("evidence_required") or []
    if required and not evidence_ids:
        raise ApiError(
            "EVIDENCE_MISSING",
            f"reason_code requires evidence: {', '.join(required)}",
```

檢查僅驗 `evidence_ids` 非空，不逐項比對 `gps` / `timestamp` 是否真的存在。

### 步驟 6 — 執行既有測試

- **動作**：跑異常框架與取消分流測試
- **預期**：取得執行證據
- **實際**：38 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0041_exception_framework.py tests/test_cancellation_6stage.py \
  tests/test_cancellation_endpoint.py -q -p winloop_plugin --tb=no
38 passed in 3.63s
```

覆蓋到 TC 判定基準的兩項：

- `test_cr_0041_exception_framework.py::test_high_severity_sets_hold_and_blocks_dispatch_and_complete`（`:105`）——high 異常擋派工與完工
- `test_cr_0041_exception_framework.py::test_resolve_clears_hold_and_records_return_path`（`:126`）——resolve 記 return_path 並解除 hold
- `test_cancellation_6stage.py::test_evidence_required_missing_422`（`:167`）——`customer_not_onsite` 缺存證 422

兩檔皆以 `no_show` 為測試用的 exception_type（`test_cr_0041_exception_framework.py:77`、`:174`），無以 technician 身分開立異常的測試。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:309`（FR-API-18）描述本項為「例外審批收件匣 + SoD」，並要求 `X-Initiator/X-Approver/X-Executor` 任二相同 → 403；取消端點確有 `require_sod_actors`（`cancellation.py:59`），但 `api/routers/cancellation.py:52-56` 的註解自述 `X-Initiator` 仍為 client 提供的字串而非取自 token。
- `exception_service.open_exception` 的 `_RETURN_PATHS` 依 `:6` 註解「只『記錄 + 提示』既有端點（cancel/refund/reassign 等已存在），本框架不重寫各動作」，即 resolve 選 `reschedule`／`cancel` 後不會自動觸發該動作。
- `work_orders.status` 無「例外中」的狀態值（`work_order_service.py:915-923` 七值），例外以 `high_risk_hold` 布林旗標表達。
- `auto_confirm_stale_completed`（`work_order_service.py:4247-4295`）排除 `high_risk_hold=TRUE` 與有 open exception 的工單（`:4269`），故掛例外的單不會被自動結案。
