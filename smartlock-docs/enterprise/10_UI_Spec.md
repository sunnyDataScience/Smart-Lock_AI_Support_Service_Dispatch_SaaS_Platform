---
title: "10 UI Spec — 關鍵頁面 UI 規範（四 Portal + 客戶公開頁）"
version: 1.0
status: active
owner: 前端 Lead + UI/UX 設計師（QA / PM 為驗收讀者）
last-updated: 2026-07-07
upstream:
  - smartlock-docs/web/P1/05_architecture_and_design.md
  - smartlock-docs/technician-platform/P1/05_architecture_and_design.md
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P013_Agent_Configuration_Studio_品牌自服務.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P006_四方RBAC模型_enforce.md
---

# 10 UI Spec — 關鍵頁面 UI 規範

> 本文件回答：每個關鍵頁面**有哪些區塊、放什麼元件、四大狀態長什麼樣、如何互動、依賴哪些 API/WS、RWD 如何降級、驗收條件是什麼**。
> 邊界：頁面清單／導覽／URL 結構在 [09_IA.md](./09_IA.md)；元件與 token 內部規格在 [11_Design_System.md](./11_Design_System.md)（本文件只引用元件名）；跨頁流程順序在 [08_User_Flow.md](./08_User_Flow.md)；API 契約在 [16_API_Spec.yaml](./16_API_Spec.yaml) / [17_AsyncAPI.yaml](./17_AsyncAPI.yaml)。

## 1. 文件定位與範圍

前端為單一 Next.js 15 / React 19 codebase（`smartlock-admin`），以 build-time 旗標 `NEXT_PUBLIC_APP_MODE` 塑出 4 個 portal，實質為掛在 App Router 上的 client-side SPA（全 `"use client"`、無 BFF、瀏覽器直連後端 api）：

| Portal | 角色 | Port | API base | 本文件章節 |
|---|---|---|---|---|
| **dispatch**（品牌營運後台）| 品牌營運人員 | :3000 | dispatch api :8001（REST + WS）| §4 |
| **tech**（師傅工作台 PWA）| 簽約師傅——為 **technician-platform 的獨立跨品牌師傅 web**，不進品牌 bundle（ADR-P005）| :3001 | tech api :8002（WS 指 :8001）| §5 |
| **platform**（平台 console）| 平台管理員 | :3003 | platform api :8003 | §6 |
| **landing**（行銷頁，無登入態）| 潛在加盟品牌 / 師傅 | :3002 | :8001 + :8003 | §7 |
| 客戶 token 公開頁 | 終端客戶（無登入，簽章 token）| — | `/track` `/quotes` `/consent` `/scope-change` | §8 |

## 2. 全域 UI 規則

### 2.1 頁面外殼

- **Admin Shell**（dispatch / platform）：Sidebar 240px（tablet 收合 64、mobile hamburger）+ Page Header 64px sticky + Content `max-w-[1200px]`；Provider 嵌套 Theme→Locale→Toast→AuthGuard。
- **PWA Shell**（tech）：Top Bar 56px + 單欄 Card Stack（480px container）+ Bottom Nav 56px + safe-area；底部導航四項：首頁 / 搶單池 / 我的工單 / 帳戶。

### 2.2 四大狀態統一定義（每頁規格卡硬性要求）

| 狀態 | 定義 | 視覺規範 |
|---|---|---|
| **Loading** | 資料抓取中 | skeleton（表格 5 行 / 卡片骨架 / KPI pulse）；**不可空白閃爍** |
| **Empty** | 查無資料 | 插圖 + 說明 + 主要 CTA（如「建立工單」）；**「無資料」與「篩選無結果（附[清除篩選]）」須區分兩種文案** |
| **Error** | 網路 / API 錯誤 | inline 錯誤區 + [重試]；error toast **不自動消失** + 重試入口；表單錯誤 inline 顯示，不得只靠 toast |
| **Permission Denied** | 角色無權（403）| **fail-closed：無權即看不見**，導向該角色安全落點或 403 說明頁。前端 gate（AuthGuard + rolePolicy + appMode）**僅為 UX 呈現層，真正授權由後端 `role_required` enforce**（四方 RBAC，ADR-P006）|

### 2.3 RWD 三斷點總則（Admin 系頁面）

Desktop（> 1024px）全功能 → Tablet（768–1024px）Sidebar 收合、表格隱藏次要欄 → Mobile（< 768px）表格轉卡片列表、篩選器收折為 Sheet、Modal 轉全螢幕 bottom sheet。Tech portal 恆為單欄 mobile-first，無斷點變化。

### 2.4 URL query 同步

列表篩選、視圖切換、分頁一律同步 URL query string（如 `?view=kanban&status=created,assigned&page=2`）；Tab 對應 URL hash——重整與分享連結不遺失狀態。

### 2.5 即時更新與靜默降級

- WebSocket 訂閱（`lib/realtime.ts`）：JWT 走 query param；斷線 backoff 重連 1s→2s→5s→10s→30s；**base 未配置或斷線一律靜默降級**——頁面照常以 REST fetch 運作（30s staleTime GET cache），不噴錯、不阻塞。
- WS 斷線期間列表降級 polling（工單 30s / 技師位置 15s）；頁面右上以 RealtimeStatusBar（狀態點 + 最後更新時間）呈現連線狀態。
- 主要頻道：`/realtime/work-orders/{id}`、`/realtime/dispatch-queue`、`/realtime/pool/{tech_id}`、`/realtime/sla-alerts`、`/realtime/notifications/{user_id}` 等 10 頻道（operationId 見 [17_AsyncAPI.yaml](./17_AsyncAPI.yaml)）。

## 3. 頁面規格卡格式

每頁依 8 段撰寫（本文件依重要度詳略）：

1. **PAGE META**：page_name / route_path / page_type / ia_pages / openapi_ops / asyncapi_ops / primary_goal / target_users / entry_point
2. **STRUCTURE: SECTIONS**：由上至下 5–8 個功能區塊（type + purpose）
3. **SECTION COMPONENT SPEC**：layout / elements（元件名引用 11_Design_System）/ **states（default / hover / loading / error / empty / disabled + Permission Denied）** / copy_constraints
4. **INTERACTION & STATE FLOW**：主要互動流程 + 資料更新策略
5. **RWD**：三斷點行為差異表
6. **DATA & API**：endpoints + error_cases（網路 / API / 權限不足）
7. **EXCEPTION**：違反全域規範之處（最小化）
8. **ACCEPTANCE CRITERIA**：驗收 checklist

## 4. dispatch portal（品牌營運後台）

### 4.1 營運儀表板（`/dashboard`，A1）

- **Sections**：KPI 卡列（KPICard×4：今日進線 / 待指派工單 / SLA 風險 / 完工率，`grid-cols-4`→2→1）→ SLA 告警帶（訂閱 `subscribeSlaAlerts`）→ 近期工單表（DataTable 精簡 6 欄）→ 快捷操作（前往派工台 / 建立工單）。
- **API**：`listWorkOrders` + WS `/realtime/sla-alerts`。四大狀態：KPI pulse skeleton；空態「今日尚無進線」；錯誤 inline + 重試；403 導登入。

### 4.2 對話列表 / 詳情（`/conversations`、`/conversations/[id]`，A2/A3）

- 列表：搜尋 + 通道/狀態篩選 + ConversationTimeline 入口；詳情：LINE 對話時間軸（文字 / 圖片 / AI 回覆標記）+ 右欄問題卡摘要（ProblemCardViewer）+ 轉真人 / 建工單操作。
- **API**：`listConversations`、`getConversation`。空態「尚無對話」；詳情錯誤 inline；未授權角色（如 accountant）fail-closed 不見此選單。

### 4.3 問題卡列表 / 詳情（`/problem-cards`、`/problem-cards/[id]`，A4/A5）

- 結構化診斷卡：品牌 / 型號 / 故障分類 / 信心分數；列表支援品牌與故障類別篩選；詳情連回原對話（A3）與 AI 診斷推理（A32）。API：`listProblemCards`。

### 4.4 工單列表（`/work-orders`，A11）

- **PAGE META**：list 型；openapi_ops `listWorkOrders, assignWorkOrder, listDispatchCandidates`；asyncapi `subscribeWorkOrderUpdates`。
- **Sections**：篩選工具列（13 狀態多選 Select + 優先度 + 技師 combobox + 日期範圍 + 搜尋 300ms debounce + 清除篩選）→ **DataTable 工單 10 欄**（規格見 11_Design_System §3.7：批次選取 / 工單號 mono link / 客戶 / 鎖具型號 / 問題分類 / StatusBadge / SLACountdown / 指派技師 / 建立時間 / ⋮ 操作）→ 批次操作列（勾選浮出「已選 N 項 — [批次指派] [匯出]」）→ 分頁器。
- **互動**：預設排序 優先度 DESC → SLA ASC；row click 開詳情；「指派」開手動指派 Modal（§4.6 Section 6）；批次指派後顯示成功 / 失敗摘要。
- **四大狀態**：Loading 5 行 skeleton；Empty 區分「目前沒有工單 + [建立工單]」與「找不到符合條件 + [清除篩選]」；Error inline + 重試；403 fail-closed。
- **RWD**：tablet 隱藏問題分類 / 建立時間欄；mobile 轉 WorkOrderCard List。
- **驗收**：13 狀態篩選正確映射 6 色群；SLA 欄用 SLACountdown 非純文字；篩選同步 URL；批次指派回饋完整。

### 4.5 工單詳情（`/work-orders/[id]`，A12）

- **Sections**：Header（工單號 mono + StatusBadge + SLACountdown lg + 主操作：指派/重新指派、變更狀態、取消 danger）→ **5 Tab（underline）：基本資訊 / 服務紀錄 / 零件 / 照片（PhotoGallery + lightbox）/ 時間軸（WorkTimeline，事件溯源自 `work_order_events`）**→ 右欄客戶卡 + AI 診斷摘要（問題分類 + 信心指數 + AIRecommendationBadge）。
- 工單狀態機值域由 Flow DSL 宣告（[../00_platform/P1/07_workorder_platform_design.md](../00_platform/P1/07_workorder_platform_design.md)）；產業欄位（brand/model/serial/warranty）由 `field_metadata` 驅動 DynamicForm/Table 渲染 🔜 規劃中，現行為固定欄位表單。
- **API**：`getWorkOrder`、`assignWorkOrder`、`listDispatchCandidates`；WS `subscribeWorkOrderUpdates`（時間軸新事件 slide-in + 2s 高亮）。Tab 對應 URL hash、lazy load。
- 客訴升級：ComplaintEscalationIndicator（anger_level 警示 + SLA 倒數）常駐 Header 下方（發生時）。

### 4.6 派工看板 / 派工台（A11 看板視圖 + A28 派工佇列；實際 route [待確認]，以 IA `/work-orders` + `/admin/dispatch-queue` 為錨）

平台核心頁。**8 Sections**：

1. **view_mode_switcher**：Tabs（列表 / 看板 / 地圖），active 存 URL `?view=list|kanban|map`，切換 content fade-in 150ms。
2. **filter_toolbar**：狀態（全部/待指派/已派工/進行中/已完工/異常）+ 優先度 + 技師（searchable multi）+ 日期範圍（預設今日）+ 搜尋（「搜尋工單編號、客戶名稱…」300ms debounce）+ 清除篩選；有條件時顯示 badge 數字；mobile 收折為 Sheet。
3. **list_view**：同 §4.4 DataTable + SLA 倒數三級（綠 > 2h / 琥珀 30min–2h / 紅 + pulse < 30min）+ 批次操作 + 分頁（每頁 20）。
4. **kanban_view**：KanbanBoard 5 欄（待指派 #6366F1 / 已派工 #8B5CF6 / 進行中 #3B82F6 / 已完工 #10B981 / 異常 #EF4444，欄頂數量 badge）；KanbanCard：工單號 mono + 客戶名（≤ 8 字）+ 鎖具型號 + 技師 Avatar 24px + SLA badge + 優先度圓點（急件琥珀 / 緊急紅）。**拖曳規則**：僅允許合法狀態轉換（轉換表見 11_Design_System §3.8）；拖曳中 `shadow.kanban` + opacity 0.9 + scale(1.02)；目標欄藍色虛線 placeholder；**Optimistic UI**——放下即移動 → `PATCH /work-orders/{id}/status` → 失敗 rollback + Toast「狀態更新失敗，已復原」；**待指派→已派工放下時自動彈出手動指派 Modal**。拖曳函式庫選型 [待確認]。
5. **map_view**：左 40% 工單列表（按距離排序）+ 右 60% 地圖分割（分割線可拖曳）；紅 pin 未指派工單（點擊 popup + [指派]）、藍 pin 技師即時位置（GPS，空閒實心 / 執行中半透明 / 離線灰）、cluster 聚合、選中時顯示路線虛線；點列表卡 → 地圖飛至 + 高亮；拖紅 pin 至技師 pin → 快速指派確認 Dialog。地圖函式庫選型 [待確認]。
6. **manual_assign_modal**：Dialog 600px；工單摘要卡 + **Top 5 推薦技師**（`GET /work-orders/{id}/candidates`，不快取）：Avatar + 姓名 + SkillBadge 陣列 + 第 1 名 ⭐ AI 推薦 Badge + 綜合評分（百分制）+ 評分細項 Collapsible（距離 / 技能匹配 / 歷史評價 / 負載平衡）+ 目前狀態（空閒綠 / 執行中藍 +「預計 HH:MM 完工」/ 離線灰不可選）+ 預估到達；備註 Textarea；[確認指派]（primary，未選 disabled）/ [取消]。states：loading 5 列 skeleton / error「無法取得推薦技師」+ 重試 / empty「目前無可用技師」/ submitting spinner / success 關閉 + Toast「已成功指派 {技師} 至 {工單}」。
7. **order_detail_drawer**：右側 Sheet 480px——不離開派工台檢視工單完整詳情 + Timeline + 操作。
8. **realtime_status_bar**：WS 狀態點 + 最後更新 HH:MM:SS + 在線技師 N 人。

- **狀態映射**：13 態 → 6 色群 → 5 欄（映射表見 [11_Design_System.md](./11_Design_System.md) §2.2 / §3.8）。
- **DATA & API**：`GET /api/v1/work-orders`（page/limit/status/priority/technician_id/date_from/date_to/search/sort/group_by）、`PATCH /work-orders/{id}/status`、`PATCH /work-orders/{id}/assign`、`GET /work-orders/{id}/candidates`、`GET /technicians/locations`；WS 推送工單狀態變更 / 新工單 / 技師位置 / SLA 預警。header：`Authorization: Bearer` + `X-Tenant-ID` + `Idempotency-Key`（mutation）。error_cases：拖曳失敗 rollback；指派失敗 Modal 保持 + inline error + 重試；地圖失敗 fallback 靜態圖 + 重試；WS 斷線降級 polling（30s / 15s）。
- **RWD**：Desktop 三視圖全開（Kanban 全視口寬）；Tablet 隱藏看板 Tab、地圖改上下分割；Mobile 僅列表（刻意降級）。
- **EXCEPTION**：Kanban 突破 1440px max-width 用全視口寬（欄最小 240px 水平捲動）；地圖分割突破 12-col grid 用 40/60 百分比。
- **驗收**（節錄）：三視圖切換 + URL 同步；合法拖曳限制；Optimistic UI + rollback；SLA 三級色正確；Top 5 候選 + AI Badge + 評分細項；Kanban 100+ 卡不卡頓、地圖 50+ pin 正常；拖曳有鍵盤替代；Loading/Empty/Error/Permission Denied 全 section 覆蓋。
- **A37 派工人工介入**（`/admin/dispatch-manual`）：技師 3 次拒單後的人工派工佇列——DispatchAttemptTimeline（1–3 次嘗試 + match score + 拒單原因）+ DispatchCandidateList 綜合分排序 + `escalateWorkOrder` 升級操作。

### 4.7 技師管理（`/technicians`、`/technicians/[id]`，A13/A14；子頁 A25 排班 / A26 技能 / A27 結算）

- 列表：技師卡（Avatar + 狀態圓點 + SkillBadge + 評分 + 今日負載）；地圖模式（TechnicianMap）。詳情 4 Tab：個人資料 / 技能認證 / 排程 / 績效。
- **A25 排班**：TechnicianScheduleCalendar 月/週曆（拖放選時段、衝突警告——Flow 14 排班衝突入口）。**A26 技能認證**：SkillCertificationForm（證書上傳 + 到期提醒，SkillBadge 到期指示）。**A27 結算明細**：SettlementBreakdown（分潤 + 獎勵 + 扣款 + 墊付）。
- 資料歸屬：技師身分 / 技能 / 授權 / 認證 / 排班 / 評分主檔屬 technician-platform（`lock_tech` 單一真相，經 OHS API 查詢；品牌不直連技師庫，ADR-P004）；本 portal 呈現品牌視角的授權技師子集。佣金邊界依 ADR-P014：per-job 計費屬品牌派工平台（§4.8），跨品牌結算 / 對帳 / payout 主體屬技師平台（§5.5）。

### 4.8 帳務 / 結算（`/accounting`，A15）與治理審批（A17 / A21 / A22）

- **A15 帳務**：KPI 摘要（本月營收 / 待收 / 墊付）+ QuotationBuilder（品牌 × 鎖型 × 工項報價矩陣 + 議價記錄）+ ReconciliationTable（技師 × 月份對帳，含墊付 / 結算）+ 發票 / 支付狀態表。
- **A17 退款審批**（`/admin/refunds`）：RefundApprovalWorkflow Modal——**雙簽 + PIN + 會計憑證**；WS `subscribeRefundEvents`；提交 `submitRefundDecision`。
- **A21 保固索賠**（`/admin/warranty-claims`）：WarrantyClaimModal（保固審核 + 技師扣罰雙簽 + 返工工單自動建立）。
- **A22 爭議仲裁**（`/admin/disputes`）：DisputeEvidencePanel 證據時間軸（對話 + 工單狀態 + 客戶送審）+ 仲裁決議表單；WS `subscribeDisputeEvents`。
- 四大狀態同 §2.2；金額一律千分位 + tabular-nums；破壞性決議（駁回 / 扣罰）用 danger + 二次確認。

### 4.9 知識庫（`/knowledge-base/*`，A6–A10）

3 Tab：**案例庫**（A6/A7，case_entries 列表 + 編輯 Modal）/ **手冊管理**（A8，manual_chunks 來源與版本）/ **SOP 審核佇列**（A9/A10，SOPReviewPanel 雙欄：左草稿右原始對話，核准 / 駁回 / 採納）。KnowledgeSearch 支援全文 / 語意切換。知識精煉 draft→審核→寫入流程遵循 ADR-P001（HITL），上游詳見 [../knowledge-refinery/](../knowledge-refinery/)。

### 4.10 進階治理（A18 RBAC / A20 稽核 / A19 庫存）

- **A18**（`/admin/roles`）：PermissionMatrix（功能 × CRUD × 資源限定）+ TemporaryGrantPanel（臨時授權 7 天上限 + 雙簽）；矩陣呈現對齊四方 RBAC 模型（ADR-P006），**前端僅呈現、enforce 在後端**。
- **A20**（`/admin/audit-events`）：AuditEventRow 可展開列（before/after JSON diff + PII 遮蔽）+ 匯出。
- **A19**（`/admin/inventory`）：庫存列表 + InventoryLowStockBanner 低庫存告警（WS `subscribeLowStockAlerts`）。

### 4.11 KPI 報表群（A29–A31，`/admin/reports/*`）

KPI 儀表板（KPIFunnelChart 轉換漏斗：對話→工單→完工）/ 技師排行榜（TechnicianRankingTable 可下鑽）/ 營收報表；ReportScheduleForm 排程匯出（cron + 多格式 + 收件人）。圖表用 recharts；數字 tabular-nums。

### 4.12 客戶主檔 / AI 診斷檢視（A23/A24/A32/A33）

- 客戶列表 + 詳情 5 Tab（基本 / 設備 DeviceStatusCard / 工單歷史 / 對話 / 帳務）。
- **A32 AI 診斷推理**（`/admin/diagnostics/[conversation_id]`）：DiagnosticTraceViewer——L1/L2/L3 推理鏈視覺化 + 信號矩陣；SSE `subscribeDiagnosticStream` 逐步渲染（SSE 未配置時靜默降級為一次性載入）。
- **A33 SOP 績效儀表板**：SOP 命中率 / 採納率趨勢。

### 4.13 Agent Configuration Studio（🔜 規劃中，依 ADR-P013）

品牌 dispatch web 的**自服務調校介面**，三大面板（Casdoor 租戶 Admin 角色限定；所有變更版本化 + audit）：

1. **Skill Registry**：集中 skill 庫（Agent Skills 標準 SKILL.md，版本化）匯入清單 + per-brand 啟用集開關 + **兩層編輯 UI**——「受保護層」（escalation 規則、domain-safety、合規語氣、租戶邊界）以鎖定圖示 + 唯讀樣式呈現、**不可編輯不可移除**；「客製層」（品牌語氣、產品重點、FAQ、開場白）可編輯。受保護的 `locksmith-cs-sop`（domain-safety）品牌不可破壞。
2. **RAG 知識庫權限管理**：RAG Source Registry 目錄（品牌自有 `manual_chunks` / `case_entries` + 共享產業語料）逐項 開/關 + 優先序拖曳排序；**跨租戶隔離為平台鎖死項**——UI 顯示為不可 override 的鎖定列（tooltip 說明 enforce 於 MCP-RAG 查詢層）。
3. **系統提示詞**：客製層編輯器 + 版本列表 + diff 檢視 + 一鍵回滾 + **OPIK eval gate**——改動送出前跑前後比對，回歸不過則擋下或告警；高風險改動（接近受保護邊界）觸發選配 HITL 審核佇列。

四大狀態：eval 執行中為 blocking loading（含進度）；eval 失敗顯示回歸差異報告 + [仍要送審（HITL）]；非 Admin 角色 fail-closed 不見此選單。

### 4.14 租戶設定 / 品牌客製 / 超管（A34–A36，🔜 規劃中）

- **A34** 租戶設定 5 Tab（含 ApiKeyManager：B2B API Key 建立 / 輪替 / 撤銷，Masked Prefix）。**A35** 品牌客製：BrandPreviewSandbox（Admin + LINE Flex 並排即時預覽；白標 token 覆蓋見 11_Design_System §2.11）。**A36** 超管平台：TenantSwitcher + 租戶列表 / 開通 / 退場。

## 5. tech portal（technician-platform 獨立師傅 web，PWA）

全站規則：480px 單欄 + Bottom Nav + Bottom Sheet + 地圖全螢幕；按鈕一律 lg（44px）；下拉重新整理；**離線優先**——OfflineQueueIndicator 常駐、操作入離線佇列上線自動同步。工單資料讀取自技師工作台工單投影（Kafka-fed read-model，欄位最小化：摘要 / 地址 / 狀態 / 時窗，ADR-P014——師傅 web 不直連品牌庫）。

### 5.1 儀表板（`/home`）

今日工單卡堆疊 + 收入摘要 + 排班快捷；WS 派工到手推播（dispatch Toast + 震動）。

### 5.2 搶單池（`/pool`，T1）

- CasePoolCard 卡片流：地址（模糊化至路段）+ 品牌型號 + 報酬 + 距離 + 時窗 + **[一鍵接單]（cta）** + 左滑略過手勢；地圖模式全螢幕 + BottomSheet 三段。
- **API**：`listWorkOrderPool`、`acceptWorkOrder`；WS `subscribeTechnicianPool`（新單 slide-down + 震動）。接單成功卡片飛入「我的工單」；被他人搶走 fade-out +「此單已被接走」。
- 四大狀態：Empty「目前沒有可接工單，開啟通知第一時間收到新單」；Error inline + 重試；未通過認證（KYC）的技師顯示鎖定卡 + 導認證頁（fail-closed）。

### 5.3 我的工單 + 完工回報（`/my-orders`、`/my-orders/[id]`，T2/T3）

- 列表：進行中 / 已完成 Tab + WorkOrderCard（左邊框 SLA 色帶）。
- 詳情：狀態進度條（接受→出發→到場→施工→完工）+ 一鍵狀態推進（cta 大按鈕：出發 / 到場 / 開始施工）+ 客戶聯絡（電話 / 導航）+ **CompletionReportForm**（檢核清單 / 零件 / 照片 ≥ 3 張 / 功能測試 / 簽名；草稿 30s 自動存 IndexedDB；離線可填、上線同步）。
- **API**：`getWorkOrder`、`completeWorkOrder`、`submitWorkOrderSignature`；WS `subscribeWorkOrderUpdates`。

### 5.4 工單 6 子流程（T5–T11）

| 路由 | 子流程 | 關鍵 UI |
|---|---|---|
| `/my-orders/[id]/scope-change`（T5）| 範圍變更申請 | 變更項目表單 + 費用試算 + 客戶同意流程（連 §8 `/scope-change`）|
| `/my-orders/[id]/material-request`（T6）| 缺料回報 | 零件 combobox + 數量 + 工單轉 `material_pending` |
| `/my-orders/[id]/delay`（T7）| 延遲通知 | 原因 + 新預計時間 → 觸發客戶通知 |
| `/my-orders/[id]/door-check`（T8）| 門面外觀檢核 | 拍照比對（施工前必拍）|
| `/my-orders/[id]/signature`（T9）| 雙方電子簽章 | SignaturePad ×2（技師 / 客戶）+ SHA-256 存證 |
| `/my-orders/[id]/reschedule`（T11）| 改期日曆 | RescheduleCalendarModal（客戶可用時段提示 + 衝突警告；`proposeReschedule`）|

### 5.5 帳戶 / 排班 / 對帳（`/account`、`/account/schedule`，T4/T10）

個人資料 + SkillBadge 牆 + 認證狀態（KYC / certification 到期提醒）/ 排班設定（`getTechnicianAvailability`）/ **跨品牌對帳**：技師平台為結算主體（ADR-P014）——單一 statement 聚合各品牌佣金 + payout 紀錄。

## 6. platform console（平台方 console，R1 骨架）

- **儀表板**：平台級 KPI（租戶數 / 活躍技師 / 派工量）。
- **品牌申請審核**：landing 進線的品牌申請列表 + 核准開通（🔜 建立 / 編輯 / License 管理為規劃中補齊項）。
- **師傅審核**：跨租戶技師註冊審核（KYC 文件檢視 + 核准 / 駁回；🔜 認證管理進階功能規劃中）。
- **公開申請頁**：無登入品牌申請表單（直打 platform api :8003）。
- 路由前綴 `/platform/*`；**deny-by-default**（未列角色一律拒絕）；未登入導 `/platform/login`。

## 7. landing portal（`/`，無登入態）

一頁式行銷：Hero + 產品能力區 + **雙 CTA**——[成為合作師傅]（外導 tech portal `/tech-register`）+ [品牌申請加盟]（表單直打 platform api）；無 AuthGuard token 檢查（公開頁）；表單提交四狀態（submitting / success 落點 / error inline / rate-limited 提示）。

## 8. 客戶 token 公開頁（無登入，簽章 token 存取）

| 路由 | 用途 | 關鍵 UI |
|---|---|---|
| `/track` | 工單進度追蹤 | 狀態進度條 + 技師到達預估 + 技師卡（姓名 / 評分；電話遮蔽）|
| `/quotes` | 報價確認 | 報價明細（quote_line_items）+ [同意報價] cta + 議價留言 |
| `/consent` | 施工同意 | 同意條款 + SignaturePad |
| `/scope-change` | 範圍變更確認 | 原報價 vs 新報價 diff + 同意 / 拒絕 |

規則：token 失效 / 過期顯示專屬說明頁（「連結已失效，請聯絡客服」），**不得**導登入頁；不渲染任何營運導覽；行動裝置優先（同 Tech PWA grid）；改期邀請（Flow 11 客戶 RSVP）由 LINE Flex 訊息深連結進入 `/track` 附時段選擇——LINE 對話端版型屬 agent 系統範圍，非本文件範圍。

## 9. 全域錯誤與離線頁

| 觸發 | 頁面 / 元件（對應真實檔）| 內容與動作 |
|---|---|---|
| 路由不存在 / `notFound()` | `src/app/not-found.tsx` | FileQuestion 64px 灰 + H1「頁面不存在」+ [返回上一頁] + [返回儀表板] |
| segment 拋錯 | `src/app/error.tsx` | AlertCircle + H1「發生錯誤」+ **error.digest（mono、可選取複製）** + [重試]（呼叫 `reset()`）+ [返回儀表板]；開發環境 `<details>` 展開 stack、生產僅 digest |
| root layout / provider 崩潰 | `src/app/global-error.tsx` | 自帶 `<html><body>` + 內聯樣式（不依賴 globals.css / next/font）+「系統發生嚴重錯誤」+ [重新載入] |
| `navigator.onLine=false` | `NetworkErrorBanner`（layout 掛載）| fixed top 紅橙橫幅「網路連線中斷，正在嘗試重連...」；恢復顯示綠色「已恢復連線」3s 自動消失；SSR-safe（mounted flag）|
| PWA 完全離線 | `/offline`（G2，Service Worker 靜態快取）| 「目前離線」大字 + [重新嘗試]（指數退避 5s→10s→30s→60s→300s 自動重試）+ **離線佇列摘要（未送出操作不會丟）** + 可離線瀏覽頁清單 + 今日工單快取（技師端）+ 上次同步時間 |
| 全域通知 | `/notifications`（G1）+ header NotificationBell | NotificationInbox：Tab（全部 / 未讀 / 已讀 / 已存檔）+ 類型 filter chips（工單 / 退款 / 爭議 / RBAC / 庫存 / 系統）+ 時間倒序卡片 + 複選批量（已讀 / 存檔）+ 深連結回來源頁；WS `subscribeUserNotifications` |

驗收：生產不洩漏 stack；global-error 不依賴外部 CSS；Banner 在路由切換間保持；離線頁展示佇列數。

## 10. 驗收與可及性總表 + 頁面索引

### 10.1 每頁共通驗收 checklist

- [ ] 所有 Section 實作 default / hover / loading / error / empty（+ disabled 如適用）
- [ ] **四大狀態**（Loading / Empty / Error / Permission Denied）覆蓋，Permission Denied fail-closed
- [ ] RWD 三斷點符合本文件定義；Tech 頁觸控目標 ≥ 44px
- [ ] 篩選 / Tab / 分頁同步 URL；重整不遺失
- [ ] WCAG 2.2 AA：對比達標、鍵盤可達、focus 可見、狀態三重指示、`prefers-reduced-motion`
- [ ] WS 斷線靜默降級不阻塞頁面；error toast 不自動消失
- [ ] 效能：列表虛擬化（大資料集）、圖表 / 地圖 lazy load；FCP 目標 [待確認]、Playwright E2E 覆蓋率門檻 [待確認]

### 10.2 頁面 ↔ IA 索引（52 頁摘要；完整對照見 [09_IA.md](./09_IA.md)）

| 群組 | IA 頁 | 本文件章節 |
|---|---|---|
| 認證 | A0 `/login`、T0 `/tech-login` | §2.1（Shell）|
| 客服閉環 | A1–A10、A16 | §4.1–§4.3、§4.9 |
| 派工閉環 | A11、A12、A13/A14、A28、A37 | §4.4–§4.7 |
| 財務治理 | A15、A17–A22 | §4.8、§4.10 |
| 客戶與 AI 診斷 | A23、A24、A32、A33 | §4.12 |
| 技師詳細管理 | A25–A27 | §4.7 |
| 報表 | A29–A31 | §4.11 |
| Agent Studio | 🔜（route 待 IA 編列）| §4.13 |
| 多租戶 🔜 | A34–A36 | §4.14 |
| 師傅端 | T1–T11 | §5 |
| 平台 console | R1 骨架 | §6 |
| 客戶公開頁 | `/track` `/quotes` `/consent` `/scope-change` | §8 |
| 全域 | G1 `/notifications`、G2 `/offline`、G3 error boundaries | §9 |

---

*10_UI_Spec v1.0 · 2026-07-07 · 上游：smartlock-docs web/P1、technician-platform/P1、00_platform/P1/07、ADR-P006 / P013 / P014*
