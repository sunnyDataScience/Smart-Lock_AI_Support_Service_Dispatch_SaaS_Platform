# TC-WO-01 — 客服按「轉為工單」

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 10） |
| 走查時間 | 2026-08-03 14:36–14:52（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `web/brand-portal`（UI）→ `api/routers`（路由）→ `api/services`（服務）→ `SQL/`（schema）；HITL 另查 `agent/lockcore` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 判定基準三條（工單 created、寫入 work_order_events 含 seq、AI 不可觸發）在程式碼中皆有對應實作；另觀測到 `api/openapi.yaml` 宣稱的 `created_by_role` 檢查在 Python 程式碼中不存在。 |

**TC 原文（來源：`smartlock-docs/enterprise/規格統控整理/SmartLock_整合測試計畫.xlsx`，② 測試案例主表）**

- 前置：問題卡 confirmed + 地址齊全
- 步驟：客服按「轉為工單」
- 預期結果（判定基準）：工單 created；寫入 work_order_events（事件溯源 seq）；AI 不可觸發此轉換（HITL 鐵律）
- 驗證需求：FR-API-01、FR-API-04｜所屬旅程：SC-03、SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 按「轉為工單」並填服務地址 | `WorkOrderCreated` | 問題卡須為 confirmed | `web/brand-portal/src/app/problem-cards/[id]/page.tsx:537`、`api/services/work_order_service.py:562` | UI 僅在 `status === "confirmed"` 顯示按鈕；service 端再擋一次，非 confirmed 拋 409 `STATE_CONFLICT` |
| 客服 | 同上 | `WorkOrderCreated` | 工單初始狀態為 created | `api/services/work_order_service.py:614-623` | `INSERT INTO work_orders (..., status, ...) VALUES (..., 'created', ...)` |
| 系統 | 建單後記事件 | `WorkOrderEventAppended(seq=n)` | 每張工單事件連號、缺號即代表遺失 | `api/services/work_order_service.py:657-668`、`1133-1138` | 寫入 `event_type='created'`，seq 由 `COALESCE(MAX(seq),0)+1` 於同一語句取號 |
| AI agent | （不應能發起）轉為工單 | — | HITL 鐵律：AI 永不自轉工單 | `agent/lockcore/app_config.py:21-28`、`api/routers/problem_cards_v2.py:412`、`api/routers/internal_ingest.py:16` | 白名單無任何 HTTP／執行工具；端點要求真人 JWT + 後台角色；agent 唯一寫入通道只建 draft 卡 |
| 客服 | 同一張卡重複轉單 | （不應重複建單） | 冪等 | `api/services/work_order_service.py:570-579`、`631-648` | 已有工單則回既有單且 `created=False`；併發撞 UNIQUE 亦回既有單 |

---

## 走查紀錄

### 步驟 1 — 定位 UI 的「轉為工單」入口與觸發條件

- **動作**：在 `web/brand-portal` 找按鈕元件與其顯示條件
- **預期**：按鈕只在問題卡為 confirmed 時可用（對應前置「問題卡 confirmed」）
- **實際**：顯示條件為 `card?.status === "confirmed"`，與前置一致

`web/brand-portal/src/app/problem-cards/[id]/page.tsx:535-537`

```tsx
const canDismiss = card?.status === "draft" || card?.status === "confirmed";
const canResolve = card?.status === "confirmed";
const canConvertToWO = card?.status === "confirmed";
```

`web/brand-portal/src/app/problem-cards/[id]/page.tsx:680-683`

```tsx
{canConvertToWO && (
  <button
    onClick={() => {
```

### 步驟 2 — 追前端送出的請求

- **動作**：讀 `handleConvertToWO`，確認 HTTP method、路徑與 payload
- **預期**：送出建立工單的請求，且帶服務地址（對應前置「地址齊全」）
- **實際**：`POST /tenants/{tenantId}/problem-cards/{id}/convert-to-work-order`，`customer_address` 為必帶欄位

`web/brand-portal/src/app/problem-cards/[id]/page.tsx:457-467`

```tsx
const res = await api.post<WorkOrderEnvelope>(
  tenantPath(`/problem-cards/${encodeURIComponent(id)}/convert-to-work-order`),
  {
    customer_address: info.customer_address,
    ...(info.customer_name ? { customer_name: info.customer_name } : {}),
    ...(info.customer_phone ? { customer_phone: info.customer_phone } : {}),
  },
  overrideReason && overrideReason.trim()
    ? { query: { override_reason: overrideReason.trim() } }
    : undefined,
);
```

（`tenantPath` 定義於 `web/brand-portal/src/lib/api.ts:205-208`，展開為 `/tenants/{tenantId}` 前綴。）

### 步驟 3 — 定位 API 路由與其呼叫者身分守衛

- **動作**：找對應的 route handler，讀其相依注入
- **預期**：只有已認證的後台人員可呼叫
- **實際**：`Depends(role_required(*BACKOFFICE_ROLES))`；`BACKOFFICE_ROLES` 展開為 `admin, operations_manager, dispatcher, customer_service`（`api/core/deps.py:293-299`），且 `role_required` 內部先過 `require_tenant`（`api/core/deps.py:198-212`）要求真人 JWT

`api/routers/problem_cards_v2.py:397-414`

```python
@router.post(
    "/tenants/{tenantId}/problem-cards/{id}/convert-to-work-order",
    operation_id="convertProblemCardToWorkOrderV2",
    summary="將已確認問題卡轉為工單 v2（F-002 客服審 PC → 開 WO）",
    response_model=WorkOrderEnvelope,
)
async def convert_problem_card_to_work_order_v2(
    response: Response,
    tenantId: str = Path(...),
    id: str = Path(...),
    body: ConvertProblemCardToWorkOrderRequest | None = None,
    override_reason: str | None = Query(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

### 步驟 4 — 判定基準①「工單 created」

- **動作**：讀 service 的 INSERT 語句，確認工單初始狀態值
- **預期**：建立的工單狀態為 `created`
- **實際**：INSERT 字面值即 `'created'`

`api/services/work_order_service.py:614-623`

```python
insert_cur = await db_module._conn.execute(
    "INSERT INTO work_orders "
    "  (problem_card_id, status, priority, "
    "   customer_name, customer_phone, customer_address, created_by, document_number, "
    "   brand, model, problem_type, service_category, photos, tenant_id, quote_gate_applied, "
    "   serial_number) "
    "VALUES (%s::uuid, 'created', %s, %s, %s, %s, "
```

### 步驟 5 — 判定基準②「寫入 work_order_events」

- **動作**：確認建單後是否寫事件、事件型別為何
- **預期**：建單後寫入一筆 work_order_events
- **實際**：呼叫 `_insert_wo_event`，`event_type="created"`

`api/services/work_order_service.py:654-668`

```python
# CR-0193 / TC-WO-01：建單事件。正典 20_Test_Cases.md:258 直接驗這一筆。
# 刻意放在 UNIQUE 回放路徑（上方 return wo, False）之後——併發撞號時事件已由
# 贏家寫過，回放路徑再寫一筆會讓同一次轉換出現兩筆 'created'。
await _insert_wo_event(
    wo_id=new_wo_id, tenant_id=tenant_id, actor_user_id=created_by,
    event_type="created",
    payload={
        "origin": "problem_card",
        "problem_card_id": pc_id,
        "urgency": pc_urgency,
        "emergency_class": pc_emergency_class,
        "quote_gate_applied": True,
    },
)
```

### 步驟 6 — 判定基準②之「事件溯源 seq」

- **動作**：確認 seq 的產生機制與唯一性保證
- **預期**：每張工單的事件有連號 seq
- **實際**：於同一 INSERT…SELECT 語句內取 `COALESCE(MAX(seq),0)+1`；撞號重試最多 5 次

`api/services/work_order_service.py:1133-1138`

```python
sql = (
    "INSERT INTO work_order_events "
    "  (work_order_id, tenant_id, actor_user_id, event_type, payload, seq) "
    "SELECT %s::uuid, %s::uuid, %s, %s, %s::jsonb, COALESCE(MAX(seq), 0) + 1 "
    "FROM work_order_events WHERE work_order_id = %s::uuid"
)
```

`api/services/work_order_service.py:1151-1155`

```python
except _pg_errors.UniqueViolation as exc:
    # 只吞「同工單併發撞號」；其他 UNIQUE 衝突照原樣拋出，不掩蓋真 bug。
    constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
    if constraint != "work_order_events_wo_seq_key":
        raise
```

### 步驟 7 — 對照 DB schema 確認 seq 的約束

- **動作**：讀建表 SQL
- **預期**：seq 有唯一性約束，`created` 為合法 event_type
- **實際**：`seq INTEGER NOT NULL` + `UNIQUE (work_order_id, seq)`；`'created'` 在 CHECK 清單內（migration 122 加入）

`SQL/Schema_work_order_events.sql:37`、`:52-53`

```sql
'created',            -- migration 122 (CR-0193)
...
seq                 INTEGER NOT NULL,
CONSTRAINT work_order_events_wo_seq_key UNIQUE (work_order_id, seq)
```

### 步驟 8 — 判定基準③「AI 不可觸發此轉換」之一：agent 有無可用工具

- **動作**：讀客服 agent 的工具白名單
- **預期**：agent 無任何可發出 HTTP 請求或執行外部指令的工具
- **實際**：白名單 6 項，皆為讀檔／搜尋／轉真人；註解明列已砍除 `web_fetch`、`exec`、`shell` 等

`agent/lockcore/app_config.py:18-28`

```python
# 客服 agent 工具白名單:只留「讀知識 + 兜底搜尋 + 轉真人」。
# read_file/list_dir/find_files/grep 是讀 skill(SKILL.md + references/)的命脈,不可砍;
# 砍掉 write/edit/exec/shell/spawn/cron/message/web_fetch/image 等對客服危險或無用的工具。
CS_TOOL_ALLOWLIST: set[str] = {
    "read_file",
    "list_dir",
    "find_files",
    "grep",
    "web_search",
    "transfer_to_human",
}
```

### 步驟 9 — 判定基準③之二：agent 唯一的寫入通道能做到什麼

- **動作**：讀 agent 對 API 的寫入路由
- **預期**：該通道不能建立工單
- **實際**：`internal_ingest` 路由檔頭明載「AI 永不自轉工單：本路由最多建草擬卡」，且該路由只呼叫 `escalation_to_draft_pc`

`api/routers/internal_ingest.py:13-16`

```python
設計原則（對齊架構鎖）：
  - agent 核心與 CS_TOOL_ALLOWLIST 不變；寫入只發生在「通道旁路」這一層。
  - 復用既有 conversation_service / problem_card_service，不重寫 SQL。
  - **AI 永不自轉工單**：本路由最多建草擬卡；confirm/convert 走客服認證端點（ADR-0028/0031）。
```

該通道建出的卡為 `draft`，而步驟 1 的 UI 條件與步驟 4 前的 service 檢查都要求 `confirmed`：

`api/services/work_order_service.py:562-567`

```python
if pc_status != "confirmed":
    raise ApiError(
        "STATE_CONFLICT",
        f"Cannot convert problem card in status '{pc_status}'; expected 'confirmed'",
        409,
    )
```

### 步驟 10 — 執行可離線運行的既有測試

- **動作**：跑覆蓋判定基準③的 agent 測試
- **預期**：白名單測試通過
- **實際**：3 passed

```
cd agent && python -m pytest tests/test_tool_allowlist.py -q
...                                                                      [100%]
3 passed in 38.67s
```

- **動作**：跑覆蓋判定基準①②的 API 測試
- **預期**：取得執行證據
- **實際**：第一輪無法取得（19 skip + 7 error，皆因無資料庫）；接上本機測試庫後重跑，26 項全過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0193_lifecycle_events.py -q -rs
SKIPPED [8] tests\test_cr_0193_lifecycle_events.py:238: DB unavailable
19 skipped in 0.35s

cd api && python -m pytest tests/test_pc_convert_to_wo.py -q -rs
ERROR    api.db:db.py:48 環境變數 POSTGRES_URI 未設定
7 failed in 4.59s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」；測試庫另套 `SQL/seeds/problem_cards.sql` 與 `SQL/seeds/work_orders.sql`，現有 21 張問題卡、3 張工單——第一輪 skip 理由之一為「no work order in DB to attach events to」）：

```
cd api && python -m pytest -p winloop_plugin tests/test_cr_0193_lifecycle_events.py -q -rs
...................                                                      [100%]
19 passed in 0.78s

cd api && python -m pytest -p winloop_plugin tests/test_pc_convert_to_wo.py -q -rs
.......                                                                  [100%]
7 passed in 3.29s
```

判定基準①②的執行證據來自第二輪；其覆蓋範圍仍如「觀測到的其他事實」第 3 點所述（事件寫入由 `_insert_wo_event` 直接驗證，convert 端點的測試斷言為回傳工單狀態）。

---

## 觀測到的其他事實

1. **`api/openapi.yaml` 宣稱的守衛機制在 Python 程式碼中找不到。**
   `api/openapi.yaml:41`：

   ```
   - **Forbidden actions**: AI agent cannot call `convert_to_work_order` directly;
     CS 1-click required (ADR-0031); enforced at API layer via `created_by_role` check
   ```

   `git grep -n "created_by_role" -- api web agent` 的命中全部落在 `api/openapi.yaml`（第 41、368、369、382、386、409、5539、5558、5752 行），`api/**/*.py` 零命中。實際生效的是步驟 3、8、9 所示的角色守衛與通道分離。此處僅並陳兩者，不裁定何者應修正。

2. **v1 與 v2 兩條路由同時存在**。前端打 v2（`api/routers/problem_cards_v2.py:397`）；v1 `api/routers/problem_cards.py:277-302` 亦提供同名操作，兩者都掛 `role_required(*BACKOFFICE_ROLES)`，但 v1 未呼叫 `problem_card_service.assert_completeness`（v2 於 `problem_cards_v2.py:422-428` 呼叫）。

3. **既有測試未涵蓋「convert 端點 → work_order_events 出現 created」的端到端斷言**。`api/tests/test_cr_0193_lifecycle_events.py` 全部直接呼叫 `_insert_wo_event`（該檔 grep `convert` 零命中）；`api/tests/test_pc_convert_to_wo.py` 斷言的是回傳工單狀態（`:137` `status == "inquiring"`），未斷言事件列。

4. **DB 對外狀態值與 API 對外狀態值不同**。DB 寫入 `'created'`（步驟 4），而 `api/tests/test_pc_convert_to_wo.py:137` 斷言 API 回傳 `status == "inquiring"`。
