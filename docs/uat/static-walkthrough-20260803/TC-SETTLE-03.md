# TC-SETTLE-03 — 同人送審的 SoD 阻擋

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，SoD 相關斷言（端點 403 + 純函式三組合）全數通過（見步驟 5） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/core/deps.py:246-276`、`api/services/cancellation_service.py:203-211`、`api/services/refund_service.py:551-612`、`api/routers/refunds_v2.py:36-78`、`api/routers/cancellation.py:44-70`、`api/routers/device_warranty.py:100-115`、`api/routers/config_m18.py:90-106`、`SQL/migrations/002-refund-sod-5tier.sql:60-78`、`api/tests/test_refund_sod_5tier.py:105-132`、`api/tests/test_refund_sod_endpoint.py:135-143` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | `require_sod_actors` 把三個 header 過濾掉空值後以 `len(actors) != len(set(actors))` 判重，任二相同即 403 `SOD_VIOLATION`；service 層 `check_sod` 為同一段邏輯的防禦性再驗，且 `refund_service.check_sod` 就是 `cancellation_service.check_sod` 本體（測試以 `is` 斷言）。DB 端另有兩條 CHECK 作 backstop。`SOD_VIOLATION` 這個識別碼在 `api/` 中命中 12 個非測試位置。 |

**TC 原文**｜前置：initiator == approver｜步驟：同人送審｜判定基準：403 SOD_VIOLATION（X-Initiator/Approver/Executor 任二相同即拒）｜需求：FR-API-11、FR-API-18｜旅程：SC-08、SC-11

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 同人送審（initiator==approver） | `SodViolationRejected(403)` | 任二相同即拒 | `core/deps.py:269-275` | 集合去重比長度 → 403 `SOD_VIOLATION` |
| 客服 | initiator==executor | `SodViolationRejected(403)` | 同上 | `core/deps.py:269` | 三值一起參與去重 |
| 系統 | service 層再驗 | `SodViolationRejected(403)` | 防禦性 | `services/refund_service.py:578` | 呼叫 `check_sod`（同一實作） |
| DB | 寫入 | `ConstraintViolation` | backstop | `SQL/migrations/002-refund-sod-5tier.sql:67`、`:76-77` | 兩條 CHECK |
| 客服 | 缺 header | `ValidationRejected(422)` | 必填 | `core/deps.py:265-268` | 缺 `X-Initiator` 或 `X-Approver` → 422 |

---

## 走查紀錄

### 步驟 1 — header 層的判重邏輯

- **動作**：讀 `require_sod_actors`
- **預期**：任二相同 → 403 `SOD_VIOLATION`
- **實際**：一致

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

三值先過濾空值再入集合，故 `X-Executor` 缺席時只比 initiator vs approver；三者齊備時三組配對皆被涵蓋。

### 步驟 2 — service 層的再驗

- **動作**：讀 `check_sod`
- **預期**：與 header 層同語意
- **實際**：同一份實作，退款 service 直接 re-export

`api/services/cancellation_service.py:203-211`

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

`api/services/refund_service.py:49-50`

```python
# 重用 P1-A SoD primitive（鐵律：不得自己重寫三維 SoD 邏輯）
from services.cancellation_service import check_sod  # noqa: F401  re-exported
```

呼叫點：`api/services/refund_service.py:575-578`

```python
    # 1. PURE 驗證（amount / refund_class / SoD 防禦性再驗）
    validate_amount(amount)
    validate_refund_class(refund_class)
    check_sod(sod_initiator, sod_approver, sod_executor)
```

### 步驟 3 — DB 層 backstop

- **動作**：讀 migration CHECK
- **預期**：資料層亦不可能寫入同人
- **實際**：兩條 CHECK

`SQL/migrations/002-refund-sod-5tier.sql:60-78`

```sql
    -- 三維 SoD DB 層硬約束（對齊 spec saas.refund §479-480）
    -- initiator 不得出現在 approver 陣列中
    ...
            ADD CONSTRAINT refund_requests_sod_initiator_chk
            CHECK (initiator_user_id IS NULL OR initiator_user_id <> ALL(approver_user_ids));
    ...
    -- executor 不得等於 initiator
    ...
            ADD CONSTRAINT refund_requests_sod_executor_chk
            CHECK (executor_user_id IS NULL OR initiator_user_id IS NULL
                   OR executor_user_id <> initiator_user_id);
```

同檔 `:39` 註明「CHECK 對 NULL 一律放行，不會擋舊資料」。`approver_user_ids` vs `executor_user_id` 這一組在 DB 端無對應 CHECK（僅 header／service 層涵蓋）。

### 步驟 4 — `SOD_VIOLATION` 識別碼的命中面

- **動作**：全 repo grep
- **預期**：TC 指名的錯誤碼存在
- **實際**：命中

```
git grep -n "SOD_VIOLATION" -- api | grep -v tests | grep -v openapi
api/core/deps.py:263, :272
api/routers/config_m18.py:101, :222
api/routers/disputes_v2.py:17
api/routers/reconciliations_v2.py:13
api/routers/reconciliation_exceptions_v2.py:21
api/services/cancellation_service.py:208
api/services/dispute_v2_service.py:16, :328, :363
api/services/family_review_service.py:228
api/services/notification_template_service.py:93
api/services/reconciliation_exception_service.py:306, :316
api/services/reconciliation_v2_service.py:11, :220, :265
```

掛 `require_sod_actors`（三維單次呼叫）的端點共三處：`routers/refunds_v2.py:46`、`routers/cancellation.py:59`、`routers/device_warranty.py:108`。另有兩維變體 `_require_sod_two`（`routers/config_m18.py:90-106`），以及跨兩次呼叫累積雙簽的變體（`routers/disputes_v2.py:20-22`、`routers/reconciliations_v2.py:16` 明示不使用三維守衛）。

### 步驟 5 — 執行既有測試

- **動作**：跑 SoD 測試
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_refund_sod_5tier.py \
  tests/test_refund_sod_endpoint.py tests/test_refund_dual_sign.py \
  tests/test_create_refund_request.py tests/test_refund_decision_v2_endpoint.py \
  -q -p winloop_plugin --tb=line

66 passed in 3.84s
```

端點層斷言：`api/tests/test_refund_sod_endpoint.py:135-143`

```python
async def test_create_refund_sod_violation_403(make_wo, client, admin_headers):
...
    assert res.status_code == 403
    assert res.json()["error_code"] == "SOD_VIOLATION"
```

純函式層三組合：`api/tests/test_refund_sod_5tier.py:105-132`

```python
def test_sod_initiator_equals_approver_403():
...
    assert ei.value.error_code == "SOD_VIOLATION"
    assert ei.value.status_code == 403


def test_sod_initiator_equals_executor_403():
...
def test_sod_approver_equals_executor_403():
...
def test_check_sod_is_reused_from_cancellation_service():
...
    assert rs.check_sod is cancel_check_sod
```

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:309`（FR-API-18）記載「敏感操作 `X-Initiator/X-Approver/X-Executor` 任二相同 → 403；SoD 違反 100% 阻擋」，與 TC 判定基準同源。
- `api/routers/cancellation.py:51-57` 的註解記載：`require_sod_actors` 只檢查 header 有值且相異，「兩個任意字串就過，且從不比對真實使用者身分」；`X-Initiator` 仍為 client 提供字串而非取自 token。
- `config_m18` 的兩維變體額外做 UUID 格式驗證（`routers/config_m18.py:106` 的 `_validate_uuid`），三維 `require_sod_actors` 不驗格式。
- RBAC 角色指派另有獨立錯誤碼 `SOD_VIOLATION_RBAC`（`services/role_assignment_service.py:128`），與本 TC 指名的 `SOD_VIOLATION` 為不同常數。
- `api/openapi.yaml:5399`、`:5435` 的錯誤碼 enum 同時列 `SOD_VIOLATION` 與 `SOD_VIOLATION_RBAC`。
