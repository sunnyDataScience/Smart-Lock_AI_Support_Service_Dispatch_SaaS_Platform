# Assembly Prompt: Admin Dashboard 管理後台儀表板

> Global Brand System v1.0 + Page Spec → 一體化 AI Prompt
> 建立日期：2026-04-21

---

## === GLOBAL PROJECT GUIDELINE (DO NOT OVERRIDE) ===

品牌：電子鎖智能客服與派工平台
角色：資深產品設計師與前端工程師
配色：Primary #2563EB (Trust Blue) / Primary Hover #1D4ED8 / Accent #F59E0B (Amber CTA) / Accent Hover #D97706 / Secondary #1E293B (Sidebar) / BG Page #F8FAFC / BG Surface #FFFFFF / Text Primary #0F172A / Text Secondary #64748B / Border #E2E8F0
語義色：Pending #6366F1 / Assigned #8B5CF6 / Active #3B82F6 / Warning #F59E0B / Success #10B981 / Danger #EF4444
字體：Inter + "Noto Sans TC", sans-serif / Code: JetBrains Mono
字級：Display 32px/700 / H1 28px/700 / H2 24px/600 / H3 20px/600 / Body 14px/400 / Caption 11px/400 / KPI 36px/700
圓角：SM 4px / MD 6px / LG 8px / XL 12px
陰影：SM 0 1px 2px rgba(0,0,0,0.05) / MD 0 4px 6px -1px rgba(0,0,0,0.1) / LG 0 10px 15px -3px rgba(0,0,0,0.1) / Kanban 0 8px 16px rgba(37,99,235,0.15)
Grid：Admin 1440px/12col/24px gap, Sidebar 240px/64px; Tech PWA 480px/1col/16px pad
斷點：Mobile <768px / Tablet 768-1024px / Desktop >1024px; Tech PWA: Mobile <480px
技術棧：Next.js 14 (App Router) + React 19 + shadcn/ui + Tailwind CSS 3.4 + TanStack Query + Zustand + Recharts + @vis.gl/react-google-maps + @dnd-kit/core
語氣：精準、可靠、有溫度。稱呼「你」。按鈕用主動語態。錯誤先說問題再說解法。

### 重要規範
- 所有頁面遵守此設計系統
- 除 EXCEPTION RULES 明確說明外，不准違反
- 元件優先使用 shadcn/ui，不自造輪子

---

## === CURRENT TASK: BUILD ONE PAGE ===

本次任務：根據上方 Global Guideline，設計並實作「Admin Dashboard 管理後台儀表板」。

### [PAGE META]

- **page_name**: Admin Dashboard
- **route_path**: `/dashboard`
- **page_type**: dashboard
- **primary_goal**: 以 KPI Card Dashboard 即時呈現工單量、完工率、逾時工單、在線技師等營運關鍵指標，讓管理者一眼掌握系統運作狀態
- **secondary_goal**: 透過趨勢圖表與最近工單列表，快速發現異常並跳轉至細節頁面處理
- **target_users**:
  - 主要：品牌／經銷商管理員（每日多次查看）
  - 次要：營運主管（每週檢視 SLA 與 AI 準確度趨勢）
- **entry_point**: 登入後預設導向 / 側邊欄點擊「儀表板」/ 點擊左上角 Logo
- **expected_time_on_page**: 30 秒 - 3 分鐘（快速瀏覽 KPI 後進入工單或技師管理）

---

### [STRUCTURE: SECTIONS]

共 6 個主要 Section：

1. **kpi_cards** — 主要 KPI 卡片列
   - section_type: stats_cards
   - section_purpose: 以 4 張 KPI 卡片呈現今日核心營運數據
   - 四張卡片：今日工單數 / 完工率 / 逾時工單 / 在線技師
   - 數值使用 text.kpi（36px/700 Inter）

2. **ai_accuracy_card** — AI 診斷準確率輔助 KPI
   - section_type: stats_cards
   - section_purpose: 呈現 AI 診斷準確率與 SLA 達標率
   - 2 張輔助卡片（AI 準確率 + SLA 達標率），佈局 2 欄等寬（各 6-col）

3. **charts_row** — 趨勢圖表區
   - section_type: charts
   - section_purpose: 左側工單趨勢折線圖 + 右側技師狀態圓餅圖
   - 佈局：左 2/3（8-col）+ 右 1/3（4-col）

4. **recent_work_orders** — 最近工單表格
   - section_type: data_table
   - section_purpose: 顯示最近 10 筆工單摘要，可展開查看詳情

5. **quick_actions** — 快捷操作列
   - section_type: action_bar
   - section_purpose: 提供管理者常用快速操作入口（建立工單、匯出報表、進入派工台）

6. **system_alerts** — 系統警示區
   - section_type: alert_list
   - section_purpose: 顯示需要立即處理的系統層級警示（WebSocket 斷線、SLA 即將違約等）

---

### [SECTION COMPONENT SPEC]

#### Section 1: kpi_cards

- **layout**: 4 欄等寬網格（Desktop 12-col grid 每張 3-col），間距 24px，上方 margin 24px
- **elements**:
  - today_orders: KPICard / required
    - 標題 "今日工單數"
    - 數值使用 text.kpi（36px/700 Inter）
    - 副標 vs 昨日 ±N%（綠色上升箭頭或紅色下降箭頭）
    - 圖標 ClipboardList
    - 卡片背景 #FFFFFF，左側 4px accent border #2563EB
    - 點擊導向 `/work-orders?filter=today`
  - completion_rate: KPICard / required
    - 標題 "完工率"
    - 數值 36px/700 + "%"
    - 副標 vs 昨日 ±N%
    - 圖標 CheckCircle
    - accent border #10B981（綠色）
    - 數值色彩閾值：≥90% 綠色 / 70-89% 琥珀色 / <70% 紅色
  - overdue_orders: KPICard / required
    - 標題 "逾時工單"
    - 數值 36px/700
    - 副標 "佔總工單 N%"
    - 圖標 AlertTriangle
    - accent border #EF4444（紅色）
    - 數值 >0 時數字紅色閃爍動畫（@keyframes blink）
    - 點擊導向 `/work-orders?filter=overdue`
  - online_technicians: KPICard / required
    - 標題 "在線技師"
    - 數值 36px/700 + " / {total}"
    - 副標 "可派遣 N 人"
    - 圖標 Users
    - accent border #F59E0B（Amber）
    - 點擊導向 `/technicians?status=online`
- **states**:
  - default: 白色卡片，圓角 LG (8px)，shadow-sm，左側 4px 色條
  - hover: shadow-md，translateY(-2px) 上移，cursor pointer
  - loading: Skeleton 動畫（標題行 w-24 h-4 + 數值行 w-16 h-10 + 副標行 w-32 h-3）
  - error: 卡片內顯示 "資料載入失敗" + 重試 IconButton，邊框變為 #FEE2E2
  - empty: 數值顯示 "—"，副標顯示 "暫無資料"
  - realtime_update: 數值變更時 scale(1.05) + color pulse 動畫 0.3s ease-out
- **copy_constraints**: KPI 標題最多 6 字；副標最多 15 字；數值最大 5 位數

#### Section 2: ai_accuracy_card

- **layout**: 2 欄等寬（各 6-col），間距 24px，與 kpi_cards 間距 16px
- **elements**:
  - ai_accuracy: KPICard / required
    - 標題 "AI 診斷準確率"
    - 數值 36px/700 + "%"
    - 副標 "近 7 日 / 樣本 N 筆"
    - 圖標 Sparkles
    - accent border #8B5CF6（紫色）
    - 色彩閾值：≥85% 綠色 / 70-84% 琥珀色 / <70% 紅色
  - sla_compliance: KPICard / required
    - 標題 "SLA 達標率"
    - 數值 36px/700 + "%"
    - 副標 "本月目標 95%"
    - 圖標 Shield
    - accent border #2563EB
    - 內含迷你進度條（目標線 95% vs 實際值）
- **states**: 同 kpi_cards 樣式規範

#### Section 3: charts_row

- **layout**: 2 欄非等寬 — 左側 8-col 工單趨勢折線圖 + 右側 4-col 技師狀態圓餅圖，間距 24px
- **elements**:
  - work_order_trend_chart: Recharts `<LineChart>` / required
    - 標題 "工單趨勢"
    - X 軸：日期（預設近 7 天）
    - Y 軸：工單數量
    - 雙折線：新建工單 #2563EB + 完成工單 #10B981
    - 區域填充半透明漸層 `<Area>`
    - 右上角時間範圍切換 Tabs：7 天 / 14 天 / 30 天
    - Tooltip 顯示具體數值 + 日期
    - `<ResponsiveContainer width="100%" height={300}>`
  - technician_status_chart: Recharts `<PieChart>` / required
    - 標題 "技師狀態分佈"
    - 扇區：在線空閒 #10B981 / 執行中 #2563EB / 離線 #94A3B8 / 請假 #F59E0B
    - 中央 `<Label>` 顯示總人數
    - 底部水平圖例 `<Legend>`
    - Hover 扇區放大效果 `activeShape`
- **states**:
  - default: 白色卡片包裹，圓角 LG (8px)，shadow-sm，padding 24px
  - hover: 折線圖 crosshair + tooltip；圓餅圖扇區放大 + tooltip
  - loading: 圖表 Skeleton（矩形佔位 h-[300px] + 閃爍動畫）
  - error: "圖表載入失敗" + 重試按鈕，替代整個圖表區域
  - empty: 折線圖顯示空座標軸 + "暫無資料"；圓餅圖顯示灰色空心圓 + "暫無技師資料"

#### Section 4: recent_work_orders

- **layout**: 全寬資料表格，白色卡片包裹，圓角 LG (8px)，shadow-sm，最多 10 列
- **elements**:
  - section_title: H2 "最近工單" + 右側 `<Link>` "查看全部 →" 導向 `/work-orders`
  - table: shadcn/ui `<Table>` / required
    - 欄位：工單編號 (Mono)、客戶名稱、鎖型型號、狀態 (Badge)、優先度 (Badge)、建立時間 (Caption)、指派技師 (Avatar + Name)
    - 工單編號格式：WO-YYYYMMDD-XXXX
    - 狀態 Badge 色彩：待指派 #64748B / 已指派 #8B5CF6 / 進行中 #3B82F6 / 已完成 #10B981 / 逾時 #EF4444
    - 優先度 Badge：一般 #64748B / 急件 #F59E0B / 緊急 #EF4444
  - expandable_rows: shadcn/ui `<Collapsible>` / optional
    - 展開後顯示：問題摘要、AI 初步診斷、客戶地址
    - 背景 #F8FAFC，左側 3px #2563EB 指示條
  - pagination_info: Caption "顯示最近 10 筆，共 {total} 筆"
- **states**:
  - default: 奇偶列交替背景 #FFFFFF / #F8FAFC
  - hover: 列背景 #EFF6FF（淺藍），cursor pointer
  - loading: 10 列 Skeleton rows
  - error: "工單載入失敗" + 重試按鈕
  - empty: 插圖 + "目前沒有工單記錄" + CTA「建立工單」

#### Section 5: quick_actions

- **layout**: 水平排列按鈕群組，位於 kpi_cards 與 charts_row 之間或頁面右上角
- **elements**:
  - create_order_btn: shadcn/ui `<Button>` variant="default" / required
    - 文字 "建立工單"
    - 圖標 Plus
    - 背景 Primary #2563EB，hover #1D4ED8
    - 點擊開啟建立工單 Modal 或導向 `/work-orders/create`
  - export_report_btn: shadcn/ui `<Button>` variant="outline" / optional
    - 文字 "匯出報表"
    - 圖標 Download
  - dispatch_board_btn: shadcn/ui `<Button>` variant="outline" / optional
    - 文字 "前往派工台"
    - 圖標 LayoutDashboard
    - 點擊導向 `/work-orders/dispatch`
- **states**:
  - default: 按鈕正常顯示
  - loading: disabled + spinner
  - disabled: opacity 50%

#### Section 6: system_alerts

- **layout**: 頁面頂部或 KPI 卡片上方，全寬 Alert 條列
- **elements**:
  - alert_items: shadcn/ui `<Alert>` 陣列 / conditional
    - variant: destructive（嚴重）/ warning（警告）/ default（資訊）
    - 顯示條件：有未處理的系統警示時才出現
    - 範例警示：
      - "有 3 筆工單即將超過 SLA 時限"（warning，點擊導向工單列表）
      - "WebSocket 連線已中斷，資料可能非最新"（destructive）
      - "今日有 2 位技師請假，可派遣人力不足"（warning）
    - 每筆含：圖標 + 訊息文字 + 操作按鈕（查看 / 忽略）+ 關閉 X
- **states**:
  - default: 依嚴重度排序，最多顯示 3 筆，更多收折
  - empty: 不顯示此 Section（不佔空間）
  - dismissed: 關閉後滑出動畫，24 小時內不再顯示同類型警示

---

### [INTERACTION & STATE FLOW]

1. 頁面載入 → 並行請求 `GET /api/v1/dashboard/overview` + `GET /api/v1/dashboard/kpi` + `GET /api/v1/work-orders?limit=10&sort=-created_at` → 各 Section 依序渲染（KPI 優先）
2. WebSocket 連線建立 → 訂閱 `ws://host/ws/dashboard` KPI 即時更新頻道 → KPI 數值變更時觸發 pulse 動畫
3. WebSocket 連線失敗 → 自動降級為 30 秒 polling（指數退避重連 1s → 2s → 4s → 最大 30s）→ 狀態指示器轉為琥珀色
4. 點擊 KPI 卡片「今日工單數」→ `router.push('/work-orders?filter=today')`
5. 點擊 KPI 卡片「逾時工單」→ `router.push('/work-orders?filter=overdue')`
6. 點擊 KPI 卡片「在線技師」→ `router.push('/technicians?status=online')`
7. 圖表時間範圍切換（7天 / 14天 / 30天）→ 重新請求 `GET /api/v1/dashboard/overview?range=7d|14d|30d` → 圖表平滑過渡動畫
8. 點擊工單列展開 → Collapsible 動畫展開顯示 AI 診斷 + 客戶地址
9. 點擊工單編號 → `router.push('/work-orders/{id}')`
10. 點擊 "查看全部" → `router.push('/work-orders')`
11. 手動 refresh → 所有 query invalidation → 短暫 loading 態

---

### [DATA & API]

- **uses_api**: true
- **endpoints**:
  - `GET /api/v1/dashboard/overview` — 儀表板綜合資料（圖表 + 技師分佈），query param `range=7d|14d|30d`
  - `GET /api/v1/dashboard/kpi` — 6 項 KPI 即時數值 + 對比基準值
  - `GET /api/v1/work-orders?limit=10&sort=-created_at` — 最近 10 筆工單
  - `WS /ws/dashboard` — WebSocket，推送 KPI 變更事件 + 新工單通知
- **request_headers**:
  - `Authorization: Bearer {access_token}`
  - `X-Tenant-ID: {tenant_id}`（多租戶隔離）
- **快取策略（TanStack Query）**:
  - KPI: staleTime 30s，WebSocket 即時 invalidation
  - 圖表: staleTime 5min，切換範圍時手動 invalidation
  - 工單列表: staleTime 1min，WebSocket 推送新工單時 prepend
  - visibilitychange 事件 → 全域 query invalidation
- **error_cases**:
  - 網路錯誤 → 頂部 Toast "網路連線異常，資料可能非最新"，使用快取繼續顯示
  - 5xx → 對應 Section inline 錯誤 + 重試按鈕（獨立 Error Boundary）
  - 4xx → 具體錯誤訊息
  - 401/403 → 導向 `/login?redirect=/dashboard`
  - WebSocket 斷線 → 指數退避重連，3 次失敗 → 切換 polling
  - Zod schema 驗證失敗 → console error + Sentry，顯示 "資料異常"

---

### [RWD 行為]

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (>1024px) | Sidebar 240px 展開 + 主區域 12-col grid，KPI 4 欄並排，圖表 8+4 分割 | 完整體驗，所有資訊一目了然 |
| Tablet (768-1024px) | Sidebar 收合 64px + 主區域 8-col grid，KPI 2x2 網格，圖表上下堆疊全寬 | 工單表格隱藏「鎖型型號」欄 |
| Mobile (<768px) | Sidebar 隱藏改為底部 Tab Bar + 單欄堆疊，KPI 全寬堆疊，圖表全寬 | 工單表格改為卡片列表；secondary KPI 收合至可展開區域 |

---

### [ACCEPTANCE CRITERIA]

- [ ] 所有 6 個 Section 功能正常，畫面完整渲染
- [ ] 4 張主要 KPI 卡片數值正確顯示，text.kpi（36px/700）樣式套用正確
- [ ] 2 張輔助 KPI 卡片（AI 準確率、SLA 達標率）正確顯示
- [ ] KPI 數值根據閾值正確變色（綠 / 琥珀 / 紅）
- [ ] 逾時工單 > 0 時紅色閃爍動畫正常觸發
- [ ] KPI 卡片 hover shadow-md + translateY(-2px)，點擊導航至對應列表頁
- [ ] WebSocket 連線成功 → KPI 即時更新 + pulse 動畫
- [ ] WebSocket 斷線 → 30s polling 降級 + 狀態指示器琥珀色
- [ ] 工單趨勢折線圖：雙折線 + 區域填充 + Tooltip + 時間範圍切換（7/14/30 天）
- [ ] 技師狀態圓餅圖：4 狀態 + 中央總數 + 圖例 + hover 放大
- [ ] 最近工單表格 10 筆 + 可展開列 + 狀態 Badge 顏色正確
- [ ] Loading / Error / Empty 三態在所有 Section 均已實作
- [ ] RWD 三斷點（Desktop / Tablet / Mobile）佈局正確
- [ ] Sidebar 展開 240px / 收合 64px / Mobile 隱藏
- [ ] 快捷操作按鈕功能正常
- [ ] 系統警示條正確顯示與關閉
- [ ] API 錯誤時各 Section 獨立 Error Boundary
- [ ] 首次載入完成 < 2 秒
- [ ] 多租戶隔離正確

---

## === EXCEPTION RULES ===

1. **KPI 卡片全寬 Mobile 覆寫**：在 Mobile (<768px) 斷點下，KPI 卡片可使用全寬佈局（override 標準 grid max-width），每張卡片佔滿螢幕寬度減去 16px 左右 padding，確保數值清晰可讀。
2. **KPI 特規字級**：KPI 數值使用 36px/700（text.kpi），超出一般 Design System Body 字級範圍。此特規僅限於 Dashboard KPI 區塊。
3. **閃爍動畫**：逾時工單數值的紅色閃爍動畫（`@keyframes blink`）為此頁面專屬警示效果，其餘頁面不得使用。
4. **Pulse 動畫**：WebSocket 即時更新的 scale + color transition pulse 動畫僅限 Dashboard KPI 卡片使用。

---

## === OUTPUT REQUIREMENTS ===

### Step 1: 結構確認
列出本頁面的 6 個 sections、各 section 的關鍵元件，以及資料流策略：
- kpi_cards → 4 張 KPICard（WebSocket 即時更新 / 30s polling fallback）
- ai_accuracy_card → 2 張輔助 KPICard（同上策略）
- charts_row → LineChart + PieChart（Recharts，staleTime 5min）
- recent_work_orders → Table 10 筆 + Collapsible（staleTime 1min）
- quick_actions → 靜態按鈕群組（無 API）
- system_alerts → Alert 列表（WebSocket 推送）

### Step 2: 設計決策說明
提供 2-3 個關鍵設計決策與理由，例如：
1. KPI 卡片左側色條設計：以 4px accent border 視覺區分各指標類型，搭配語義色建立直覺關聯
2. WebSocket + polling 降級策略：確保資料即時性同時保障可靠性
3. 獨立 Error Boundary：單一 API 失敗不影響全頁，提升系統韌性

### Step 3: 實作方案
Option A: 完整 React/Next.js 程式碼（使用 shadcn/ui + Tailwind）

請產出以下檔案結構：
```
app/(admin)/dashboard/
├── page.tsx                    # 頁面主元件
├── components/
│   ├── KPICard.tsx             # KPI 卡片元件（含 pulse/blink 動畫）
│   ├── KPICardsRow.tsx         # 4 張主要 KPI 容器
│   ├── SecondaryKPICards.tsx   # 輔助 KPI 容器
│   ├── WorkOrderTrendChart.tsx # Recharts 折線圖
│   ├── TechnicianPieChart.tsx  # Recharts 圓餅圖
│   ├── RecentOrdersTable.tsx   # 最近工單表格 + 展開列
│   ├── QuickActions.tsx        # 快捷操作按鈕
│   └── SystemAlerts.tsx        # 系統警示
├── hooks/
│   ├── useDashboardKPI.ts      # TanStack Query + WebSocket hook
│   ├── useDashboardCharts.ts   # 圖表資料 hook
│   └── useRecentOrders.ts      # 工單列表 hook
└── types.ts                    # TypeScript 型別定義
```

### 品質檢查
- [ ] 色彩系統一致性（Primary #2563EB / Accent #F59E0B / BG #F8FAFC / Surface #FFFFFF）
- [ ] 字體層級正確（KPI 36px/700、H1 28px/700、H2 24px/600、Body 14px/400）
- [ ] 元件風格統一（shadcn/ui Table, Button, Badge, Alert, Collapsible）
- [ ] 響應式設計完整（Desktop 12-col / Tablet 2x2 KPI / Mobile 堆疊）
- [ ] 所有狀態已處理（Loading Skeleton / Error + Retry / Empty + CTA / Disabled）
- [ ] 無障礙支援（鍵盤導航 Tab / ARIA labels / 圖表 aria-describedby / 色彩對比 ≥4.5:1）
- [ ] 效能指標達標（LCP < 2s / CLS < 0.1 / 圖表 lazy load / TanStack Query 快取）

---

執行優先順序：Global 規範 > Page 特定需求 > Exception
Assembly 日期：2026-04-21
Brand System 版本：v1.0
