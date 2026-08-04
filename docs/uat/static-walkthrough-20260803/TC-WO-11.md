# TC-WO-11 — 高風險異常暫停工單（422 HIGH_RISK_HOLD）與 return_path 解除

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `test_cr_0041_exception_framework.py` 等三檔，19 項全數通過（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/exception_service.py:17-29`、`:63-102`、`:153-208`、`api/services/work_order_service.py:1764-1765`、`:2061-2076`、`:2203-2213`、`api/routers/exception_cases_v2.py:25-135`、`SQL/migrations/049-exception-framework.sql:44-48`、`api/tests/test_cr_0041_exception_framework.py:104-160` |
| 優先級 / 路徑類型 | P0 / 例外 |

TC 判定基準的兩條主線皆有落點且錯誤碼字面相符：`HIGH_RISK_HOLD` 於 `api/services/work_order_service.py:2073` 以 422 拋出，`_assert_not_high_risk_hold` 同時掛在完工（`:1765`）與派工（`:2213`）兩條路徑；`resolve` 帶 `return_path` 後若該工單已無其他 open/investigating/escalated 的 high/critical 異常，即 `UPDATE work_orders SET high_risk_hold = FALSE`（`api/services/exception_service.py:195-207`）。判為部分實作的原因在前置：TC 寫「高風險異常（safety）」，而 `exception_type` 的值域十類（`api/services/exception_service.py:18-22`）中無 `safety`；觸發 hold 的條件是 `severity ∈ {high, critical}`（`:24`、`:97-101`）而非型別名稱。此處為前置條件的識別碼落差，非判定基準本身。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 4. 工單生命週期案例（TC-WO） |
| 前置 | 高風險異常（safety）開立 |
| 步驟 | 對該工單 assign / complete |
| 預期結果（判定基準） | 422 HIGH_RISK_HOLD；resolve 帶 return_path 後解除 |
| 路徑類型 | 例外 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-API-18 |
| 屬於哪條旅程腳本 | — |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 異常型別 `safety` | `api/services/exception_service.py:18-22` 十類無 `safety`；非清單值 → 422 `VALIDATION_ERROR`（`:73-78`） | 無同名型別 |
| 「高風險」的判定依據 | `api/services/exception_service.py:24` `_HIGH_RISK = {"high", "critical"}`；`:97-101` 條件為 `severity in _HIGH_RISK and work_order_id` | 有落點（依 severity 非型別） |
| 開立即設 hold | `api/services/exception_service.py:98-101` `UPDATE work_orders SET high_risk_hold = TRUE` | 有落點 |
| assign 被擋 | `api/services/work_order_service.py:2212-2213` 呼叫 `_assert_not_high_risk_hold(wo_id)` | 有落點 |
| complete 被擋 | `api/services/work_order_service.py:1764-1765` 同上（註解自述「含 override」） | 有落點 |
| 錯誤碼 `HIGH_RISK_HOLD` | `api/services/work_order_service.py:2072-2075` | 有落點（字面相符） |
| 狀態碼 422 | `api/services/work_order_service.py:2075` | 有落點 |
| resolve 帶 `return_path` | `api/routers/exception_cases_v2.py:42`（必填欄）、`api/services/exception_service.py:167-172`（非九值 → 422） | 有落點 |
| resolve 後解除 hold | `api/services/exception_service.py:195-207` | 有落點（有條件：無其他 open high-risk） |
| DB 欄位 | `SQL/migrations/049-exception-framework.sql:44` `ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS high_risk_hold BOOLEAN NOT NULL DEFAULT FALSE` | 有落點 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台使用者 | `POST /tenants/{tid}/exception-cases`（severity=high/critical + WO） | `ExceptionOpened` ∧ `WorkOrderHeld` | BR-M15-03 | `api/routers/exception_cases_v2.py:56-58`、`api/services/exception_service.py:88-101` | 角色限 admin/ops/dispatcher/cs（`:25-27`）；INSERT 後 `high_risk_hold = TRUE` |
| 後台使用者 | severity=medium/low | `ExceptionOpened` | 不暫停 | `api/services/exception_service.py:97` | 條件不成立，不改 `high_risk_hold` |
| 派工者 | `:assign` | `RequestRejected(422)` | hold 擋派工 | `api/services/work_order_service.py:2212-2213` → `:2071-2076` | `HIGH_RISK_HOLD` 422 |
| 技師／後台 | `:complete` | `RequestRejected(422)` | hold 擋完工 | `api/services/work_order_service.py:1764-1765` → `:2071-2076` | `HIGH_RISK_HOLD` 422 |
| 後台使用者 | `:resolve` 帶 `return_path` | `ExceptionResolved` | 九值白名單 | `api/services/exception_service.py:167-172`、`:186-193` | 非白名單 → 422；否則 status=`resolved` |
| 系統 | resolve 後檢查 | `WorkOrderHoldReleased` | 無其他 open high-risk | `api/services/exception_service.py:196-207` | 查得到其他 open → 不解除；查不到 → `high_risk_hold = FALSE` |
| 後台使用者 | 重複 resolve | `RequestRejected(409)` | 已結案不可再處理 | `api/services/exception_service.py:182-183` | `STATE_CONFLICT` 409 |
| 系統 | 自動結案掃描 | （跳過 hold 單） | 不自動結案 | `api/services/work_order_service.py:4269` | `AND COALESCE(high_risk_hold, FALSE) = FALSE` |

---

## 逐層走查

### 第 1 層 — API 路由：開立與處理異常

`api/routers/exception_cases_v2.py:25-27`

```python
_resolve_roles = role_required(
    "admin", "operations_manager", "dispatcher", "customer_service"
)
```

`api/routers/exception_cases_v2.py:35-43`

```python
class _OpenExceptionRequest(BaseModel):
    exception_type: str = Field(..., description="ExceptionType 10 值之一")
    work_order_id: str | None = None
    severity: str = Field(default="medium", description="low/medium/high/critical")
    description: str | None = Field(default=None, max_length=2000)


class _ResolveExceptionRequest(BaseModel):
    return_path: str = Field(..., description="continue/requote/reschedule/reassign/new_wo/cancel/refund/rma/dispute")
```

`api/routers/exception_cases_v2.py:108-113`

```python
@router.post(
    "/tenants/{tenantId}/exception-cases/{exceptionId}:resolve",
    operation_id="resolveExceptionCase",
    summary="處理異常 v2（選 return_path；解除 high_risk_hold）",
    tags=["M15 Exception"],
)
async def resolve_exception_case(
```

檔頭另註明命名區隔（`api/routers/exception_cases_v2.py:3-4`）：「真 M15 異常 control tower（與誤命名的 `exceptions_v2.py`〔實為師傅排班〕區隔）」。

### 第 2 層 — service：型別／嚴重度值域與 hold 設定

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
_ACTIVE_STATUSES = ("open", "investigating", "escalated")
```

- TC 前置寫「高風險異常（**safety**）開立」（出處：`smartlock-docs/enterprise/20_Test_Cases.md` 之 TC-WO-11 列）
- 程式碼的 `exception_type` 十值中無 `safety`（`api/services/exception_service.py:18-22`），且 `safety` 在 `api/services` / `api/routers` / `api/models` 的命中只有兩處無關者：`audit_log_service.py:218` 的 `"safety_gate"` 事件型別映射、`problem_card_service.py:497` 的 `_VALID_EMERGENCY_CLASSES` 含 `"safety_risk"`
- 觸發 hold 的條件為 `severity ∈ {high, critical}`（`:97`），與型別名稱無關

此處僅並陳，不裁定。

`api/services/exception_service.py:96-102`

```python
    row = await cur.fetchone()
    if severity in _HIGH_RISK and work_order_id:
        await conn.execute(
            "UPDATE work_orders SET high_risk_hold = TRUE, updated_at = NOW() WHERE id = %s::uuid",
            (work_order_id,),
        )
    return _row_to_dict(row)
```

### 第 3 層 — gate：assign / complete 的攔截點

`api/services/work_order_service.py:2061-2076`

```python
async def _assert_not_high_risk_hold(wo_id: str) -> None:
    """CR-0041 BR-M15-03：high_risk_hold 旗標為 TRUE → 擋派工/完工（422）。

    工單因 high/critical 異常被暫停；須先 resolve 該異常（exception_service）解除 hold 才能繼續。
    """
    cur = await db_module._conn.execute(
        "SELECT high_risk_hold FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    if row and row[0]:
        raise ApiError(
            "HIGH_RISK_HOLD",
            "工單處於高風險暫停（high_risk_hold）；須先處理對應異常案件才能繼續（BR-M15-03）",
            422,
        )
```

派工路徑，`api/services/work_order_service.py:2203-2215`：

```python
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ASSIGN_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot assign work order in status '{current}'; expected one of {sorted(_ASSIGN_FROM)}",
            409,
        )

    # CR-0026 / BR-M05-03：派工前必填欄位 gate（缺品牌/型號/地址/問題類型 → 422）
    await _assert_dispatch_ready(wo_id)
    # CR-0041 / BR-M15-03：high_risk_hold 擋派工
    await _assert_not_high_risk_hold(wo_id)
    # CR-0095 D2：報價同意 gate（一律需 accepted 報價；主管可 override）
    await _assert_quote_accepted(wo_id, actor_role, override_reason)
```

完工路徑，`api/services/work_order_service.py:1764-1765`：

```python
    # CR-0041 / BR-M15-03：high_risk_hold 擋完工（含 override，須先 resolve 異常解除 hold）
    await _assert_not_high_risk_hold(wo_id)
```

gate 順序上，assign 先過狀態機（`:2204-2209`，非 `created`/`assigned` → 409 `STATE_CONFLICT`）與必填欄位（`:2211`），再到 `HIGH_RISK_HOLD`；complete 先過狀態機（`:1753-1759`）再到 `HIGH_RISK_HOLD`，之後才是完工硬閘（`:1766-1775`）。因此同一張單若同時違反前序條件，回的會是前序的錯誤碼。此為事實陳述，不涉判定。

### 第 4 層 — resolve 與 hold 解除

`api/services/exception_service.py:167-183`

```python
    if return_path not in _RETURN_PATHS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"return_path must be one of {sorted(_RETURN_PATHS)}",
            422,
        )
    conn = await _conn()
    cur = await conn.execute(
        "SELECT status, work_order_id FROM saas.exception_case "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid FOR UPDATE",
        (exception_id, tenant_id),
    )
    head = await cur.fetchone()
    if not head:
        raise ApiError("NOT_FOUND", "Exception not found", 404)
    if head[0] in ("resolved", "closed"):
        raise ApiError("STATE_CONFLICT", f"Exception already {head[0]}", 409)
```

`api/services/exception_service.py:195-207`

```python
    # 解除 high_risk_hold（若該 WO 已無其他 open/escalated high-risk 異常）
    if wo_id:
        chk = await conn.execute(
            "SELECT 1 FROM saas.exception_case "
            "WHERE work_order_id = %s AND severity IN ('high', 'critical') "
            "  AND status IN ('open', 'investigating', 'escalated') LIMIT 1",
            (wo_id,),
        )
        if not await chk.fetchone():
            await conn.execute(
                "UPDATE work_orders SET high_risk_hold = FALSE, updated_at = NOW() WHERE id = %s",
                (wo_id,),
            )
```

`return_path` 的語意由檔頭自述（`api/services/exception_service.py:5-6`）：「resolve：選 `return_path`（BR-M15-01 9 動作之一）；若該 WO 無其他 open high-risk 異常 → 解除 hold。`return_path` 只『記錄 + 提示』既有端點（cancel/refund/reassign 等已存在），本框架不重寫各動作（HD-1 MVP）」。即 `return_path` 為決策記錄欄，不觸發對應動作的執行。

### 第 5 層 — DB schema

`SQL/migrations/049-exception-framework.sql:44-48`

```sql
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS high_risk_hold BOOLEAN NOT NULL DEFAULT FALSE;
...
COMMENT ON COLUMN work_orders.high_risk_hold IS
```

檔頭 `SQL/migrations/049-exception-framework.sql:9` 記載設計取捨：「+ `work_orders.high_risk_hold` 旗標（HD-2：不改主狀態機，dispatch/complete gate 檢查；exception resolved 解除）」。

### 第 6 層 — 前端錯誤訊息對映

四個站台的錯誤碼字典皆有本錯誤碼：

```
web/brand-portal/src/lib/apiError.ts:72:  HIGH_RISK_HOLD: "此工單因高風險異常已被暫停，請先處理對應異常。",
web/tech-portal/src/lib/apiError.ts:75:  HIGH_RISK_HOLD: "此工單因高風險異常已被暫停，請先處理對應異常。",
web/landing/src/lib/apiError.ts:72:  HIGH_RISK_HOLD: "此工單因高風險異常已被暫停，請先處理對應異常。",
web/platform-console/src/i18n/messages/zh-TW.json:63:      "HIGH_RISK_HOLD": "此工單因高風險異常已被暫停，請先處理對應異常。",
```

---

## 既有測試證據

實跑（本機 Docker 測試庫，Windows 加 `-p winloop_plugin`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0041_exception_framework.py tests/test_cr_0153_uri_strict_guard.py \
  tests/test_cr_0131_surface_failclosed.py -q -p winloop_plugin
19 passed in 153.46s (0:02:33)
```

對到 TC 步驟與判定基準的兩項：

`api/tests/test_cr_0041_exception_framework.py:104-120`

```python
async def test_high_severity_sets_hold_and_blocks_dispatch_and_complete():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _seed_wo(wo_id, status="in_progress")
    try:
        await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="appearance_refused",
            work_order_id=wo_id, severity="high", description="安全風險",
        )
        assert await _hold(wo_id) is True  # BR-M15-03 high → hold

        # 派工/完工共用的 high_risk_hold gate 直接驗（assign_order/complete_order 皆呼此）
        with pytest.raises(ApiError) as ei:
            await wos._assert_not_high_risk_hold(wo_id)
        assert ei.value.error_code == "HIGH_RISK_HOLD"
```

該測試以 `exception_type="appearance_refused"` + `description="安全風險"` 表達「safety」情境，並直接呼叫 `_assert_not_high_risk_hold`，未經 `:assign` / `:complete` 端點。

`api/tests/test_cr_0041_exception_framework.py:126-143`

```python
async def test_resolve_clears_hold_and_records_return_path():
    ...
        exc = await es.open_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_type="quality_complaint",
            work_order_id=wo_id, severity="critical",
        )
        assert await _hold(wo_id) is True
        resolved = await es.resolve_exception(
            tenant_id=DEFAULT_TENANT_ID, exception_id=exc["id"],
            return_path="reschedule", resolution="改期重做",
        )
        assert resolved["status"] == "resolved"
        assert resolved["return_path"] == "reschedule"
        assert await _hold(wo_id) is False  # 無其他 open high-risk → 解除 hold
```

同檔另有 `test_resolve_invalid_return_path_422`（`:149-160`）與 medium 不暫停的斷言（`:95-98`）。

---

## 事實結論

1. `HIGH_RISK_HOLD` 錯誤碼在 `api` 中唯一的 raise 點為 `api/services/work_order_service.py:2072-2075`，狀態碼 422，與 TC 判定基準字面相符。
2. 該 gate 由 `_assert_not_high_risk_hold` 提供，掛在完工（`api/services/work_order_service.py:1765`）與派工（`:2213`）兩條路徑，涵蓋 TC 步驟的 assign / complete 兩者。
3. hold 的設定條件為 `severity ∈ {high, critical}` 且帶 `work_order_id`（`api/services/exception_service.py:97`），與 `exception_type` 名稱無關。
4. `exception_type` 值域十類（`api/services/exception_service.py:18-22`）中無 `safety`；TC 前置指名的 `safety` 在異常框架程式碼零命中，`safety` 一詞於 `api/services` 的其他命中為 `audit_log_service.py:218` 的 `safety_gate` 與 `problem_card_service.py:497` 的 `safety_risk`（緊急分類，非異常型別）。此處僅並陳，不裁定。
5. `resolve` 帶 `return_path` 後解除 hold 為**條件式**：需該工單再無 severity ∈ {high, critical} 且 status ∈ {open, investigating, escalated} 的異常（`api/services/exception_service.py:196-207`）。
6. `return_path` 九值白名單（`api/services/exception_service.py:25-28`），非白名單值 → 422 `VALIDATION_ERROR`（`:167-172`）；其語意由檔頭自述為「只記錄 + 提示既有端點」，不執行對應動作（`:5-6`、`:164`）。
7. `high_risk_hold` 為 `work_orders` 上的布林欄（`SQL/migrations/049-exception-framework.sql:44`），設計上刻意不改主狀態機（同檔 `:9`）。
8. 自動結案掃描亦排除 hold 單（`api/services/work_order_service.py:4269`）。
9. 既有測試在 service 層直接驗 gate 與解除，未經 `:assign` / `:complete` HTTP 端點；三檔合計 19 項於本機測試庫全數通過。
