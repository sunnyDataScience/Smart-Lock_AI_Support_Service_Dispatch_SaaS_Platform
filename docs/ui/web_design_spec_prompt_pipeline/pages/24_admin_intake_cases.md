---
title: 進線建案（Case）頁面設計規格
status: active
tier: 5
ia_page: A38
route: /admin/cases
cr: CR-0108
last_synced_with: web/src/app/admin/cases/page.tsx
---

# Page-Level Prompt: 進線建案（Case）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> IA 編號 **A38**（暫定）。M01 進線 Case 入口（CR-0108）—— 客服多渠道代建 Case、瀏覽進線案件列表、推進案件狀態與首次回應 SLA 監控。
> Case = 一次進線事件（上游容器，下可含多 problem_card / work_order，CR-0108 D4）。LINE 進線由 agent 自動建案，本頁列表會顯示這些 `source=line` 案件；非 LINE 進線（電話／官網／熟客介紹）由客服在此手動代建。

---

## [PAGE META]

- **page_name**: 進線建案 Intake Cases
- **route_path**: `/admin/cases`
- **page_type**: form + list
- **ia_pages**: A38（暫定）
- **openapi_ops**: listIntakeCases, createIntakeCase, getIntakeCase, updateIntakeCase
- **asyncapi_ops**: none
- **primary_goal**: 讓客服把所有進線（含 LINE 自動建案與電話／官網／熟客介紹的手動代建）統一收斂成可追蹤的 Case，並啟動首次回應 SLA 計時
- **secondary_goal**: 即時掌握逾時未回應案件，推進 open → in_progress → closed 案件生命週期
- **target_users**:
  - 主要：客服（customer_service）—— 接聽電話、登記進線、首次回應
  - 次要：客服主管 / 派工員 / 平台管理員（operations_manager / dispatcher / admin）—— 監看進線量與 SLA
- **entry_point**: 左側導覽列「開單流程」群組第 2 項「進線案件」（icon: Inbox），位於 Dashboard 之後、對話之前
- **expected_time_on_page**: 代建一筆案件 30 秒 - 1 分鐘；巡檢進線列表與推進狀態 1-3 分鐘

---

## [STRUCTURE: SECTIONS]

> 由上至下，單欄堆疊。

1. **page_header**
   - section_type: header_bar
   - section_purpose: 頁面標題（含 Inbox 圖示）、進線總件數、SLA 逾時告警徽章

2. **feedback_banner**
   - section_type: inline_banner
   - section_purpose: 操作結果回饋（建立成功綠 banner / 錯誤紅 banner），位於內容區頂部

3. **intake_form**
   - section_type: form
   - section_purpose: 客服代建非 LINE 進線案件（渠道 + 客戶姓名 / 電話 / 摘要），建立後自動發號並啟動 SLA

4. **case_list_table**
   - section_type: data_table
   - section_purpose: 顯示所有進線案件（案號 / 渠道 / 客戶 / 摘要 / 狀態 / SLA / 操作）

5. **status_actions**（嵌於列表「操作」欄）
   - section_type: inline_actions
   - section_purpose: 依案件當前狀態推進（標記處理中 / 結案）

---

## [SECTION COMPONENT SPEC]

### Section: page_header

> ✅ 已實作 — `web/src/app/admin/cases/page.tsx:115-124`

- **layout**: 全寬單列，`flex items-center gap-3`，底部分隔線 `border-b`，左側留位給 mobile 漢堡（`pl-14 pr-4 md:px-8 py-5`）
- **elements**:
  - page_icon: Icon / required / lucide `Inbox` / `h-7 w-7 text-[var(--primary)]`（`page.tsx:116`）
  - page_title: H1 / required / 文案固定「進線案件（Case）」/ `text-2xl font-bold text-[var(--text-primary)]`（`page.tsx:117`）
  - case_count: Text Caption / required / 「共 {items.length} 件」/ `text-[13px] text-[var(--text-secondary)]`（`page.tsx:118`）
  - sla_overdue_badge: Badge / conditional / 僅 `overdueCount > 0` 顯示；內含 lucide `AlertTriangle` + 「{overdueCount} 件 SLA 逾時」/ 紅底紅字 `bg-red-50 text-red-700`（`page.tsx:119-123`，`overdueCount` 來源 `page.tsx:109`）
- **states**:
  - default: 顯示標題 + 件數，無逾時則不顯示告警徽章
  - overdue: 有逾時案件時顯示紅色告警徽章
  - loading: 件數沿用初始 `items` 空陣列 → 顯示「共 0 件」（🚧 目前標題列無 skeleton；規格建議件數載入中改 skeleton）
- **copy_constraints**: 標題固定文案

### Section: feedback_banner

> ✅ 已實作 — `web/src/app/admin/cases/page.tsx:127-136`

- **layout**: 全寬橫幅，置於內容捲動區頂部，`mb-4 rounded-lg px-4 py-3 text-sm`
- **elements**:
  - error_banner: Banner / conditional / 紅底紅字 `border-red-200 bg-red-50 text-red-700`；內容為 `error` 字串（`page.tsx:127-131`）。錯誤訊息格式：API 錯誤顯示 `{errorCode} ({status})：{message}`（`page.tsx:60`），表單前端驗證失敗顯示「請至少填寫需求摘要或客戶聯絡資訊」（`page.tsx:71-73`）
  - success_banner: Banner / conditional / 綠底綠字 `border-green-200 bg-green-50 text-green-700`，含 lucide `Check` icon；內容如「已建立進線案件 C-000123（電話）」（`page.tsx:132-136`，文案組裝 `page.tsx:86`）
- **states**:
  - default: 兩個 banner 皆隱藏
  - error: 顯示紅色 banner（`error` 非 null 時）
  - success: 顯示綠色 banner（`ok` 非 null 時）
  - 🚧 規格建議：success banner 數秒後自動淡出 / 可手動關閉（目前需下次操作覆寫才消失）

### Section: intake_form

> ✅ 已實作 — `web/src/app/admin/cases/page.tsx:138-180`

- **layout**: 卡片容器 `rounded-lg border bg-[var(--bg-surface)] p-4 mb-6`；欄位區 responsive grid `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`（`page.tsx:139,146`）
- **elements**:
  - form_title: H3 / required / 含 lucide `PhoneCall` icon + 「代客建案（電話/官網/熟客介紹）」/ `text-[15px] font-semibold`（`page.tsx:140-142`）
  - form_hint: Text Caption / required / 固定提示「LINE 進線由系統自動建案；此處供客服登記非 LINE 進線。建立後自動發案號並啟動首次回應 SLA 計時。」`text-[12px] text-[var(--text-secondary)]`（`page.tsx:143-145`）
  - channel_select: Select / required / label「進線渠道」標星號 required；選項僅 3 項（`CHANNEL_OPTIONS`，`page.tsx:24-28`）：
    - `phone` →「電話」（預設值，`page.tsx:48`）
    - `web` →「官網表單」
    - `referral` →「熟客介紹」
    - 🚧 `line` 不在手動表單（由 agent 自動建案，`page.tsx:23` 註解 D1）；partner 4 渠道屬 Phase II（M14），後端 `_SOURCE_CHANNELS` 僅收 `line/phone/web/referral`（`api/services/intake_case_service.py:24`）
  - customer_name_input: Input / optional / label「客戶姓名」/ 受控 `customerName`（`page.tsx:156-158`）
  - customer_phone_input: Input / optional / label「客戶電話」/ 受控 `customerPhone`（`page.tsx:159-161`）
  - summary_input: Input / optional / label「需求摘要」/ placeholder「如：三樓鐵門鎖舌卡住」/ 受控 `summary`（`page.tsx:162-169`）
  - submit_btn: Button Primary / required / 文案「建立進線案件」/ busy 時「建立中…」+ disabled；`h-[38px] bg-[var(--primary)] hover:bg-[#1D4ED8]`（`page.tsx:172-178`）
- **input style**: 所有 input/select 共用 `INPUT` class — `rounded-md border px-3 py-2 text-[13px] focus:border-[var(--primary)]`（`page.tsx:261-262`）
- **field component**: 共用 `Field` wrapper，label 小灰字 + required 紅星（`page.tsx:264-272`）
- **states**:
  - default: 渠道預設「電話」，其餘欄位空白
  - validating: 送出前前端檢查 — 摘要、客戶姓名、客戶電話三者皆空 → 顯示錯誤「請至少填寫需求摘要或客戶聯絡資訊」，不送 API（`page.tsx:71-74`）
  - submitting: `busy=true`，按鈕 disabled + 文案改「建立中…」（`page.tsx:177`）
  - success: 清空姓名 / 電話 / 摘要（渠道保留），重新載入列表，顯示成功 banner（`page.tsx:86-90`）
  - error: 顯示錯誤 banner，欄位內容保留（`page.tsx:91-92`）
- **copy_constraints**: label 短詞；摘要為單行 input（🚧 規格建議：摘要改 textarea 支援多行，目前為單行 `<input>`）

### Section: case_list_table

> ✅ 已實作 — `web/src/app/admin/cases/page.tsx:182-254`

- **layout**: 全寬原生 `<table className="w-full text-sm">`，外層 `rounded-lg border bg-[var(--bg-surface)] overflow-hidden`；表頭 `bg-[#F8FAFC] text-xs text-[var(--text-secondary)]`（`page.tsx:188-200`）
- **columns**（7 欄，`page.tsx:191-199` 表頭 / `page.tsx:202-249` 資料列）:
  - col_case_number: Text Mono / required / 案號 `C-NNNNNN`，等寬字體強調 `font-mono text-[13px] font-medium`（`page.tsx:204-206`）。案號由後端序列 `saas.intake_case_number_seq` 原子遞增、格式化為 `C-{seq:06d}`（`api/services/intake_case_service.py:82-84`）
  - col_channel: Text / required / 顯示 `CHANNEL_LABEL[source_channel]`（`page.tsx:207-209`）— `line→LINE`、`phone→電話`、`web→官網表單`、`referral→熟客介紹`（`page.tsx:29-34`）。⚠️ 此欄是 LINE 自動建案案件在本頁的可見入口（CR-0108 S3）
  - col_customer: Text / required / `customer_name`（空顯示「—」）+ 若有電話以 `· {customer_phone}` 接續灰字（`page.tsx:210-213`）
  - col_summary: Text / required / `summary`（空顯示「—」）（`page.tsx:214`）
  - col_status: StatusBadge / required / 文字來自 `STATUS_LABEL`（`page.tsx:35-39`）：`open→待回應`、`in_progress→處理中`、`closed→已結案`；單一徽章樣式 `bg-[#E0E7FF] text-[#4338CA]`（🚧 三狀態目前共用同色 indigo 徽章，未做狀態分色；規格建議：open=amber / in_progress=blue / closed=gray）（`page.tsx:215-219`）
  - col_sla: SLA Indicator / required / 詳見下方「SLA 視覺」（`page.tsx:220-230`）
  - col_actions: Inline Actions / required / 詳見下方 status_actions（`page.tsx:231-248`）
- **states**:
  - default: 列以 `border-t` 分隔（`page.tsx:203`）
  - loading: 顯示純文字「載入中…」`text-sm text-[var(--text-secondary)]`（`page.tsx:183-184`）（🚧 規格建議：改 skeleton rows，對齊技師頁 §technician_table）
  - empty: 顯示純文字「目前沒有進線案件」`text-[var(--text-disabled)]`（`page.tsx:185-186`）（🚧 規格建議：升級為 EmptyState 插圖 + 引導 CTA「立即代客建案」聚焦表單）
  - error: 不在表格內呈現，統一走頂部 error banner（`page.tsx:60,92,105`）
  - 🚧 未實作：排序、分頁、篩選（後端 `listIntakeCases` 已支援 `status` / `source_channel` query 篩選與 `limit`，前端尚未接 UI；`api/routers/intake_cases_v2.py:55-66`）。前端目前無條件 `GET /cases` 取預設 50 筆（`page.tsx:57`，後端預設 `limit=50`）
- **copy_constraints**: 摘要過長未截斷（🚧 規格建議：摘要欄 `truncate` + hover tooltip 顯示全文）

### Section: status_actions（嵌於 col_actions）

> ✅ 已實作 — `web/src/app/admin/cases/page.tsx:231-248`

- **layout**: 行內按鈕，`rounded border px-2 py-1 text-[12px] hover:bg-[#F1F5F9]`
- **elements**（依案件當前 `status` 條件渲染，single-step 推進）:
  - mark_in_progress_btn: Button Ghost / conditional / 僅 `status === "open"` 顯示 / 文案「標記處理中」/ 點擊 `updateStatus(id, "in_progress")`（`page.tsx:232-239`）。後端在 open→in_progress 時以 `COALESCE` 記首次回應 `first_responded_at = NOW()`（`api/services/intake_case_service.py:170-171`），此即關閉首次回應 SLA 計時
  - close_btn: Button Ghost / conditional / 僅 `status === "in_progress"` 顯示 / 文案「結案」/ 點擊 `updateStatus(id, "closed")`（`page.tsx:240-247`）
  - closed 態：無任何操作按鈕（終態）
- **interaction**: `updateStatus` 走 `PATCH /tenants/{tid}/cases/{id}` body `{ status }`，成功後 `cacheInvalidate` + reload 列表（`page.tsx:98-107`）
- **states**:
  - open: 僅顯示「標記處理中」
  - in_progress: 僅顯示「結案」
  - closed: 無按鈕
  - error: 失敗走頂部 error banner（`page.tsx:104-106`）
  - 🚧 未實作：操作中 loading / disabled 狀態（無 per-row busy 旗標，連點可能重複送 PATCH）；結案無二次確認（規格建議：結案為不可逆推進，加確認對話框）

---

## SLA 視覺規範

> ✅ 衍生旗標已實作 — 視覺 `page.tsx:220-230`；旗標來源 `api/services/intake_case_service.py:129,147`

first-response SLA 數值來自 config `[intake] first_response_sla_minutes`（預設 30 分，`api/services/intake_case_service.py:29-30`）。建案時後端寫入 `first_response_due_at = NOW() + interval(分鐘)`（`intake_case_service.py:90-91`）。`sla_overdue` 為**衍生旗標**（非 DB 欄位）：`first_response_due_at` 存在 **且** `first_responded_at` 為 null（尚未回應）**且** `first_response_due_at < now`（已過期）（`intake_case_service.py:129`）。

| 條件（依序判斷） | 顯示 | 樣式 | code |
|---|---|---|---|
| `status === "closed"` | 「—」 | `text-[var(--text-disabled)]` | `page.tsx:221-222` |
| `sla_overdue === true` | 「逾時」 | 紅字粗體 `font-semibold text-red-600` | `page.tsx:223-224` |
| `first_responded_at` 有值 | 「已回應」 | 綠字 `text-[#15803D]` | `page.tsx:225-226` |
| 其餘（待回應中） | 「待回應」 | 琥珀字 `text-[#B45309]` | `page.tsx:227-228` |

頁首 SLA 逾時告警徽章統計 = `items.filter(c => c.sla_overdue).length`（`page.tsx:109`）。

- 🚧 未實作（規格先行）：
  - **SLA 倒數**：列表未顯示距到期剩餘分鐘 / 已逾時時長（`first_response_due_at` 已有資料，可算）。規格建議：「待回應」態加倒數（如「剩 12 分」），逾時態加逾時時長（如「逾時 8 分」）
  - **SLA 級距分流**：CR-0108 D2 提到「級距」，目前僅單一 30 分門檻、單一逾時態，無多級距（如黃色預警 / 紅色逾時 / 嚴重逾時）分色分流
  - **自動刷新**：列表無 polling，SLA 旗標僅在手動 reload / 操作後重算（前端 `now` 不變則徽章不會自動翻紅，須重新 `load()`）

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入** → `useEffect` 觸發 `load()` → `GET /tenants/{tid}/cases`（取 envelope `{ data }`）→ 渲染列表 + 頁首件數 / 逾時統計（`page.tsx:53-68`）
2. **代客建案** → 填渠道 + 至少一項（摘要 / 姓名 / 電話）→ 點「建立進線案件」→ 前端非空檢查 → `POST /tenants/{tid}/cases` → 成功：`cacheInvalidate` + 成功 banner（含新案號）+ 清空欄位 + reload；失敗：error banner（`page.tsx:70-96`）
3. **標記處理中** → open 案件點「標記處理中」→ `PATCH {status:"in_progress"}` → 後端記 `first_responded_at`（關閉 SLA）→ reload（`page.tsx:232-239`）
4. **結案** → in_progress 案件點「結案」→ `PATCH {status:"closed"}` → reload（`page.tsx:240-247`）
5. **LINE 自動建案可見**（被動）→ agent 在 LINE 進線轉真人時自動建立 `source=line` 的 Case（CR-0108 S3）→ 客服 reload 本頁即見該案件（渠道顯示「LINE」），可同樣推進狀態

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1024px) | Sidebar 常駐；建案表單 4 欄 grid（`lg:grid-cols-4`）；表格全寬 7 欄 | 完整體驗（`page.tsx:146`） |
| Tablet (768-1023px) | Sidebar 常駐（`md:relative`）；建案表單 2 欄 grid（`md:grid-cols-2`）；內距 `md:px-8` | 表格欄位不變，寬度不足時容器 `overflow-auto` 水平捲動（`page.tsx:126`） |
| Mobile (<768px) | Sidebar 收為抽屜（Hamburger 觸發）；表單單欄堆疊（`grid-cols-1`）；頁首左留 `pl-14` 給漢堡 | 表格水平捲動；🚧 規格建議：mobile 改卡片式列表（對齊技師頁），目前仍為水平捲動表格 |

### 資料更新策略

- 列表：進入頁面載入一次；建案 / 改狀態後手動 `load()` 重新拉取（`page.tsx:90,103`）
- 快取：以 `lib/cache` 包裝 `GET`，寫操作後 `cacheInvalidate('GET:{tenantPath}/cases')`（`page.tsx:85,102`）
- 🚧 未實作：自動輪詢 / WebSocket 即時推送（SLA 逾時不會自動翻新，需手動重整）

---

## [DATA & API]

- **uses_api**: true
- **base path**: 經 `tenantPath("/cases")` 組裝 `/tenants/{tenantId}/cases`（`web/src/lib/api.ts` 提供 `api` + `tenantPath`）
- **endpoints**:
  - GET `/tenants/{tid}/cases` — 進線 Case 列表（operationId `listIntakeCases`）
    - Query（後端支援，前端🚧未接）: `status`, `source_channel`, `limit`（≤200，預設 50）
    - Response: `{ data: IntakeCase[] }`（每筆含衍生 `sla_overdue`）
    - 角色: `require_tenant`（`api/routers/intake_cases_v2.py:49-66`）
  - POST `/tenants/{tid}/cases` — 客服代建 Case（operationId `createIntakeCase`，201）
    - Body: `{ source_channel, summary?, customer_name?, customer_phone?, customer_line_id?, customer_id? }`（前端僅送前 4 項，`page.tsx:79-84`）
    - 角色: `BACKOFFICE_ROLES`（含 customer_service）+ idempotency guard（`intake_cases_v2.py:69-98`）
    - 驗證: `source_channel` 須屬 `line/phone/web/referral`，否則 422（`intake_case_service.py:73-78`）
  - GET `/tenants/{tid}/cases/{id}` — Case 詳情（operationId `getIntakeCase`）— 🚧 前端本頁未使用（無詳情頁，規格建議未來新增 `/admin/cases/[id]`）
  - PATCH `/tenants/{tid}/cases/{id}` — 更新狀態 / 補資訊（operationId `updateIntakeCase`）
    - Body 允許欄位: `status`, `summary`, `customer_name`, `customer_phone`（`intake_case_service.py:151`）；前端僅送 `status`（`page.tsx:101`）
    - 角色: `BACKOFFICE_ROLES`（`intake_cases_v2.py:116-131`）
    - 副作用: status→in_progress 時 `COALESCE` 記 `first_responded_at`（`intake_case_service.py:170-171`）
- **envelope**: 統一 `{ data }`（`intake_case_service.py:148`；list 在 router 層 `{"data": items}`，`intake_cases_v2.py:66`）
- **IntakeCase shape**（前端 interface，`page.tsx:9-21`）: `id, case_number, source_channel, customer_name, customer_phone, summary, status, first_response_due_at, first_responded_at, sla_overdue?, created_at`
- **error_cases**:
  - 前端驗證失敗（三欄全空）: 不送 API，error banner「請至少填寫需求摘要或客戶聯絡資訊」（`page.tsx:71-74`）
  - API 錯誤: 統一格式化 `{errorCode} ({status})：{message}` 顯示於 error banner（`page.tsx:60,92,105`）
  - 跨租戶（403 `CROSS_TENANT_READ` / `CROSS_TENANT_WRITE`）: 走 API 錯誤 banner（後端 guard `intake_cases_v2.py:43-46`）
  - 404 `CASE_NOT_FOUND`: PATCH 不存在案件時後端回 404（`intake_case_service.py:144`），走 error banner
  - 422 `VALIDATION_ERROR`: 非法 `source_channel` / `status`（`intake_case_service.py:74,162`），走 error banner
  - 503 `DB_UNAVAILABLE`: DB 不可用（`intake_case_service.py:72`），走 error banner

---

## [權限可見性]

> ✅ 已實作 — `web/src/lib/rolePolicy.ts:38` + Sidebar 角色過濾 `Sidebar.tsx:241-257`

- **可進入本頁的角色**（rolePolicy prefix `/admin/cases`，`rolePolicy.ts:38`）: `admin`、`operations_manager`、`dispatcher`、`customer_service`
- **Sidebar 可見性**: 上述角色才在「開單流程」群組看到「進線案件」項；其餘角色（如 technician）`canAccessRoute("/admin/cases", role)` 為 false，nav 項與頁面皆不可達（`Sidebar.tsx:250-254`）
- **寫操作授權**（後端二次把關）: 建案 / 更新走 `BACKOFFICE_ROLES`（含 customer_service），讀取走 `require_tenant`；前端角色與後端角色一致（`intake_cases_v2.py:80,126`）
- **跨租戶**: 後端 `_guard_tenant` 確保 path tenantId 與登入租戶一致，否則 403（`intake_cases_v2.py:43-46`）

---

## [EXCEPTION TO GLOBAL RULES]

- 列表使用原生 `<table>` 而非 shadcn/ui `<Table>`（對齊本 repo admin 頁實際慣例，非技師頁規格的 shadcn DataTable）；視覺仍遵循 Design System token（`var(--border)` / `var(--bg-surface)` / `var(--primary)` 等）
- 狀態徽章目前不分色（三態共用 indigo），為已知簡化，視為待補（見 col_status 🚧）
- 其餘完全遵循 Global System Prompt（色彩 token、字級、圓角、間距）

---

## [ACCEPTANCE CRITERIA]

- [x] 頁面標題顯示 Inbox 圖示 +「進線案件（Case）」+ 件數，逾時時顯示紅色 SLA 告警徽章
- [x] 代建表單渠道下拉僅 3 項（電話 / 官網表單 / 熟客介紹），預設「電話」，LINE 不在手動選項
- [x] 三欄（摘要 / 姓名 / 電話）全空時前端阻擋送出並提示
- [x] 建案成功顯示綠 banner（含新案號）、清空欄位、重新載入列表
- [x] 列表 7 欄正確顯示，案號為等寬 `C-NNNNNN`，渠道 / 狀態走中文 label map
- [x] SLA 欄依「結案 / 逾時 / 已回應 / 待回應」四態正確顯示色字
- [x] open 顯示「標記處理中」、in_progress 顯示「結案」、closed 無操作；推進後 reload
- [x] open→in_progress 後端記 first_responded_at（關閉首次回應 SLA）
- [x] loading / empty / error 三態具備（純文字版 + 頂部 error banner）
- [x] 僅 admin / operations_manager / dispatcher / customer_service 可見 nav 與進入頁面
- [ ] 🚧 列表篩選 / 排序 / 分頁 UI（後端已支援 query，前端待接）
- [ ] 🚧 8 渠道完整版（partner 4 渠道 Phase II / M14）
- [ ] 🚧 SLA 倒數顯示與多級距分流分色
- [ ] 🚧 狀態徽章分色（open/in_progress/closed）
- [ ] 🚧 結案二次確認 + per-row 操作 loading 防連點
- [ ] 🚧 Case 詳情頁（`getIntakeCase` 已備，前端未用）
- [ ] 🚧 Mobile 卡片式列表 / loading skeleton / EmptyState 插圖
- [ ] 🚧 列表自動刷新（polling / WebSocket）讓 SLA 逾時即時翻新

---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

- **Upstream**: Sidebar「開單流程 > 進線案件」/ Dashboard 進線量卡片（規劃中）
- **Downstream**: 🚧 Case 詳情頁（未建）；CR-0108 D4 規劃 Case 下可衍生 problem_card / work_order（case_id nullable 關聯，`intake_case_service.py:8`）
- 本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找（A38 待登錄）。
