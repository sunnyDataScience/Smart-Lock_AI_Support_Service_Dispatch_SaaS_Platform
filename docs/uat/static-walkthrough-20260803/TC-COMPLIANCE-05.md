# TC-COMPLIANCE-05 — SOP draft 未經 family review 直接 adopt 必須失敗

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

判定理由（事實）：TC 判定基準三項中，「必須失敗」在 service 層有硬 gate（`api/services/sop_draft_service.py:405-417`，回 425 `FAMILY_REVIEW_REQUIRED`），v1／v2 兩條 adopt 路由都經過同一函式；「reviewer 缺席 >24h → 升級」有專屬 cron（`api/realtime/family_review_sla_cron.py:89-140`，寫 audit `sop.family_review_overdue` + 通知管理層）。「覆核率 100%」的報表在程式碼中無對應——`family_reviews` 於 `api/services/sop_performance_service.py` 零命中，該檔的 `approval_rate_pct` 算的是 `sop_drafts.status` 的 admin 初審通過率（步驟 5）；「暫停 publish」亦無獨立機制，SLA cron 只寫 audit 與通知，不改任何狀態或旗標（步驟 4）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | SOP draft 未經 family review 直接 adopt |
| 預期結果（判定基準） | 必須失敗；覆核率 100%；reviewer 缺席 >24h → 升級 + 暫停 publish |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-REF-03、FR-REF-05、NFR-Aud-004、NFR-Comp-002 |
| 屬於哪條旅程腳本 | SC-16 |

需求原文（`smartlock-docs/enterprise/05_NFR.md:163`）：「NFR-Aud-004｜Family Reviewer 紀錄｜100% 覆核、不可篡改、SLA ≤ 24h｜覆核率報表 + hash chain（`family_reviews`）｜合約下限」。
同檔 `:214`：「NFR-Comp-002｜合約 4.4(d) 家族覆核｜覆核率 100%｜覆核報表｜合約下限」。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 未覆核直接 adopt → 失敗 | `api/services/sop_draft_service.py:405-417` | 有落點（425 `FAMILY_REVIEW_REQUIRED`） |
| 判「approved 的覆核」而非「有覆核」 | `api/services/sop_draft_service.py:408-411`（`action = 'approved'`） | 有落點 |
| 覆核者 ≠ 初審 admin（四眼） | `api/services/family_review_service.py:221-228` | 有落點（403 `SOD_VIOLATION`） |
| ledger 不可篡改（hash chain） | `api/services/family_review_service.py:27-66`、`SQL/migrations/074-family-review-ledger.sql:8-9` | 有落點 |
| reviewer 缺席 >24h → 升級 | `api/realtime/family_review_sla_cron.py:93-140` | 有落點 |
| 缺席 >24h → 暫停 publish | — | **無對應**（步驟 4） |
| 覆核率 100% 報表 | — | **無對應**（步驟 5） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台審核者 | adopt（無家族覆核） | `AdoptRejected(425)` | 合約 4.4(d) 硬 gate | `api/services/sop_draft_service.py:408-417` | 查 `family_reviews` 有無 `action='approved'`，無則 425 |
| 後台審核者 | adopt（覆核為 rejected） | `AdoptRejected(425)` | 只認 approved | `api/services/sop_draft_service.py:409-410` | WHERE 帶 `action = 'approved'` |
| 家族覆核者 | 建覆核（自己就是初審 admin） | `RequestRejected(403)` | 四眼 | `api/services/family_review_service.py:224-228` | `SOD_VIOLATION` 403 |
| 家族覆核者 | 建覆核 | `FamilyReviewAppended(hash)` | 不可篡改 ledger | `api/services/family_review_service.py:234-252` | advisory lock + prev_hash/entry_hash 寫入 |
| 系統 cron | 每小時掃逾 24h 未審 | `FamilyReviewOverdue` | SLA 24h | `api/realtime/family_review_sla_cron.py:93-135` | 寫 audit `sop.family_review_overdue` + 通知 |
| 系統 cron | 逾時後暫停該租戶 publish | `PublishSuspended` | BR-SOP-002 | — | **找不到**：cron 不改任何狀態欄位或旗標 |
| 營運 | 查覆核率報表 | `ReviewRateReported` | 覆核率 100% | — | **找不到**：`family_reviews` 於報表 service 零命中 |

---

## 逐層走查

### 步驟 1 — API 路由層：兩條 adopt 路由

v1，`api/routers/sop_drafts.py:129-149`：

```python
@router.post(
    "/sop-drafts/{id}/adopt",
    operation_id="adoptSopDraft",
    summary="採納 SOP 草稿（核准後入庫成為案例）",
    response_model=CaseEntryEnvelope,
)
async def adopt_sop_draft(
    body: SopDraftAdoptRequest | None = None,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    ...
    case = await sop_draft_service.adopt_draft(
```

v2，`api/routers/sops_v2.py:400-419`：

```python
@router.post(
    "/tenants/{tenantId}/sops/drafts/{draftId}/adopt",
    operation_id="adoptSopDraftV2",
    ...
    case = await sop_draft_service.adopt_draft(
```

兩者的守衛皆為 `role_required(*REVIEW_ROLES)` + `idempotency_guard`，且都收斂到同一個 service 函式 `sop_draft_service.adopt_draft`。

### 步驟 2 — service 層：家族覆核硬 gate

`api/services/sop_draft_service.py:396-417`：

```python
    current_status = (row[0] or "").lower()
    if current_status != "approved":
        raise ApiError(
            "CONFLICT",
            f"Cannot adopt draft in status '{current_status}'; only 'approved' is allowed",
            409,
        )

    # CR-0164 C（合約 4.4d 紅線，衝突①裁定＝硬 gate）：adopt 進 KB/RAG 前須有
    # action='approved' 的家族覆核（不可只判「存在」——rejected 不退回 status，
    # 判存在會讓被退件草稿仍可 adopt）。缺 → 425 TOO_EARLY，導流先完成家族覆核。
    fr = await (await db_module._conn.execute(
        "SELECT 1 FROM family_reviews "
        "WHERE sop_draft_id = %s::uuid AND action = 'approved' LIMIT 1",
        (draft_id,))).fetchone()
    if not fr:
        raise ApiError(
            "FAMILY_REVIEW_REQUIRED",
            "採納前須先完成家族覆核（family review approved）——合約 4.4(d) 紅線",
            425,
        )
```

gate 位於狀態機檢查之後、`case_entries` INSERT（`api/services/sop_draft_service.py:437` 起）與 `sop_drafts` 狀態推進為 `published`（`:469-470`）之前。

狀態機定義於檔頭 `api/services/sop_draft_service.py:19-23`：

```
寫入路徑狀態機（review / adopt）：
  ...
  approved -------adopt-------------> published（同時建立 case_entries 一筆）
其他轉換一律 409 Conflict。已 published 不可再 adopt（一次性入庫）。
```

### 步驟 3 — service 層：家族覆核建立時的四眼與 ledger

`api/services/family_review_service.py:208-228`：

```python
    cur = await db_module._conn.execute(
        "SELECT status, reviewed_by FROM sop_drafts "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (sop_draft_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "SOP draft not found", 404)
    if (row[0] or "").lower() != "approved":
        raise ApiError(
            "CONFLICT",
            "Only admin-approved SOP drafts can be submitted for family review",
            409,
        )
    # TI-A10-02 / 合約 4.4(d)：高風險 SOP 雙審 —— 家族覆核者須異於初審 admin
    # （Knowledge Owner ≠ domain expert，四眼），同人不得兩審。
    admin_reviewer = row[1]
    if admin_reviewer and str(admin_reviewer) == str(reviewer_id):
        raise ApiError(
            "SOD_VIOLATION",
            "family reviewer must differ from initial admin reviewer (dual-review)",
            403,
        )
```

hash chain 寫入 `api/services/family_review_service.py:234-252`：

```python
        async with db_module._conn.transaction():
            await db_module._conn.execute("SET LOCAL lock_timeout = '2s'")
            await db_module._conn.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_FR_CHAIN_LOCK_KEY,)
            )
            prev_hash = await _fr_latest_hash()
            entry_hash = _fr_entry_hash(
                prev_hash, _fr_canonical(sop_draft_id, action, reviewer_id, comment))
```

驗證函式 `api/services/family_review_service.py:48-66`（`verify_family_review_ledger`，回 `{checked, valid, broken_at}`）。

一 draft 一覆核由 DB unique 約束保證，`api/services/family_review_service.py:253-260` 捕捉 `uniq_family_review_draft` 轉 409。

### 步驟 4 — cron 層：24h SLA 逾時處置

`api/realtime/family_review_sla_cron.py:1-11` 檔頭：

```python
"""家族覆核 SLA 逾時升級 cron — CR-0166 R1（合約 4.4(d) / BR-SOP-002）。

家族覆核端點宣稱 reviewer SLA 24h，但逾時無任何升級機制。本 cron 每日掃
sop_drafts.reviewed_at（管理員初審通過時間）超過 24h、仍未有 family_reviews
紀錄的草稿 → 寫 audit event（sop.family_review_overdue）＋通知該租戶管理層。
...
「累計 ≥3 件未審 → ChangeRequest 替補提名」（BR-SOP-002 後半）列 Phase II backlog。
"""
```

SLA 常數 `api/realtime/family_review_sla_cron.py:27`：

```python
SLA_HOURS = int(os.getenv("FAMILY_REVIEW_SLA_HOURS", "24"))
```

掃描條件 `api/realtime/family_review_sla_cron.py:93-107`：

```python
            "FROM sop_drafts sd "
            "WHERE LOWER(sd.status) = 'approved' "
            "  AND sd.reviewed_at IS NOT NULL "
            "  AND sd.reviewed_at < NOW() - (%s * INTERVAL '1 hour') "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM family_reviews fr WHERE fr.sop_draft_id = sd.id"
            "  ) "
```

逾時處置 `api/realtime/family_review_sla_cron.py:116-140`：兩個動作，(1) `audit_log_service.log_event(action="sop.family_review_overdue", ...)`、(2) `_notify_managers`。該函式全段無任何 UPDATE 語句；`sop_drafts` 的 status、旗標與 adopt gate 的判定條件皆未被改動。

TC 判定基準寫「reviewer 缺席 >24h → 升級 + 暫停 publish」（出處：批次 A TC 原文第 56 行）／程式碼的 SLA cron 只寫 audit 與通知（`family_review_sla_cron.py:120-140`）；publish（adopt）在任何時點都由步驟 2 的 gate 擋住，未見以「逾時」為條件的額外暫停機制。此處僅並陳，不裁定。

### 步驟 5 — 覆核率報表

`api/services/sop_performance_service.py:7`（檔頭）：

```
  - approval_rate = approved / (approved + rejected)
```

其計算來源 `api/services/sop_performance_service.py:60-99`，全部讀 `sop_drafts` 表：

```python
    cur = await db_module._conn.execute(
        "SELECT status, COUNT(*) FROM sop_drafts "
        "WHERE tenant_id = %s::uuid AND deleted_at IS NULL "
        "GROUP BY status",
        (tenant_id,),
    )
    ...
    approved = status_dist["approved"]
    rejected = status_dist["rejected"]
    published = status_dist["published"]
    decided = approved + rejected
    approval_rate = (
        round(100.0 * approved / decided, 2) if decided > 0 else 0.0
    )
```

即 `approval_rate_pct` 的分子分母皆取自 `sop_drafts.status`（admin 初審），非家族覆核。

`family_reviews` 在報表相關檔案的命中：

```
git grep -c "family_reviews" -- api/services/sop_performance_service.py api/routers/reports_kpi.py
（無輸出，exit=1）
```

前端指標頁 `web/brand-portal/src/app/admin/knowledge-base/sop-performance/page.tsx:14`、`:155` 消費的即為 `rates.approval_rate_pct`。

### 步驟 6 — DB schema 層

`SQL/migrations/074-family-review-ledger.sql:8-13`：

```sql
ALTER TABLE family_reviews ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE family_reviews ADD COLUMN IF NOT EXISTS entry_hash TEXT;
COMMENT ON COLUMN family_reviews.entry_hash IS
  'CR-0079/TI-A10-02：sha256(prev_hash + 正規化內容)；家族覆核 ledger 不可篡改偵測（合約 4.4d）';
CREATE INDEX IF NOT EXISTS idx_family_reviews_entry_hash
  ON family_reviews (created_at, id) WHERE entry_hash IS NOT NULL;
```

該 migration 檔頭（`:2-7`）自述雙審 distinct 由 service 層強制，DB 層只補 hash chain 欄位。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0164_family_review_gate.py tests/test_sop_performance.py \
  -p winloop_plugin -q
9 passed in 0.95s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0079_sop_dual_review.py -p winloop_plugin -q
3 passed in 0.90s
```

`api/tests/test_cr_0164_family_review_gate.py` 對到步驟 2 的 gate；`api/tests/test_cr_0079_sop_dual_review.py` 對到步驟 3 的四眼與 ledger。

`api/tests/test_sop_performance.py:77-78` 釘住的是 admin 初審率：

```python
    # approval_rate = 10/(10+2) = 83.33%
    assert result["rates"]["approval_rate_pct"] == 83.33
```

`api/tests/` 中無測試檔名或斷言涵蓋「家族覆核率 100%」或「逾時暫停 publish」。

---

## 事實結論

1. 未經 `action='approved'` 家族覆核的 adopt 一律失敗，錯誤碼 `FAMILY_REVIEW_REQUIRED`、HTTP 425，v1／v2 兩條路由共用同一 gate。
2. gate 判的是「有 approved 覆核」而非「有覆核紀錄」，該設計意圖寫在 `sop_draft_service.py:405-407` 的註解。
3. 家族覆核者與初審 admin 相同時回 403 `SOD_VIOLATION`（`family_review_service.py:224-228`）。
4. `family_reviews` 有 sha256 hash chain 與獨立 advisory lock，並有 `verify_family_review_ledger` 驗證函式。
5. SLA cron 每小時執行、以 `sop_drafts.reviewed_at` 起算 24 小時、以 audit_events 去重，逾時動作為寫 audit + 推播通知，不改變任何狀態。
6. 現有 SOP 指標報表的 `approval_rate_pct` 來源為 `sop_drafts.status`，與家族覆核率不同源；`family_reviews` 在報表 service 零命中。
7. cron 檔頭自述 BR-SOP-002 後半「累計 ≥3 件未審 → ChangeRequest 替補提名」列為 Phase II backlog。
