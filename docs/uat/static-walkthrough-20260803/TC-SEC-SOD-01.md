# TC-SEC-SOD-01 — 職責分離（SoD）違反回 403

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑既有 SoD 測試，退款／月結對帳／爭議三線相關 7 檔 178 項全數通過（見步驟 5） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/core/deps.py:246-276`、`api/routers/refunds_v2.py:42-48`、`api/routers/cancellation.py:51-59`、`api/routers/device_warranty.py:108`、`api/routers/config_m18.py:91-105`、`api/routers/disputes_v2.py:52-58/268-288`、`api/routers/reconciliations_v2.py:42-48/170-176`、`api/services/reconciliation_v2_service.py:210-268`、`api/services/dispute_v2_service.py:318-366`、`api/services/cancellation_service.py:203-211`、`api/services/refund_service.py:50/555-620`、`api/services/reconciliation_exception_service.py:306-320`、`api/services/role_assignment_service.py:115-128`、`api/services/family_review_service.py:228`、`api/services/notification_template_service.py:93`、`api/routers/exceptions_v2.py:89-114`、`SQL/migrations/002-refund-sod-5tier.sql:60-72`、`SQL/migrations/005-reconciliation-v2.sql:47-49`、`SQL/migrations/006-dispute-v2.sql:80-82` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | `SOD_VIOLATION` 錯誤碼在 api 中存在且非零命中，共 6 個 service／router 落點，皆為 403。TC 前置列的三條路徑分屬兩種機制：**退款**走三維 header（`X-Initiator`／`X-Approver`／`X-Executor`，`require_sod_actors`），TC 步驟的「initiator=approver」與「initiator=executor」兩種變體皆有對應攔截；**月結對帳**與**爭議**走雙人 co-sign（單一 `X-Initiator` 對比庫中 `reviewed_by`），無 executor 維度，「initiator=executor」在該兩路徑無對應程式碼。另：TC 前置的「月結」在程式碼中有兩個可對應模組（對帳 `reconciliations_v2` 與月結批次 `monthly_settlements_v2`），後者無任何 SoD 比對，本文件並陳兩種讀法不裁定（見步驟 4）；角色指派路徑用的是另一個錯誤碼 `SOD_VIOLATION_RBAC`（`role_assignment_service.py:128`），非 TC 指名的 `SOD_VIOLATION`。 |

**TC 原文**｜前置：退款/月結/爭議｜步驟：initiator=approver 或 initiator=executor｜判定基準：403 SOD_VIOLATION｜需求：FR-API-18、NFR-Sec-003｜旅程：SC-08、SC-11

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台使用者 | 建退款，`X-Initiator` = `X-Approver` | `RequestRejected(403)` | 三維 SoD | `api/core/deps.py:269-275` | `SOD_VIOLATION`，403 |
| 後台使用者 | 建退款，`X-Initiator` = `X-Executor` | `RequestRejected(403)` | 三維 SoD | `api/core/deps.py:269-275` | `SOD_VIOLATION`，403（同一段集合比對） |
| ops_manager | 月結對帳 `:co-sign`，`X-Initiator` = 前手 reviewer | `RequestRejected(403)` | 雙人 co-sign | `api/services/reconciliation_v2_service.py:262-268` | `SOD_VIOLATION`，403 |
| ops_manager | 爭議 `:co-sign`，`X-Initiator` = 前手 reviewer | `RequestRejected(403)` | 雙人 co-sign | `api/services/dispute_v2_service.py:360-366` | `SOD_VIOLATION`，403 |
| ops_manager | 月結對帳／爭議，`X-Executor` 帶入 | — | — | — | **找不到**：該兩路徑的 header 依賴只解析 `X-Initiator` |
| DB | 寫入雙簽欄位 | `ConstraintViolated` | DB 層 backstop | `SQL/migrations/005-reconciliation-v2.sql:47-49`、`006-dispute-v2.sql:80-82`、`002-refund-sod-5tier.sql:60-72` | CHECK constraint 三處 |

---

## 走查紀錄

### 步驟 1 — `SOD_VIOLATION` 錯誤碼是否存在、在哪裡

- **動作**：全 repo grep TC 指名的識別碼
- **預期**：非零命中
- **實際**：非零命中；api 程式碼（排除文件／CHANGELOG／openapi）共 6 個 raise 點

```
git grep -rn "SOD_VIOLATION" -- api/core api/routers api/services
api/core/deps.py:263:    X-Executor optional。任二相同 → 403 SOD_VIOLATION。
api/core/deps.py:272:            "SOD_VIOLATION",
api/routers/config_m18.py:101:            "SOD_VIOLATION",
api/services/cancellation_service.py:208:            "SOD_VIOLATION",
api/services/dispute_v2_service.py:363:            "SOD_VIOLATION",
api/services/family_review_service.py:228:            "SOD_VIOLATION",
api/services/notification_template_service.py:93: raise ApiError("SOD_VIOLATION", ...)
api/services/reconciliation_exception_service.py:316:            "SOD_VIOLATION",
api/services/reconciliation_v2_service.py:265:            "SOD_VIOLATION",
api/services/role_assignment_service.py:128: ... "SOD_VIOLATION_RBAC" ...
```

`role_assignment_service.py:128` 用的是 `SOD_VIOLATION_RBAC`，字面與 TC 指名的 `SOD_VIOLATION` 不同：

```python
        raise ApiError("SOD_VIOLATION_RBAC", "approver must differ from proposer (SoD)", 403)
```

### 步驟 2 — 三維 SoD 的判定邏輯（TC 步驟的兩種變體）

- **動作**：讀 `require_sod_actors`
- **預期**：initiator=approver 與 initiator=executor 皆 403
- **實際**：以集合去重長度比對，兩種變體同一段程式碼攔截

`api/core/deps.py:255-276`

```python
async def require_sod_actors(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
    x_executor: str | None = Header(default=None, alias="X-Executor"),
) -> SodActors:
    """解析 X-Initiator / X-Approver / X-Executor headers。

    spec（openapi-smart-lock-saas.yaml）: X-Initiator + X-Approver required，
    X-Executor optional。任二相同 → 403 SOD_VIOLATION。
    """
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    if not x_approver:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Approver", 422)
    actors = [a for a in (x_initiator, x_approver, x_executor) if a]
    if len(actors) != len(set(actors)):
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: X-Initiator / X-Approver / X-Executor must be distinct",
            403,
        )
    return SodActors(initiator=x_initiator, approver=x_approver, executor=x_executor)
```

同型的純函式版本在 `api/services/cancellation_service.py:203-211`：

```python
def check_sod(initiator: str | None, approver: str | None, executor: str | None = None) -> None:
    """SoD 三維（BR-M17-01 / ADR-0102 §D）：initiator / approver / executor 任二相同 → 403。"""
    actors = [a for a in (initiator, approver, executor) if a]
    if len(actors) != len(set(actors)):
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: initiator / approver / executor must be distinct",
            403,
        )
```

掛上 `require_sod_actors` 的端點共三個 router：

```
git grep -n "Depends(require_sod_actors)" -- api/routers
api/routers/cancellation.py:59
api/routers/device_warranty.py:108
api/routers/refunds_v2.py:46
```

TC 前置的「退款」對應 `api/routers/refunds_v2.py:42-48`：

```python
async def create_refund_sod(
    body: RefundSodRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

退款路徑在 service 層還有第二道同一函式的再驗，`api/services/refund_service.py:576-578`：

```python
    # 1. PURE 驗證（amount / refund_class / SoD 防禦性再驗）
    validate_amount(amount)
    validate_refund_class(refund_class)
    check_sod(sod_initiator, sod_approver, sod_executor)
```

該 `check_sod` 由 `api/services/refund_service.py:50` 自 `cancellation_service` re-export，即與步驟 2 引用的三維集合比對為同一份實作；其 docstring（`refund_service.py:570`）自述為「check_sod 防禦性再驗」。因此退款路徑上「initiator=approver」與「initiator=executor」各有 router 層（`deps.py:270-275`）、service 層（`refund_service.py:578`）、DB 層（`SQL/migrations/002-refund-sod-5tier.sql:60-72`）三處攔截。

### 步驟 3 — 月結對帳與爭議：雙人 co-sign，無 executor 維度

- **動作**：讀 `:co-sign` 路徑的 header 依賴與 service 判定
- **預期**：三維比對
- **實際**：只解析 `X-Initiator` 一個 header，與庫中 `reviewed_by` 一維比對

`api/routers/reconciliations_v2.py:42-48`（`disputes_v2.py:52-58` 為同型）

```python
async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    """X-Initiator header required（CSM on review、ops_manager on co-sign）。"""
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return x_initiator
```

`api/services/reconciliation_v2_service.py:262-268`

```python
        # SoD：co-signer 必須 ≠ reviewer
        if reviewed_by and str(reviewed_by) == co_signer_id:
            raise ApiError(
                "SOD_VIOLATION",
                "Separation of Duties violated: co-signer 不可與 reviewer 相同",
                403,
            )
```

`api/services/dispute_v2_service.py:360-366`

```python
    # SoD：co-signer 必須 ≠ reviewed_by（DB level CHECK 亦有 backstop）
    if reviewed_by and str(reviewed_by) == co_signer_id:
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: co-signer 不可與 reviewer 相同",
            403,
        )
```

兩檔的模組 docstring 均自述不使用三維：`api/routers/disputes_v2.py:20`、`api/routers/reconciliations_v2.py:16` 皆為「注意：本模組不使用 require_sod_actors（三維 SoD）——那是 single-call 雙簽」。

TC 步驟寫「initiator=approver **或** initiator=executor」（出處：`smartlock-docs/enterprise/20_Test_Cases.md` 之 TC-SEC-SOD-01 列）／程式碼在月結對帳與爭議路徑只實作 initiator vs reviewer 一維，`X-Executor` 在 `api/routers/reconciliations_v2.py`、`api/routers/disputes_v2.py` 全檔零命中。此處僅並陳，不裁定。

### 步驟 4 — 逐條件比對

- **動作**：把 TC 前置×步驟的組合對到程式碼
- **預期**：六格皆有落點
- **實際**：

| 前置 | initiator=approver | initiator=executor | 錯誤碼 |
|---|---|---|---|
| 退款（`POST /tenants/{id}/refunds`） | 有（`deps.py:270-275` + `refund_service.py:578`） | 有（同段集合比對，同兩處） | `SOD_VIOLATION` 403 |
| 月結——讀法 A：對帳（`reconciliations/{id}:co-sign`） | 有（`reconciliation_v2_service.py:263`） | **無對應**（無 executor 維度） | `SOD_VIOLATION` 403 |
| 月結——讀法 B：月結批次（`monthly_settlements_v2.py`） | **無對應** | **無對應** | 無 |
| 爭議（`disputes/{id}:co-sign`） | 有（`dispute_v2_service.py:361`） | **無對應**（無 executor 維度） | `SOD_VIOLATION` 403 |

TC 前置只寫「月結」，程式碼中有兩個模組可對應，兩者的 SoD 狀況不同：

- **讀法 A — 對帳**：`api/routers/reconciliations_v2.py`。模組 docstring（`:10-18`）描述 CSM review → ops_manager co-sign 兩段式流程，co-sign 時 `approved_by ≠ reviewed_by`，違反回 403 `SOD_VIOLATION`。該檔自述「本模組不使用 `require_sod_actors`（三維 SoD）——那是 single-call 雙簽；本流程是跨兩個 call 的累積雙簽」（`:16-18`）。
- **讀法 B — 月結批次**：`api/routers/monthly_settlements_v2.py`，該檔自述端點為「觸發月結批次」（`:74`）、「取月結 batch summary」（`:105`）、「下載月結 CSV」（`:124`）——字面上是「月結」。其權限依賴為 `role_required(*OPS_ROLES)` 與 `_require_initiator`（`:81-82`、`:156-157`），無任何兩造相異比對；`SOD_VIOLATION` / `require_sod_actors` / `check_sod` 三個識別碼在該檔與 `settlements_v2.py`、`settlement_service.py` 皆零命中（grep 證據見「觀測到的其他事實」）。

TC 未指明「月結」為何者，本文件並陳兩種讀法。此處僅並陳，不裁定。

DB 層另有三處 CHECK backstop：

`SQL/migrations/002-refund-sod-5tier.sql:60-67`

```sql
    -- 三維 SoD DB 層硬約束（對齊 spec saas.refund §479-480）
    -- initiator 不得出現在 approver 陣列中
        ALTER TABLE refund_requests
            ADD CONSTRAINT refund_requests_sod_initiator_chk
            CHECK (initiator_user_id IS NULL OR initiator_user_id <> ALL(approver_user_ids));
```

`SQL/migrations/005-reconciliation-v2.sql:47-49`

```sql
  -- DB 層 SoD backstop：兩個 signer 非 NULL 時必須相異
  CONSTRAINT recon_dual_sign_distinct
    CHECK (reviewed_by IS NULL OR approved_by IS NULL OR reviewed_by <> approved_by)
```

`SQL/migrations/006-dispute-v2.sql:80-82` 為同型（`dispute_dual_sign_distinct`，比對 `reviewed_by` 與 `cosigned_by`）。

### 步驟 5 — 執行既有測試

- **動作**：跑與 SoD 相關的既有測試
- **預期**：取得執行證據
- **實際**：三批合計 178 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0071_rbac_sod.py tests/test_cr_0143_role_assignment_api.py \
  tests/test_cancellation_6stage.py tests/test_cancellation_endpoint.py \
  tests/test_config_m18.py tests/test_cr_0079_sop_dual_review.py \
  tests/test_cancel_v2_role_guard.py -q -p winloop_plugin
73 passed in 5.63s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_refund_sod_endpoint.py tests/test_refund_sod_5tier.py \
  tests/test_refund_dual_sign.py -q -p winloop_plugin
53 passed in 3.67s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_reconciliations_v2.py tests/test_disputes_v2.py -q -p winloop_plugin
52 passed in 3.45s
```

對到 TC 步驟兩變體的測試：

- initiator=approver（退款端點）：`api/tests/test_refund_sod_endpoint.py:135-143`

```python
async def test_create_refund_sod_violation_403(make_wo, client, admin_headers):
    wo_id = await make_wo()
    res = await client.post(
        _path(),
        headers=_sod_headers(admin_headers, initiator=_SAME_UID, approver=_SAME_UID),
        json={"work_order_id": wo_id, "amount": 8000, "refund_class": "product", "reason": "x"},
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "SOD_VIOLATION"
```

- initiator=executor：`api/tests/test_cancellation_6stage.py:160-163`（取消服務的純函式層，非退款端點）

```python
def test_sod_executor_collision_403():
    with pytest.raises(ApiError) as ei:
        cs.check_sod("user-a", "user-b", "user-a")
    assert ei.value.error_code == "SOD_VIOLATION"
```

- 月結對帳／爭議 co-sign：`api/tests/test_reconciliations_v2.py:332-344`、`api/tests/test_disputes_v2.py:367-380`，兩者皆以「`X-Initiator` 設為與 `reviewed_by` 相同」斷言 403 `SOD_VIOLATION`。

---

## 觀測到的其他事實

- `require_sod_actors` 比對的是 client 可控的 header 字串，不與 JWT 身分（`user_id`）比對。此行為由 `api/tests/test_cancel_v2_role_guard.py:79-93` 明文釘住：

```python
def test_sod_actors_alone_is_not_an_authorization_check():
    """釘住「為什麼 require_sod_actors 不算守衛」。

    它只驗兩個 header 有值且相異，是 client 可控字串，不比對真實身分。
    """
    ...
    assert "user_id" not in body, (
        "require_sod_actors 現在會比對 user_id 了？"
```

- `api/routers/cancellation.py:51-52` 檔內註解自述同一件事：「require_sod_actors 擋不住：它只檢查 X-Initiator / X-Approver 有值且彼此相異」。
- FR-API-18 原文（`smartlock-docs/enterprise/04_SRS.md:309`）為「例外案件（reschedule / exception_case / dispute）集中收件匣；敏感操作 `X-Initiator/X-Approver/X-Executor` 任二相同 → 403」。例外收件匣核准端點 `api/routers/exceptions_v2.py:95-101` 的依賴為 `_admin_only` + `idempotency_guard`，無 SoD header 依賴：

```python
async def approve_exception(
    body: ExceptionDecision,
    tenantId: str = Path(...),
    exceptionId: str = Path(...),
    user: CurrentUser = Depends(_admin_only),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

- 月結批次端點（`api/routers/monthly_settlements_v2.py`、`api/routers/settlements_v2.py`、`api/services/settlement_service.py`）對 `SOD_VIOLATION` / `require_sod_actors` / `check_sod` 三個識別碼皆零命中：

```
git grep -c "SOD_VIOLATION\|require_sod_actors\|check_sod" -- \
  api/routers/monthly_settlements_v2.py api/routers/settlements_v2.py \
  api/services/settlement_service.py
（無輸出，exit=1）
```

- `api/routers/config_m18.py:91-105` 另有一份二維版本 `_require_sod_two`（只比 `X-Initiator` vs `X-Approver`），與 `deps.py` 的三維版本並存。
- 其餘三處 `SOD_VIOLATION` 落點與 TC 前置無關：`family_review_service.py:228`（SOP 家族覆核四眼）、`notification_template_service.py:93`（模板 creator 不可自核）、`reconciliation_exception_service.py:316`（對帳異常修正雙簽）。
