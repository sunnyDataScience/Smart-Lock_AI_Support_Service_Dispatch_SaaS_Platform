# TC-COMPLIANCE-02 — legal_hold=true 時提 forget → 423 拒絕

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

判定理由（事實）：TC 判定基準三項中，「423 拒絕」與「audit `gdpr_forget_blocked`」兩項在程式碼中有精確落點且測試釘住（`api/services/gdpr_forget_service.py:263-274`、`api/tests/test_cr_0164_gdpr_forget.py:43-60`）；第三項「7d 內客戶通知（含預計解除時間）」的資料欄位存在（`expected_release_at`，`SQL/migrations/021-gdpr-forget-requests.sql:42`）但無任何發送通知的程式碼——`notification` / `notify` / `push_notification` 三個識別碼在 `api/services/gdpr_forget_service.py` 與 `api/routers/gdpr_forget_v2.py` 皆零命中（步驟 4），且 service docstring 自述該步驟為「業務 SOP 流程，本 service 只標 status」。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | evidence legal_hold=true 時提 forget |
| 預期結果（判定基準） | 423 拒絕 + 7d 內客戶通知（含預計解除時間）+ audit gdpr_forget_blocked |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-API-16、NFR-Comp-004、NFR-Priv-005 |
| 屬於哪條旅程腳本 | SC-19 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 偵測 subject 名下 legal_hold 證據 | `api/services/gdpr_forget_service.py:72-79` | 有落點 |
| 回 423 | `api/services/gdpr_forget_service.py:270-274`（`LEGAL_HOLD_ACTIVE`, 423） | 有落點 |
| audit `gdpr_forget_blocked` | `api/services/gdpr_forget_service.py:266-269` | 有落點 |
| 「預計解除時間」欄位存在 | `SQL/migrations/021-gdpr-forget-requests.sql:42`、`api/routers/gdpr_forget_v2.py:51` | 有落點 |
| 7d 內客戶通知 | — | **無對應**（步驟 4） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| admin | `:soft-delete`（subject 有 legal_hold media） | `ForgetBlocked(423)` | legal_hold wins | `api/services/gdpr_forget_service.py:265-274` | 先寫 audit 再拋 `LEGAL_HOLD_ACTIVE` 423 |
| 系統 | 記稽核 | `AuditAppended(gdpr_forget_blocked)` | append-only | `api/services/gdpr_forget_service.py:266-269` | `action="gdpr_forget_blocked"`，`extra={"reason": "legal_hold_active"}` |
| admin/DPO | `:legal-hold-deny` | `ForgetDeniedForLegalHold` | 僅 `received` 可轉；理由 ≥5 字元 | `api/services/gdpr_forget_service.py:210-239` | UPDATE status=`legal_hold_denied` + 寫 `expected_release_at` + audit |
| 系統 | 7 日內通知客戶 | `CustomerNotified` | NFR-Priv-005 | — | **找不到**：兩檔對 notification 相關識別碼零命中 |

---

## 逐層走查

### 步驟 1 — legal-hold 偵測條件

`api/services/gdpr_forget_service.py:72-79`：

```python
async def _has_active_legal_hold(subject_user_id: str) -> bool:
    """CR-0164 D2：subject 名下有 legal_hold=true 且未刪的 media → forget 須擋（423）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM media_files "
        "WHERE uploader_user_id = %s::uuid AND legal_hold = TRUE AND deleted_at IS NULL "
        "LIMIT 1",
        (subject_user_id,))
    return (await cur.fetchone()) is not None
```

判定條件為「以 `uploader_user_id` 關聯、`legal_hold = TRUE`、`deleted_at IS NULL`」三者同時成立。

### 步驟 2 — 423 與 audit 的先後順序

`api/services/gdpr_forget_service.py:263-274`：

```python
    # CR-0164 D2：legal-hold 前置擋——subject 名下有 legal_hold media → 423 拒絕
    # （TC-COMPLIANCE-02 P0；不再靠 admin 手動先 deny 的順序相依）。
    if await _has_active_legal_hold(subject_user_id):
        await _forget_audit(
            action="gdpr_forget_blocked", tenant_id=req["tenant_id"],
            subject_user_id=subject_user_id, actor_user_id=actor_user_id,
            request_id=request_id, extra={"reason": "legal_hold_active"})
        raise ApiError(
            "LEGAL_HOLD_ACTIVE",
            "subject 名下有 legal-hold 中的證據，forget 暫不可執行（須先解除 legal-hold）",
            423,
        )
```

該段註解直接引用本 TC 編號。audit 寫入在 raise 之前。

`LEGAL_HOLD_ACTIVE` 與 `423` 在 api 程式碼中的全部命中：

```
git grep -rn "LEGAL_HOLD_ACTIVE\|423" -- api/services api/routers api/core --include=*.py
api/services/gdpr_forget_service.py:73:    """CR-0164 D2：subject 名下有 legal_hold=true 且未刪的 media → forget 須擋（423）。"""
api/services/gdpr_forget_service.py:263:    # CR-0164 D2：legal-hold 前置擋——subject 名下有 legal_hold media → 423 拒絕
api/services/gdpr_forget_service.py:271:            "LEGAL_HOLD_ACTIVE",
api/services/gdpr_forget_service.py:273:            423,
```

### 步驟 3 — legal-hold 拒絕路徑與「預計解除時間」

`api/services/gdpr_forget_service.py:196-239` 為 `deny_legal_hold`。其 docstring（`:204-206`）：

```python
    """admin/DPO 標記 legal-hold 拒絕（received → legal_hold_denied）。

    7 天內通知客戶（業務 SOP 流程，本 service 只標 status）。
    """
```

寫入語句 `api/services/gdpr_forget_service.py:213-227` 含 `expected_release_at`：

```python
    upd = await db_module._conn.execute(
        "UPDATE saas.forget_request SET "
        "  status = 'legal_hold_denied', "
        "  legal_hold_reason = %s, "
        "  expected_release_at = %s, "
```

DB 欄位定義 `SQL/migrations/021-gdpr-forget-requests.sql:41-42`：

```sql
  legal_hold_reason   text        NULL,    -- 若 status='legal_hold_denied' 必填
  expected_release_at timestamptz NULL,    -- legal hold 預計解除時間（7d 內通知）
```

router 的 request body 模型 `api/routers/gdpr_forget_v2.py:49-51`：

```python
class LegalHoldDenyBody(BaseModel):
    legal_hold_reason: str
    expected_release_at: datetime | None = None
```

`expected_release_at` 為可選欄位（預設 `None`），service 端無非空校驗（`api/services/gdpr_forget_service.py:210-211` 只校驗 `legal_hold_reason` 長度 ≥5）。

### 步驟 4 — 通知路徑

在 GDPR forget 的兩個檔案中搜尋通知相關識別碼：

```
git grep -n "notification\|notify\|push_notification" -- \
  api/services/gdpr_forget_service.py api/routers/gdpr_forget_v2.py
（無輸出）
```

專案中確有通知服務（`api/services/notification_service.py`，被 `api/realtime/family_review_sla_cron.py:143-161` 等處使用），但未被 GDPR forget 流程引用。

TC 判定基準寫「7d 內客戶通知（含預計解除時間）」（出處：批次 A TC 原文第 20 行；需求出處 `smartlock-docs/enterprise/05_NFR.md:124` NFR-Priv-005「GDPR forget ≤ 7d 執行 OR customer notice」）／程式碼只把「預計解除時間」存入 `saas.forget_request.expected_release_at`，未見發送動作，且 service docstring 自述通知為「業務 SOP 流程」。此處僅並陳，不裁定。

### 步驟 5 — DB 層 legal_hold 欄位來源

`SQL/migrations/066-media-legal-hold.sql:7-9`：

```sql
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN media_files.legal_hold IS
  'CR-0067/TI-M09-03：法務保留旗標；true 時即使 retention_until 過期也不軟刪（legal_hold wins）';
```

設定該旗標的端點為 `api/routers/media_v2.py:207-217`（`set_media_legal_hold_v2` → `media_service.set_legal_hold`）。

### 步驟 6 — 前端呼叫端

`web/brand-portal/src/app/admin/gdpr-forget-queue/page.tsx` 為此流程的後台頁面（`git grep -l gdpr -- web/brand-portal/src` 命中該檔）。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_gdpr_forget.py tests/test_cr_0164_gdpr_forget.py \
  tests/test_gdpr_hard_delete_cron.py -p winloop_plugin -q
2 failed, 23 passed in 1.31s
```

對到本 TC 的測試 `api/tests/test_cr_0164_gdpr_forget.py:43-60`（本輪通過）：

```python
async def test_legal_hold_blocks_soft_delete_with_423_and_audit():
    """名下有 legal_hold media → soft_delete 423 + audit gdpr_forget_blocked。"""
    ...
        assert exc.value.status_code == 423
    ...
            "AND action='gdpr_forget_blocked'", (uid,))).fetchone()
        assert blk[0] >= 1, "legal-hold 擋下應寫 gdpr_forget_blocked audit"
```

該檔第 3 行的模組 docstring 亦自述覆蓋範圍：「legal-hold 前置擋（名下 legal_hold media → 423 LEGAL_HOLD_ACTIVE + audit blocked）」。

兩項失敗為 `tests/test_gdpr_forget.py::test_soft_delete_sets_eligibility_30_days` 與 `::test_hard_delete_cooldown_passed_happy`，成因見 TC-COMPLIANCE-01 之「既有測試證據」段（假 cursor 序列與現行呼叫序列不符），與本 TC 的 legal-hold 判定無關。

無測試涵蓋「7d 內客戶通知」——`api/tests/` 中 `expected_release_at` 的命中僅出現在 `test_gdpr_forget.py` 的假資料 tuple 中，無斷言通知送出。

---

## 事實結論

1. legal-hold 阻擋為 `soft_delete` 的前置檢查，早於任何 PII 覆寫（`gdpr_forget_service.py:265` 位於 `:296` 的 UPDATE 之前）。
2. HTTP 狀態碼為 423、錯誤碼為 `LEGAL_HOLD_ACTIVE`；該錯誤碼在 api 中僅此一處。
3. audit action 字面為 `gdpr_forget_blocked`，與 TC 指名字串一致，且寫入發生在拋錯之前。
4. `expected_release_at` 為 DB 欄位與 API 可選輸入，無非空校驗、無下游消費者。
5. GDPR forget 兩檔對 notification 相關識別碼零命中；service docstring 將 7 日通知標示為業務 SOP 流程。
6. `_has_active_legal_hold` 的關聯鍵為 `media_files.uploader_user_id`，未涵蓋其他以 subject 為當事人但由他人上傳的證據。
