# TC-ONSITE-02 — 現場加價 ≤ NTD 500 的師傅自確三件套

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，分級與 pending gate 相關 7 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 20:35（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:2890-2921`、`:2924-3075`、`:1471-1488`、`:1585-1591`、`SQL/migrations/053-scope-tier-autoconfirm-config.sql`、`api/routers/work_orders_v2.py:771-798`、`api/services/scope_change_service.py:125-270`、`api/services/signature_service.py:46-74`、`web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 金額分級函式 `_classify_scope_tier` 存在且門檻 `minor_max=500` 由 M18 config 驅動，`delta ≤ 500` 判為 `minor`、`requires_supervisor=False`。但 `record_scope_change` 對**所有** tier 一律 `INSERT scope_changes ... status='pending'`＋mint public token＋推 LINE，`tier` 僅寫進 `new_scope` JSONB 與事件 payload；程式碼中找不到「minor 即自動通過／免客戶確認」的分支。TC 所述「三件套」的三個構件分散於三處（`digital_signatures`、`media_files`、`audit_events`），無任一處以「三件套齊備」為條件放行 scope change。 |

**TC 原文**｜前置：現場加價 ≤ NTD 500｜步驟：師傅發起 scope change｜判定基準：師傅自確 + 客戶簽名 + 照片三件套即通過｜需求：FR-API-08｜旅程：SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | POST `/work-orders/{id}/scope-change` | `ScopeChangeRequested` | 狀態限 `_SUBFLOW_FROM` | `work_order_service.py:2949-2955` | 非 assigned/accepted/in_progress → 409 |
| 系統 | 依金額分級 | `ScopeTierClassified` | ≤500 → minor | `work_order_service.py:2898-2921` | 回 `{tier, delta, pct, requires_supervisor}` |
| 系統 | 建提案 | `ProposalCreated(pending)` | minor 免客戶確認 | `work_order_service.py:2992-3009` | **無 tier 分支**，一律 `status='pending'` |
| 系統 | 推 LINE 給客戶 | `ProposalPushed` | minor 不推 | `work_order_service.py:3054-3071` | **無 tier 分支**，一律 enqueue |
| 技師 | 三件套齊備自確 | `ScopeChangeSelfApproved` | 簽名＋照片＋audit | — | **找不到**任何以三件套為條件的核可路徑 |
| 客戶 | 公開連結決議 | `CustomerApproved` | accept → 復工 | `scope_change_service.py:172-207` | `customer_approved` + wo → `in_progress` + `resumed` 事件 |

---

## 走查紀錄

### 步驟 1 — 金額分級與 ≤500 的判定

- **動作**：讀 `_classify_scope_tier`
- **預期**：≤500 判 minor 且不需主管
- **實際**：一致

`api/services/work_order_service.py:2890-2921`

```python
# CR-0038 桶4 / BR-M08-02：scope change 金額分級閘預設（門檻入 M18 config 不寫死）
_SCOPE_TIER_DEFAULTS = {
    "minor_max": 500,       # ≤500 視為 minor（可後續做自動核准）
    "standard_max": 2000,   # 501-2000 為 standard
    "major_pct": 0.5,       # 增幅 ≥ 原價 50% → major（需主管核准），無視金額
}


async def _classify_scope_tier(original_price: float, new_price: float | None) -> dict:
    ...
    delta = max(0.0, (new_price or 0.0) - (original_price or 0.0))
    pct = (delta / original_price) if original_price and original_price > 0 else (1.0 if delta else 0.0)
    if delta > float(policy["standard_max"]) or pct >= float(policy["major_pct"]):
        tier = "major"
    elif delta > float(policy["minor_max"]):
        tier = "standard"
    else:
        tier = "minor"
    return {
        "tier": tier,
        "delta": round(delta, 2),
        "pct": round(pct, 4),
        "requires_supervisor": tier == "major",
    }
```

註解 `:2892` 自述「≤500 視為 minor（**可後續做自動核准**）」。

門檻的 config 來源：`SQL/migrations/053-scope-tier-autoconfirm-config.sql:19-24`

```sql
INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'scope_change_policy', 'default',
  '{"minor_max":500,"standard_max":2000,"major_pct":0.5}'::jsonb,
```

**另一項事實**：`pct >= major_pct`（0.5）優先於金額判定。原報價 600 元、加價 400 元（≤500）時 `pct=0.667` → tier 為 `major`，非 `minor`（`work_order_service.py:2910`）。

### 步驟 2 — 分級結果的實際作用

- **動作**：追 `tier_info` 的所有消費點
- **預期**：minor 走自動通過分支
- **實際**：只被寫入資料，無任何 if 分支消費

`api/services/work_order_service.py:2988-3009`

```python
    # CR-0038 桶4 / BR-M08-02：金額分級（config 驅動）；major 標 requires_supervisor
    tier_info = await _classify_scope_tier(original_price, new_price)

    # INSERT scope_changes 表
    cur = await db_module._conn.execute(
        "INSERT INTO scope_changes "
        "  (work_order_id, technician_id, reason, "
        "   original_scope, new_scope, original_price, new_price, status) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s, 'pending') "
        "RETURNING id",
```

SQL 字面即 `'pending'`，無參數化、無條件分支。`tier_info` 之後僅出現在 `new_scope` JSONB（`:3005`）與事件 payload（`:3033`）。

`requires_supervisor` 的全 repo 消費者：

```
$ grep -rn "requires_supervisor" --include=*.py --include=*.tsx --include=*.ts api web
api/services/work_order_service.py:2900:  ...；major → requires_supervisor。"""
api/services/work_order_service.py:2920:        "requires_supervisor": tier == "major",
api/services/work_order_service.py:2988:  # CR-0038 桶4 / BR-M08-02：金額分級（config 驅動）；major 標 requires_supervisor
api/tests/test_cr_0038_bucket4.py:26,34,42,50
```

除註解、產生點與 4 個測試斷言外，無執行期讀取者。

### 步驟 3 — pending scope 的實際效力

- **動作**：讀 `_has_pending_scope_change` 的引用點
- **預期**：minor 提案不擋後續作業
- **實際**：任何 `status='pending'`（含 minor）都擋完工

`api/services/work_order_service.py:1471-1477`

```python
async def _has_pending_scope_change(wo_id: str) -> bool:
    """CR-0049 / BR-M08-02：是否有未決（status='pending'）範圍變更（報價/加價未經客戶確認）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM scope_changes WHERE work_order_id = %s::uuid AND status = 'pending' LIMIT 1",
        (wo_id,),
    )
    return await cur.fetchone() is not None
```

`api/services/work_order_service.py:1585-1591`

```python
    # CR-0049 / BR-M08-02：報價變更未經客戶確認（pending scope）→ 不可完工（安全閘，admin override 路徑可繞）
    if await _has_pending_scope_change(wo_id):
        raise ApiError(
            "PENDING_SCOPE_CHANGE",
            "有未經客戶確認的範圍/加價變更，須客戶確認或主管覆寫後才可完工",
            409,
        )
```

查詢條件不含 tier 或金額。

- TC 判定基準：≤500 三件套齊「即通過」
- 程式碼：提案一律 `pending`，解除途徑只有客戶決議（`scope_change_service.py:172-184`）或 admin override（`:320-331`）

此處僅並陳，不裁定。

### 步驟 4 — 三件套三個構件的實際落點

- **動作**：逐項對照
- **預期**：三件套齊備可作為放行條件
- **實際**：三者各自獨立寫入，無聚合判定

| 三件套構件 | 程式碼落點 | 事實 |
|---|---|---|
| 師傅自確 | — | **找不到**；`scope_changes` 無 technician self-approve 欄或狀態 |
| 客戶簽名 | `api/services/signature_service.py:167-174` 寫 `digital_signatures` | 有；但只在完工硬閘被查（`work_order_service.py:1480-1488` `_signature_exists`），非 scope change 條件 |
| 照片 | `api/services/media_service.py:222-254` 寫 `media_files` | 有；完工硬閘查張數（`:1552-1559`），非 scope change 條件 |
| audit | `api/services/scope_change_service.py:212-227` | 有；但只在**客戶回覆後**寫，`record_scope_change` 發起時不寫 audit_events |

`record_scope_change` 發起端的留痕是 `work_order_events`（`work_order_service.py:3035-3038`），非 `audit_events`：

```python
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="scope_change", payload=payload,
    )
```

### 步驟 5 — 技師端 UI 走的實際是哪條路

- **動作**：讀技師端「現場報價修正／scope-change」頁
- **預期**：呼叫 scope-change 端點
- **實際**：呼叫的是 `requote-requests`，且刻意不收金額

`web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:1-5`

```tsx
// CR-0144/ADR-027:現場報價修正(requote command)——技師只提交項目異動草稿,
// **不含金額**(零定價權;金額由品牌定價引擎+小編審核決定,經客戶確認生效)。
// 本頁原為 scope-change 自填單價流,與 ADR-027 相悖,2026-07-10 原地改造。
```

`:61-64`

```tsx
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/requote-requests`),
        { reason, item_diffs: diffs },
      );
```

搜尋 `web/` 中對 `POST .../scope-change` 的呼叫：

```
$ grep -rn "scope-change" web/tech-portal/src web/brand-portal/src --include=*.tsx --include=*.ts
web/tech-portal/src/app/my-orders/[id]/page.tsx:580:  href={`/my-orders/${wo.id}/scope-change`}
web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:5,32
web/brand-portal/src/app/scope-change/[token]/page.tsx（客戶端 public 頁）
...
```

僅有導頁連結與客戶端 public 頁，**找不到**任何前端對 `POST /tenants/{t}/work-orders/{id}/scope-change`（`work_orders_v2.py:771`）的呼叫；技師端加價金額因此不經由該端點產生。

### 步驟 6 — 執行既有測試

- **動作**：跑分級與 pending gate 測試
- **預期**：取得執行證據
- **實際**：7 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0038_bucket4.py tests/test_cr_0049_pending_scope_gate.py \
  -q -p winloop_plugin --tb=line
7 passed
```

`test_cr_0038_bucket4.py::test_scope_tier_minor`（`:22-26`）斷言 `requires_supervisor is False`；`test_cr_0049_pending_scope_gate.py::test_pending_scope_blocks_completion`（`:58`）斷言 pending 擋完工。兩檔皆無「minor 自動通過」的斷言。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:189` 與 `02_BRD.md:286` 記載「≤500 師傅自確，三件套（客戶簽名＋照片＋audit log）齊備後續工」，與 TC 判定基準同源。
- `record_scope_change` 對 `total_estimate` 為空字串／None 時視為不改價（`work_order_service.py:2976-2977`），此時 `new_price=None`、`delta=0` → tier 恆為 `minor`。
- 客戶 30 分鐘未回覆有 cron 標記逾時（`scope_change_service.py:383-420`），只寫 audit 不改 status，不自動通過。
- `scope_changes` 提案的 public token TTL 為 7 天（`work_order_service.py:3017-3022`）。
