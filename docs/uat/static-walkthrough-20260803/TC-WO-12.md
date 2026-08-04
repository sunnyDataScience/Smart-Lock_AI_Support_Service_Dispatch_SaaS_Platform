# TC-WO-12 — 六階段取消的費用套用與稽核欄位

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（33 項全過）＋一支置於 scratchpad 的探針（未入 repo）逐階段量測費用與稽核 payload（見步驟 5、6） |
| 走查時間 | 2026-08-03 20:30（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/cancellation_service.py:39-118`、`:137-188`、`:282-443`、`api/routers/cancellation.py:35-93`、`api/models/internal.py:85-107`、`api/services/config_service.py:86-105`、`api/tests/test_cancellation_6stage.py`、`api/tests/test_cancellation_endpoint.py` |
| 優先級 / 路徑類型 | P0 / happy＋例外 |
| 事實結論 | 六個 `fee_type` 與 TC 列舉的 0 / 0 / 取消費 / 車馬+取消 / 車馬+檢測+取消 / 完工比例+車馬一一對應，S1～S4 實跑金額為 0 / 0 / 300 / (500+500) / (1100+500)。S5 的「完工比例」在 `compute_fees` 有 `completed_ratio` 參數，但編排函式 `cancel_work_order_6stage` 呼叫時未傳（`cancellation_service.py:327-330`），ratio 取預設 1.0，實跑為工項全額 2000 + 車馬 500。缺 `reason_code` → 422（pydantic `VALIDATION_ERROR`）、未知 code → 422 `REASON_CODE_UNKNOWN`。稽核 payload 含 `cancellation_stage`、`original_amount`/`new_amount`/`travel_fee`，但無 body 的 `initiator_role` 欄位，發起人以 `operator_id`（SoD header 字串）與 `technician_initiated` 布林承載。 |

**TC 原文**｜前置：S1 / S1.5 / S2 / S3 / S4 / S5 六階段 fixture｜步驟：依報價未確認、已確認未派工、已派未出發、出發中、到場未施工、部分完工逐階段取消｜判定基準：依 ADR-0102 v2 套用 0 / 0 / 取消費 / 車馬+取消 / 車馬+檢測+取消 / 完工比例+車馬；缺 reason_code → 422；audit 含 stage/fee/initiator｜happy＋例外｜P0｜FR-API-11｜SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | POST `.../work-orders/{woId}/cancel` | `CancellationPosted` | SoD 三維 + 角色白名單 | `routers/cancellation.py:58-59` | `role_required(*BACKOFFICE_ROLES)` + `require_sod_actors` |
| 系統 | 查 reason code | `ReasonResolved` | 字典為權威 | `cancellation_service.py:125-134` | 未知 → 422 `REASON_CODE_UNKNOWN` |
| 系統 | 推算階段 | `StageDerived` | code 明確階段優先，`any` 由狀態映射 | `cancellation_service.py:137-143` | `_STATUS_TO_STAGE` created/assigned/accepted/in_progress → S1/S2/S3/S4 |
| 系統 | 計費 | `FeesComputed` | 六種 `fee_type` | `cancellation_service.py:156-188` | zero / s2_flat / travel_plus_cancel / travel_plus_inspection_plus_cancel / partial_formula |
| 系統 | 寫稽核 | `AuditEventLogged` | ADR-0102 §D 必填欄位 | `cancellation_service.py:348-374` | `audit_events` 一列，`action='cancellation.posted'` |
| 系統 | 寫取消單 + 改狀態 | `WorkOrderCancelled` | terminal 不可取消 | `cancellation_service.py:377-412` | INSERT `cancellation` + UPDATE 帶 `<> ALL` 樂觀條件 |
| 系統 | 落生命週期事件 | `WorkOrderEventInserted` | 走唯一出口取 seq | `cancellation_service.py:417-433` | `event_type='cancelled'`，payload 含 stage / fee / initiator_role |

---

## 走查紀錄

### 步驟 1 — 六個 fee_type 的定義

- **動作**：讀 `DEFAULT_CANCELLATION_CONFIG` 的型別註解與費率
- **預期**：對應 TC 列舉六類
- **實際**：一致

`api/services/cancellation_service.py:33-51`

```python
# customer_fee 計算型別：
#   zero                                  → 0
#   s2_flat                               → 取消費 (s2_cancellation_fee)
#   travel_plus_cancel                    → 車馬費 + 取消費
#   travel_plus_inspection_plus_cancel    → 車馬費 + 檢測費 + 取消費
#   partial_formula                       → 工項總額 × 完工比例 + 車馬費
DEFAULT_CANCELLATION_CONFIG: dict[str, Any] = {
    # CR-0044：S3/S4 取消費校正為 esales 已決定值（SoT 衝突業主 2026-06-19 裁決採 esales）。
    # 來源：esales『03 區域與加價規則』CNL-S2/S3/S4=300/500/800（已知規格 ADR-0102，2026-06-03，較新）。
    "version_note": "ADR-0102 / esales 03 加價規則 2026-06-03（CR-0044 業主 2026-06-19 裁決 S3=500/S4=800）",
    "fees": {
        "s2_cancellation_fee": 300,
        "s3_cancellation_fee": 500,
        "s4_cancellation_fee": 800,
        "inspection_fee": 300,
        "travel_fee_min": 500,
        "travel_fee_max": 1200,
        "travel_fee_per_km": 20,
    },
```

reason code 字典把 TC 步驟描述的六種情境各自綁到一個 stage 與 fee_type（`:56-105`）：`quote_not_confirmed`→S1/zero、`quote_confirmed_no_dispatch`→S1_5/zero、`dispatched_not_departed`→S2/s2_flat、`en_route_cancelled`→S3/travel_plus_cancel、`onsite_not_executed`→S4/travel_plus_inspection_plus_cancel、`partial_completed_cancel`→S5/partial_formula。

### 步驟 2 — 計費函式

- **動作**：讀 `compute_fees`
- **預期**：五種型別各自公式
- **實際**：一致；`partial_formula` 的 ratio 有預設值 1.0

`api/services/cancellation_service.py:169-188`

```python
    fees = cancellation_config["fees"]
    fee_type = reason_entry.get("fee_type", "zero")
    base = float(base_amount or 0.0)

    if fee_type == "zero":
        return (0.0, 0.0)
    if fee_type == "s2_flat":
        return (float(fees["s2_cancellation_fee"]), 0.0)
    if fee_type == "travel_plus_cancel":
        return (float(fees["s3_cancellation_fee"]), _travel_fee(cancellation_config, distance_km))
    if fee_type == "travel_plus_inspection_plus_cancel":
        customer = float(fees["inspection_fee"]) + float(fees["s4_cancellation_fee"])
        return (customer, _travel_fee(cancellation_config, distance_km))
    if fee_type == "partial_formula":
        ratio = 1.0 if completed_ratio is None else max(0.0, min(1.0, float(completed_ratio)))
        return (round(base * ratio, 2), _travel_fee(cancellation_config, distance_km))
```

### 步驟 3 — 編排層是否供給完工比例

- **動作**：追 `cancel_work_order_6stage` 呼叫 `compute_fees` 的實參
- **預期**：帶入完工比例
- **實際**：未帶 `completed_ratio`

`api/services/cancellation_service.py:324-330`

```python
    # 3. 推算階段 + 費用（PURE）
    stage = derive_stage(wo["status"], reason_entry)
    base_amount = wo["final_price"] if wo["final_price"] is not None else wo["estimated_price"]
    customer_fee, travel_fee = compute_fees(
        stage, reason_entry, cancellation_config,
        base_amount=base_amount, distance_km=distance_km,
    )
```

- TC 判定基準寫 S5 = 「完工比例+車馬」
- 程式碼在 pure 函式支援 ratio（`cancellation_service.py:182-184`），但編排層未傳（`:327-330`），實際套用 ratio=1.0＝工項全額+車馬（步驟 6 實測 2000 + 500）

此處僅並陳，不裁定。

檔頭亦自述此範圍限制：

`api/services/cancellation_service.py:11-13`

```python
⚠ 現行 schema 無 quote_version 表 → S1_5 / S5 的精確判定（quote.customer_confirmed
／完工項目比例）以 reason_code 字典為權威來源 + WO 狀態機 best-effort 推算。
完整 quote lifecycle 接入見 gap audit §7 波次 P3。
```

即 S1.5 與 S5 的階段判定由請求帶入的 `reason_code` 決定，非由報價狀態或完工項目比例推得。

### 步驟 4 — 缺 / 未知 reason_code

- **動作**：追兩種輸入的處理
- **預期**：皆 422
- **實際**：一致，但 error_code 不同

缺欄位：`reason_code` 在 request model 為必填（`api/models/internal.py:88-89`）

```python
    reason_code: str = Field(..., min_length=1, max_length=64,
                             description="from cancellation_reason_codes config lookup (ADR-0102 §B)")
```

pydantic 驗證失敗由全域 handler 轉為 `VALIDATION_ERROR`（`api/core/errors.py:202-216`），該 code 對應 422（`api/core/errors.py:53`：`"VALIDATION_ERROR": (422, "Validation Error")`）。

未知 code：`api/services/cancellation_service.py:125-134`

```python
def get_reason_entry(reason_code: str, cancellation_config: dict) -> dict:
    """查 reason code 字典；未知 → 422 REASON_CODE_UNKNOWN。"""
    entry = cancellation_config.get("reason_codes", {}).get(reason_code)
    if entry is None:
        raise ApiError(
            "REASON_CODE_UNKNOWN",
            f"Unknown cancellation reason_code '{reason_code}'",
            422,
        )
    return entry
```

### 步驟 5 — 稽核 payload 的欄位

- **動作**：讀寫入 `audit_events` 的 payload
- **預期**：含 stage / fee / initiator
- **實際**：stage 與 fee 有；initiator 以 `operator_id` 與 `technician_initiated` 承載，body 的 `initiator_role` 不在 payload 內

`api/services/cancellation_service.py:347-374`

```python
    # 6. audit（ADR-0102 §D 必填欄位）→ 取回 audit_event_id（cancellation.audit_event_id NOT NULL）
    audit_payload = {
        "operator_id": sod_initiator,        # SoD initiator (X-Initiator)
        "approver_id": sod_approver,         # SoD approver (X-Approver)
        "executor_id": sod_executor,         # SoD executor (X-Executor)
        "operator_role": actor_role,
        "original_amount": original_customer_fee,
        "new_amount": customer_fee,
        "delta_pct": round(delta_pct, 2),
        "reason_code": reason_code,
        "supervisor_approval_id": sod_approver if goodwill_waiver else None,
        "evidence_ids": evidence_ids or [],
        "config_version_applied": config_version,
        "cancellation_stage": stage,
        "technician_initiated": initiator_role == "technician",
        "technician_monthly_count": technician_monthly_count,
        "travel_fee": travel_fee,
        "technician_penalty": technician_penalty,
    }
    audit_event_id = await audit_log_service.log_event_returning_id(
        event_type="financial_action",
        actor_id=actor_id,
        actor_role=actor_role,
        action="cancellation.posted",
        target_type="work_order",
        target_id=wo_id,
        payload=audit_payload,
    )
```

`initiator_role` 原值落在另兩處：`cancellation` 表的 `initiator_role` 欄（`:377-389`）與 `work_order_events` payload（`:419-433`）：

```python
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_id,
        event_type="cancelled",
        payload={
            "from_status": wo["status"],
            "cancellation_stage": stage,
            "reason_code": reason_code,
            "initiator_role": initiator_role,
            "customer_fee": str(customer_fee),
            "travel_fee": str(travel_fee),
            "technician_penalty": str(technician_penalty),
            "goodwill_waiver": goodwill_waiver,
            "audit_event_id": str(audit_event_id),
        },
    )
```

- TC 判定基準寫「audit 含 stage/fee/initiator」
- 程式碼的 `audit_events.payload` 含 `cancellation_stage`、`original_amount`/`new_amount`/`travel_fee`／`technician_penalty`，發起人欄位為 `operator_id`（取自 `X-Initiator` header 字串）與 `technician_initiated`（布林）；`initiator_role` 字串本身在 `cancellation` 表與 `work_order_events` payload

此處僅並陳，不裁定。

router 註解另記載 `X-Initiator` 的可信度範圍（`api/routers/cancellation.py:54-57`）：

```python
    # ⚠️ 未修的部分：X-Initiator 仍是 client 提供的字串而非取自 token。
    # 真實身分有另外進 audit（cancellation_service 的 actor_id/actor_role），
    # 所以稽核不會被騙，但 SoD 的「發起人」欄位本身仍不可信。
```

### 步驟 6 — 執行測試與逐階段探針

- **動作**：跑取消相關三檔；另以 scratchpad 探針逐階段實跑（既有端點測試只覆蓋 S1 / S2 / S3）
- **預期**：取得六階段實際金額
- **實際**：如下表

既有測試（本機 Docker 測試庫）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cancellation_6stage.py \
  tests/test_cancellation_endpoint.py tests/test_cancel_v2_role_guard.py -q -p winloop_plugin --tb=line
33 passed in 3.73s
```

探針（**未寫入 repo**，直接呼叫 `cancel_work_order_6stage`，`estimated_price=2000`、`distance_km=None`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  <scratchpad>/test_wo12_probe.py -q -p winloop_plugin -s

status=created     code=quote_not_confirmed                    stage=S1   customer_fee=    0.00 travel_fee=    0.00
status=created     code=quote_confirmed_no_dispatch            stage=S1_5 customer_fee=    0.00 travel_fee=    0.00
status=assigned    code=dispatched_not_departed                stage=S2   customer_fee=  300.00 travel_fee=    0.00
status=accepted    code=en_route_cancelled                     stage=S3   customer_fee=  500.00 travel_fee=  500.00
status=in_progress code=onsite_not_executed                    stage=S4   customer_fee= 1100.00 travel_fee=  500.00
status=in_progress code=partial_completed_cancel               stage=S5   customer_fee= 2000.00 travel_fee=  500.00
AUDIT_PAYLOAD_KEYS= ['approver_id', 'cancellation_stage', 'config_version_applied', 'delta_pct', 'evidence_ids', 'executor_id', 'new_amount', 'operator_id', 'operator_role', 'original_amount', 'reason_code', 'supervisor_approval_id', 'technician_initiated', 'technician_monthly_count', 'travel_fee']
AUDIT_SAMPLE= {'cancellation_stage': 'S5', 'original_amount': 2000.0, 'new_amount': 2000.0, 'travel_fee': 500.0, 'reason_code': 'partial_completed_cancel', 'operator_id': 'ini-1', 'operator_role': 'admin', 'technician_initiated': False}
1 passed
```

逐條對照 TC 判定基準：

| TC 列舉 | 探針實測 | 事實 |
|---|---|---|
| S1 = 0 | customer 0 / travel 0 | 相同 |
| S1.5 = 0 | customer 0 / travel 0 | 相同；階段由 `reason_code` 指定，非由報價狀態推得 |
| S2 = 取消費 | 300 / 0 | 相同（`s2_cancellation_fee=300`） |
| S3 = 車馬+取消 | 500 / 500 | 相同（`s3_cancellation_fee=500` + `travel_fee_min=500`） |
| S4 = 車馬+檢測+取消 | 1100 / 500 | 相同（300 檢測 + 800 取消，車馬另計） |
| S5 = 完工比例+車馬 | 2000 / 500 | 工項全額（ratio 預設 1.0），未套用完工比例 |
| 缺 reason_code → 422 | — | pydantic 必填 → `VALIDATION_ERROR` 422；未知 code → `REASON_CODE_UNKNOWN` 422（`test_cancel_unknown_reason_code_422` 覆蓋） |
| audit 含 stage/fee/initiator | 見 `AUDIT_PAYLOAD_KEYS` | stage、fee（original/new/travel）有；initiator 為 `operator_id` + `technician_initiated` |

---

## 觀測到的其他事實

- `ADR-0102` 原文不在 tracked 檔案中：`git grep -rn "ADR-0102" -- smartlock-docs` 僅命中 `04_SRS.md:585`（記載「裁決 C1：ADR-0102 為正——實作為 6-stage v2」）與 `20_Test_Cases.md:269`（本 TC 自身）；ADR 本體不存在於現行文件樹（歷史 ADR 於 2026-07-08 大掃除後查 git）。
- 費用值有版本差註記：`version_note` 與 `:40-42` 註解記載 S3/S4 取消費由 300 校正為 500/800（CR-0044 業主 2026-06-19 裁決採 esales 值）。
- 車馬費為 `travel_fee_min + per_km × distance_km` 並在 `[500, 1200]` 夾擠（`cancellation_service.py:146-153`）；`distance_km` 由 client 於 body 提供（`api/models/internal.py:93`）。
- `goodwill_waiver=true` 時客戶側費用與車馬費一併歸零（`:225-229`），且 `supervisor_approval_id` 記為 `X-Approver`。
- 六階段取消端點的角色守衛為 2026-08-02 補掛（`api/routers/cancellation.py:45-58` 的註解記載原本只有 `require_tenant`，無角色檢查）。
- S5 的 base amount 取 `final_price`，無值時退回 `estimated_price`（`:326`）；兩者皆無值時 base=0。
- 本 TC 前置要求「六階段 fixture」；`api/tests/` 的既有端點測試只建立 S1 / S2 / S3 三種情境（`test_cancellation_endpoint.py:95`、`:79`、`:169`），S1.5 / S4 / S5 僅有 pure 函式層測試（`test_cancellation_6stage.py:74-114`）。
