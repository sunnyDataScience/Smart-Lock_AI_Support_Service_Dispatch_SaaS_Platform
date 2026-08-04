# TC-SETTLE-06 — 爭議單雙簽（review → cosign）與同人連簽阻擋

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，爭議相關 2 檔（含同人連簽 403）通過（見步驟 5） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/routers/disputes_v2.py:1-296`、`api/services/dispute_v2_service.py:56-58`、`:268-402`、`SQL/migrations/006-dispute-v2.sql:22-90`、`api/tests/test_disputes_v2.py:316-386` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 兩段式雙簽完整存在：`:review` 把 `filed` 推到 `in_review`／`mediation` 並記 `reviewed_by`；`:co-sign` 從 `in_review`／`mediation` 推到 `resolved` 並記 `cosigned_by`。同人連簽由 `co_sign_dispute` 比對 `co_signer_id == reviewed_by` → 403 `SOD_VIOLATION`，DB 端另有 `CHECK (reviewed_by IS NULL OR cosigned_by IS NULL OR reviewed_by <> cosigned_by)` 作 backstop。未經 review 直接 co-sign → 409 `DUAL_SIGN_REQUIRED`。兩個行為人皆取自 `X-Initiator` header。 |

**TC 原文**｜前置：爭議單｜步驟：雙簽：review → cosign 不同人｜判定基準：resolved；同人連簽 → 403｜需求：FR-API-18｜旅程：SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| CSM | `:review` | `DisputeReviewed` | filed → in_review | `services/dispute_v2_service.py:294-312` | 非 `filed` → 409 `STATE_CONFLICT`；寫 `reviewed_by` |
| ops_manager | `:co-sign`（不同人） | `DisputeResolved` | in_review→resolved | `services/dispute_v2_service.py:376-391` | 寫 `cosigned_by` + `resolved_at`，狀態 `resolved` |
| 同一人 | `:co-sign` | `SodViolationRejected(403)` | 同人不可兩簽 | `services/dispute_v2_service.py:360-366` | 403 `SOD_VIOLATION` |
| ops_manager | 未經 review 直接 co-sign | `Rejected(409)` | 須先 review | `services/dispute_v2_service.py:353-358` | 409 `DUAL_SIGN_REQUIRED` |
| DB | 寫入 | `ConstraintViolation` | backstop | `SQL/migrations/006-dispute-v2.sql:82` | CHECK 兩簽相異 |
| 系統 | 結案留痕 | `DisputeClosed` | 稽核 | `services/dispute_v2_service.py:393-400` | `logger.info("DisputeClosed: ...")`；無 `audit_events` 寫入 |

---

## 走查紀錄

### 步驟 1 — 兩段式流程的狀態集合

- **動作**：讀允許的來源狀態
- **預期**：review 由 filed 起、co-sign 由 in_review 起
- **實際**：一致

`api/services/dispute_v2_service.py:56-58`

```python
_REVIEWABLE_FROM = {"filed"}

_COSIGNABLE_FROM = {"in_review", "mediation"}
```

router docstring 記載同樣的兩段流程（`api/routers/disputes_v2.py:13-22`）：

```
dual-sign flow（HD-3）：
  step-1  X-Initiator = CSM review         → status: filed → in_review（或 mediation）
  step-2  X-Initiator = ops_manager co-sign → status: in_review|mediation → resolved

SoD（HD-3）：co-signer（X-Initiator on :co-sign）必須 ≠ reviewed_by，否則 403 SOD_VIOLATION。
cross-tenant guard（ADR-0030）：path tenantId ≠ JWT tenant_id → 403 CROSS_TENANT_*.

注意：本模組不使用 require_sod_actors（三維 SoD）——那是 single-call 雙簽；
本流程是跨兩個 call 的累積雙簽（review 存 reviewed_by，co-sign 存 cosigned_by）。
```

### 步驟 2 — review 寫入第一簽

- **動作**：讀 `review_dispute`
- **預期**：記 `reviewed_by`
- **實際**：一致

`api/services/dispute_v2_service.py:293-312`

```python
    current_status = row[0]
    if current_status not in _REVIEWABLE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot review dispute in status '{current_status}'; expected one of {sorted(_REVIEWABLE_FROM)}",
            409,
        )

    new_status = "mediation" if to_mediation else "in_review"

    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = %s, "
        "  reviewed_by = %s::uuid, "
        "  reviewed_at = NOW(), "
        "  proposed_resolution = %s, "
        "  resolution_amount = COALESCE(%s, resolution_amount) "
        "WHERE id = %s::uuid",
        (new_status, reviewer_id, proposed_resolution, resolution_amount, dispute_id),
    )
```

`reviewer_id` 來自 router 的 `X-Initiator`（`routers/disputes_v2.py:232`、`:245`）：

```python
    initiator: str = Depends(_require_initiator),
...
        reviewer_id=initiator,
```

`_require_initiator` 缺 header → 422（`routers/disputes_v2.py:52-58`）。

### 步驟 3 — co-sign 的三個分支

- **動作**：讀 `co_sign_dispute`
- **預期**：不同人 → resolved；同人 → 403；未經 review → 409
- **實際**：三者齊備

`api/services/dispute_v2_service.py:353-391`

```python
    if current_status not in _COSIGNABLE_FROM:
        raise ApiError(
            "DUAL_SIGN_REQUIRED",
            "需先經 CSM review（status=in_review 或 mediation）才能 co-sign",
            409,
        )

    # SoD：co-signer 必須 ≠ reviewed_by（DB level CHECK 亦有 backstop）
    if reviewed_by and str(reviewed_by) == co_signer_id:
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: co-signer 不可與 reviewer 相同",
            403,
        )
...
    await db_module._conn.execute(
        "UPDATE saas.dispute SET "
        "  status = 'resolved', "
        "  cosigned_by = %s::uuid, "
        "  cosigned_at = NOW(), "
        "  resolution = %s, "
        "  resolution_amount = COALESCE(%s, resolution_amount), "
        "  resolved_at = NOW() "
        "WHERE id = %s::uuid",
```

另有 `resolution` 長度驗證（`:335-340`，< 5 字 → 422），與 body model 的 `min_length=5`（`routers/disputes_v2.py:84`）一致。

### 步驟 4 — DB backstop

- **動作**：讀 migration
- **預期**：資料層亦不可能兩簽同人
- **實際**：CHECK 存在

`SQL/migrations/006-dispute-v2.sql:82`

```sql
    CHECK (reviewed_by IS NULL OR cosigned_by IS NULL OR reviewed_by <> cosigned_by)
```

同檔 `:22` 註記約束名為 `dispute_dual_sign_distinct`；`:90` 的 COMMENT 記載流程為「step-1 reviewed_by(CSM) → step-2 cosigned_by(ops_manager) → status:resolved」。

### 步驟 5 — 執行既有測試

- **動作**：跑爭議測試
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_disputes_v2.py \
  tests/test_dispute_negative_resolution.py tests/test_cr_0070_payment_mock.py \
  -q -p winloop_plugin --tb=line

43 passed in 3.21s
```

三條判定基準的直接斷言：`api/tests/test_disputes_v2.py:320-380`

```python
async def test_co_sign_in_review_to_resolved(client):
    """co-sign：in_review → resolved（SoD 兩人相異）。"""
...
        assert data["status"] == "resolved"
...
        assert data["resolved_at"] is not None
...
async def test_co_sign_without_review_409_dual_sign_required(client):
    """co-sign 對 filed（未 review）→ 409 DUAL_SIGN_REQUIRED。"""
...
        assert resp.json()["error_code"] == "DUAL_SIGN_REQUIRED"
...
async def test_co_sign_same_person_as_reviewer_403_sod_violation(client):
    """co-sign 與 review 同一人 → 403 SOD_VIOLATION。"""
...
        headers["X-Initiator"] = CSM_USER_ID  # 與 reviewed_by 相同 → SOD_VIOLATION
...
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SOD_VIOLATION"
```

---

## 觀測到的其他事實

- 結案只寫 logger，不寫 `audit_events`：`services/dispute_v2_service.py:393-400`

  ```python
      logger.info(
          "DisputeClosed: dispute_id=%s, reviewer=%s, co_signer=%s, resolution_amount=%s",
  ```

  例外是 `resolution_amount < 0` 時走 `_emit_negative_resolution_event`（`:370-374`、`:573+`），router docstring `:24-25` 記載 DGS/refund cascade 本波次不觸發。
- `X-Initiator` 為 client 提供字串，未與呼叫者 JWT 身分比對；router 只以 `role_required(*REVIEW_ROLES, fail_closed=True)` 限制角色（`routers/disputes_v2.py:231`、`:272`）。
- 系統中有兩張爭議表：`saas.dispute`（本 TC 的 v2 雙簽流程）與 `disputes`（`payment_service.report_cash_dispute` 寫入的現金爭議，`services/payment_service.py:183-189`），兩者狀態機不同。
- `resolved` 之後可 `:reopen` 產生帶 `parent_dispute_id` 的新爭議單（`services/dispute_v2_service.py:502+`，測試 `test_disputes_v2.py:477`）。
- 逾期升級另有 cron `dispute-escalation`（daily，`realtime/job_registry.py:146-157`），對應 `_escalate_overdue_disputes`（`services/dispute_v2_service.py:634`）；開單時 `sla_deadline` 設為 `NOW() + INTERVAL '60 days'`（`:256`）。
