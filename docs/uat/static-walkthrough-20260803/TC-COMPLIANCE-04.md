# TC-COMPLIANCE-04 — 保存期到期 cron（過期軟刪、RMA +3y、legal-hold 永久不刪）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

判定理由（事實）：TC 判定基準三項在程式碼中皆有對應落點且皆有既有測試覆蓋——過期軟刪（`api/services/media_service.py:117-132`）、list 排除軟刪（`api/services/media_service.py:312`）、RMA/保固 +3 年（`api/services/media_service.py:216-226`）、legal-hold 不刪（`api/services/media_service.py:129`）。實跑相關 4 個測試檔 18 項全過。另觀測到 cron 檔頭註解與 migration 048 backfill 寫「2 年」，與現行程式碼的 3 年並存（步驟 6，僅並陳）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | 保存期到期 cron |
| 預期結果（判定基準） | 過期 media 軟刪且 list 排除；RMA +3y / legal-hold 永久不刪 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | FR-API-16、NFR-Comp-004、NFR-Priv-008 |
| 屬於哪條旅程腳本 | SC-19 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 保存期 cron 存在且每日跑 | `api/realtime/media_retention_cron.py:18`、`api/realtime/job_registry.py:206-217` | 有落點 |
| 過期 media 軟刪（標 `deleted_at`） | `api/services/media_service.py:123-131` | 有落點 |
| list 排除軟刪 | `api/services/media_service.py:312`、`:276`、`:352` | 有落點 |
| RMA（客訴）+3y | `api/services/media_service.py:216` | 有落點 |
| 保固工單 +3y | `api/services/media_service.py:217-226` | 有落點 |
| legal-hold 永久不刪 | `api/services/media_service.py:129`、`SQL/migrations/066-media-legal-hold.sql:7` | 有落點 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 上傳者 | 上傳證據 | `MediaUploaded(retention_until)` | 一般 1y / 客訴・保固 3y | `api/services/media_service.py:213-226` | `ret_years = 3 if purpose.startswith("dispute_evidence") else 1`；`service_category IN ('warranty_in','warranty_out')` 亦升 3 |
| 系統 cron | 每日掃過期 | `MediaSoftDeleted` | `retention_until < NOW()` 且未軟刪 | `api/services/media_service.py:123-131` | UPDATE `deleted_at = NOW()`，回筆數 |
| 系統 cron | 掃到 legal_hold 列 | （不應軟刪） | legal_hold wins | `api/services/media_service.py:129` | WHERE 子句含 `AND legal_hold IS NOT TRUE` |
| 後台使用者 | 列工單媒體 | `MediaListed(excluding deleted)` | 排除軟刪 | `api/services/media_service.py:312` | `AND deleted_at IS NULL` |
| admin | 設定 legal_hold | `LegalHoldSet` | 手動；寫稽核 | `api/services/media_service.py:338-364`、`api/routers/media_v2.py:207-217` | UPDATE + audit |

---

## 逐層走查

### 步驟 1 — cron 層

`api/realtime/media_retention_cron.py:1-6`：

```python
"""Media Retention Cron — CR-0040 BR-M09-03：每日軟刪過期 evidence。

cron 每日掃一次 media_files.retention_until < NOW 且未軟刪者 → 標 deleted_at
（HD-4 軟刪，可復原 + audit）。走 media_service 確保邏輯一致。
保存期：一般 1 年、客訴/保固 2 年（Q027；於 upload 時依 purpose/WO 算入 retention_until）。
"""
```

間隔常數 `api/realtime/media_retention_cron.py:18`：

```python
DEFAULT_INTERVAL_S = int(os.getenv("MEDIA_RETENTION_INTERVAL", str(24 * 60 * 60)))  # 1 day
```

cron 主體只做一件事，`api/realtime/media_retention_cron.py:80`：

```python
        return await media_service.soft_delete_expired_media()
```

該 worker 於 job registry 登記，`api/realtime/job_registry.py:206-217`：

```python
    _job(
        "media-retention",
        "realtime.media_retention_cron:worker",
        kind="scheduled",
        schedule="daily",
        scope="brand.media_files retention",
        idempotency="deleted_at IS NULL predicate",
        timeout=900,
        retry="Scheduler retry",
        compensation="soft-delete can be restored by governed workflow",
        run_once="run_once",
    ),
```

registry 的執行入口為 `api/main.py:183`（`runtime_manager`）與 `api/worker_main.py:39`（`run_job_once`）。

### 步驟 2 — service 層：軟刪語句與 legal-hold 排除

`api/services/media_service.py:117-132`：

```python
async def soft_delete_expired_media() -> int:
    """CR-0040 清除 cron（HD-4 軟刪）：retention_until 過期且未軟刪的 media 標 deleted_at。回筆數。

    CR-0067 / TI-M09-03：legal_hold=true（法務保留）即使過期也不刪（legal_hold wins）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "UPDATE media_files SET deleted_at = NOW() "
        "WHERE retention_until IS NOT NULL AND retention_until < NOW() "
        "  AND deleted_at IS NULL "
        "  AND legal_hold IS NOT TRUE "
        "RETURNING id"
    )
    rows = await cur.fetchall()
    return len(rows)
```

四個 WHERE 條件分別對應：保存期已設、已過期、尚未軟刪、非法務保留。

### 步驟 3 — service 層：保存期計算（RMA +3y）

`api/services/media_service.py:213-226`：

```python
    # 保存期：RMA 證據（客訴 dispute / 保固 warranty WO）3 年；其餘 1 年。
    # CR-0164 F#6（衝突②裁定）：NFR-Priv-003/Aud-003（合約下限）+ R-F4 紅線＝RMA +3 年
    # 為正典，推翻 Q027 的 2 年（Q027 無文件出處）。
    ret_years = 3 if purpose.startswith("dispute_evidence") else 1
    if ret_years == 1 and work_order_id:
        wcur = await db_module._conn.execute(
            "SELECT 1 FROM work_orders WHERE id = %s::uuid "
            "  AND service_category IN ('warranty_in', 'warranty_out')",
            (work_order_id,),
        )
        if await wcur.fetchone():
            ret_years = 3
```

觸發 3 年的兩條路徑：`purpose` 以 `dispute_evidence` 開頭（涵蓋 `_ALLOWED_PURPOSES` 中的 `dispute_evidence_customer` / `dispute_evidence_technician`，見 `api/services/media_service.py:38-39`），或工單 `service_category` 為 `warranty_in` / `warranty_out`。

需求出處：`smartlock-docs/enterprise/05_NFR.md:122`（NFR-Priv-003「RMA / 客訴 retention +3y，合約下限」）、同檔 `:162`（NFR-Aud-003「1y / RMA+3y / eternal / GDPR ≤ 7d」）。

### 步驟 4 — service 層：list 排除軟刪

`api/services/media_service.py:302-317`：

```python
async def list_media_for_work_order(
    *, tenant_id: str, work_order_id: str, role: str | None = None
) -> dict:
    """列工單媒體。CR-0040：依角色過濾不可見 purpose（品牌不看環境照）+ 排除軟刪。"""
    ...
    sql = (
        "SELECT id, purpose, filename, content_type, size_bytes, created_at, legal_hold "
        "FROM media_files "
        "WHERE work_order_id = %s::uuid AND tenant_id = %s::uuid "
        "  AND deleted_at IS NULL "
    )
```

`deleted_at IS NULL` 在 media service 中的全部命中：

```
git grep -n "deleted_at IS NULL" -- api/services/media_service.py
api/services/media_service.py:127:        "  AND deleted_at IS NULL "
api/services/media_service.py:211:        "  AND deleted_at IS NULL LIMIT 1",
api/services/media_service.py:276:        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL",
api/services/media_service.py:312:        "  AND deleted_at IS NULL "
api/services/media_service.py:352:        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL",
```

即 list（`:312`）、單檔取用（`:276`）、去重查詢（`:211`）、legal_hold 設定（`:352`）皆排除軟刪列。

### 步驟 5 — DB schema 層

`SQL/migrations/048-media-evidence-governance.sql:12-13`：

```sql
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ;
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS deleted_at      TIMESTAMPTZ;
```

`SQL/migrations/066-media-legal-hold.sql:7-9`：

```sql
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN media_files.legal_hold IS
  'CR-0067/TI-M09-03：法務保留旗標；true 時即使 retention_until 過期也不軟刪（legal_hold wins）';
```

掃描用 partial index `SQL/migrations/048-media-evidence-governance.sql:23-25`：

```sql
CREATE INDEX IF NOT EXISTS idx_media_files_retention
    ON media_files (retention_until)
    WHERE deleted_at IS NULL;
```

### 步驟 6 — 保存年限的兩種數字並存

現行程式碼為 3 年（`api/services/media_service.py:213-226`）。以下三處仍寫 2 年：

- `api/realtime/media_retention_cron.py:5`：「保存期：一般 1 年、客訴/保固 2 年（Q027；...）」
- `SQL/migrations/048-media-evidence-governance.sql:16-20` 的 backfill：
  ```sql
  UPDATE media_files
  SET retention_until = created_at + (
          CASE WHEN purpose LIKE 'dispute_evidence%' THEN INTERVAL '2 years'
               ELSE INTERVAL '1 year' END)
  WHERE retention_until IS NULL;
  ```
- `SQL/migrations/048-media-evidence-governance.sql:27-28` 的 COMMENT：「保存期到期日（一般 1 年、客訴/保固 2 年，Q027）」

`api/services/media_service.py:214-215` 的註解自述該差異來源：「CR-0164 F#6（衝突②裁定）：NFR-Priv-003/Aud-003（合約下限）+ R-F4 紅線＝RMA +3 年為正典，推翻 Q027 的 2 年」。

TC 判定基準寫「RMA +3y」（出處：批次 A TC 原文第 44 行）／新上傳走 3 年（`media_service.py:216`），migration 048 對存量列 backfill 為 2 年（`048-media-evidence-governance.sql:18`）。此處僅並陳，不裁定。

### 步驟 7 — legal_hold 設定端點與前端

`api/routers/media_v2.py:207-217`：

```python
async def set_media_legal_hold_v2(
    ...
    return await media_service.set_legal_hold(
```

`api/services/media_service.py:338-345`：

```python
async def set_legal_hold(
    *, tenant_id: str, media_id: str, hold: bool,
    reason: str | None = None, actor_id: str | None = None, actor_role: str | None = None,
) -> dict:
    """CR-0109：手動設定/解除媒體法務保留（legal_hold）。

    legal_hold=true → retention cron 不軟刪（爭議/保固/訴訟期間鎖證據，legal_hold wins）。
    手動 admin/主管操作（自動觸發/解除規則待業主定義，本輪僅手動）。寫稽核軌跡。
    """
```

list 回傳項目帶 `legal_hold` 旗標供前端顯示，`api/services/media_service.py:332`：

```python
            "legal_hold": bool(r[6]),  # CR-0109：法務保留旗標（true=不被 retention cron 清）
```

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0040_evidence_governance.py tests/test_cr_0067_coverage_batch5.py \
  tests/test_cr_0109_legal_hold.py tests/test_cr_0164_rma_retention_3y.py \
  -p winloop_plugin -q
18 passed in 4.93s
```

分別對到：

- 過期軟刪：`api/tests/test_cr_0040_evidence_governance.py:115-125`（插一筆 `retention_until` 在過去 → 呼 `soft_delete_expired_media`）
- legal-hold 不刪：`api/tests/test_cr_0067_coverage_batch5.py:74-82`（兩筆皆過期，a 無 legal_hold、b 有）
- legal_hold 端點：`api/tests/test_cr_0109_legal_hold.py:40`（含 `retention_until, legal_hold` 欄位插入）
- RMA +3y：`api/tests/test_cr_0164_rma_retention_3y.py:27`
  ```python
        "SELECT EXTRACT(YEAR FROM AGE(retention_until, created_at)) "
  ```

---

## 事實結論

1. 保存期軟刪由單一 SQL 語句完成，四個 WHERE 條件同時涵蓋「已過期」「未軟刪」「非 legal-hold」（`media_service.py:125-130`）。
2. legal-hold 為布林欄位、DB 預設 `false`，僅由手動端點設定（`media_v2.py:207`），無自動解除規則。
3. RMA 3 年由兩條件觸發：`purpose` 前綴 `dispute_evidence`、或工單 `service_category` 為保固類。
4. media service 的 5 個查詢語句全部帶 `deleted_at IS NULL`，軟刪後不出現在 list、單檔取用與去重路徑。
5. cron 每日執行、經 job registry 登記（`job_registry.py:206-217`），逾時 900 秒、標示為可重跑（`idempotency="deleted_at IS NULL predicate"`）。
6. 「2 年」與「3 年」兩個數字同時存在於 repo：程式碼為 3 年，cron docstring 與 migration 048 的 backfill/COMMENT 為 2 年。
