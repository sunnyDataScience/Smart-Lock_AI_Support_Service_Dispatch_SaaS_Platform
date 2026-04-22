# Assembly Prompt: 財務結算管理

> Global Brand System v1.0 + Page Spec → 一體化 AI Prompt
> 建立日期：2026-04-21

---

## === GLOBAL PROJECT GUIDELINE (DO NOT OVERRIDE) ===

你是「電子鎖智能客服與派工平台」的資深產品設計師與前端工程師，負責維護整個專案的設計一致性。

### 核心設計系統

- 品牌：電子鎖智能客服與派工平台
- 角色：資深產品設計師與前端工程師
- 配色：Primary #2563EB (Trust Blue) / Primary Hover #1D4ED8 / Accent #F59E0B (Amber CTA) / Accent Hover #D97706 / Secondary #1E293B (Sidebar) / BG Page #F8FAFC / BG Surface #FFFFFF / Text Primary #0F172A / Text Secondary #64748B / Border #E2E8F0
- 語義色：Pending #6366F1 / Assigned #8B5CF6 / Active #3B82F6 / Warning #F59E0B / Success #10B981 / Danger #EF4444
- 字體：Inter + "Noto Sans TC", sans-serif / Code: JetBrains Mono
- 字級：Display 32px/700 / H1 28px/700 / H2 24px/600 / H3 20px/600 / Body 14px/400 / Caption 11px/400 / KPI 36px/700
- 圓角：SM 4px / MD 6px / LG 8px / XL 12px
- 陰影：SM 0 1px 2px rgba(0,0,0,0.05) / MD 0 4px 6px -1px rgba(0,0,0,0.1) / LG 0 10px 15px -3px rgba(0,0,0,0.1)
- Grid：Admin 1440px/12col/24px gap, Sidebar 240px/64px
- 斷點：Mobile <768px / Tablet 768-1024px / Desktop >1024px
- 技術棧：Next.js 14 (App Router) + React 19 + shadcn/ui + Tailwind CSS 3.4 + TanStack Query + Zustand + Recharts + @vis.gl/react-google-maps + @dnd-kit/core
- 語氣：精準、可靠、有溫度。稱呼「你」。按鈕用主動語態。錯誤先說問題再說解法。

### 重要規範
- 所有頁面遵守此設計系統
- 除 EXCEPTION RULES 明確說明外，不准違反
- 元件優先使用 shadcn/ui，不自造輪子

---

## === CURRENT TASK: BUILD ONE PAGE ===

本次任務：根據上方 Global Guideline，設計並實作「財務結算管理」頁面。

### [PAGE SPECIFICATION]

# Page-Level Prompt: 財務結算管理

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 財務結算頁面整合技師結算、發票管理與營收報表，為平台營運的核心財務中樞。

---

## [PAGE META]

- **page_name**: 財務結算管理 Accounting & Settlement
- **route_path**: `/accounting`
- **page_type**: tabbed_dashboard (list + charts)
- **primary_goal**: 管理技師結算流程、追蹤發票付款狀態、呈現營收數據分析
- **secondary_goal**: 提供匯出功能支援財務報表與稅務申報
- **target_users**:
  - 主要：平台財務管理員（每日使用）
  - 次要：平台管理員（每週檢視營收報表）
- **entry_point**: 左側導覽列「財務管理」/ Dashboard 營收 KPI 卡片點擊
- **expected_time_on_page**: 5-15 分鐘（結算作業）、2-5 分鐘（報表檢視）

---

## [STRUCTURE: SECTIONS]

1. **page_header**
   - section_type: header_bar
   - section_purpose: 頁面標題與 Tab 導覽

2. **tab_navigation**
   - section_type: tabs
   - section_purpose: 切換三大功能區塊（結算管理 / 發票管理 / 營收報表）

### Tab 1 — 結算管理

3. **settlement_period_selector**
   - section_type: filter_controls
   - section_purpose: 選擇結算月份與結算週期

4. **settlement_table**
   - section_type: data_table
   - section_purpose: 技師結算清單，含批次操作

5. **settlement_detail_modal**
   - section_type: modal_detail
   - section_purpose: 單筆結算明細，逐工單佣金與獎懲明細

### Tab 2 — 發票管理

6. **invoice_filter_bar**
   - section_type: filter_controls
   - section_purpose: 篩選發票狀態與搜尋

7. **invoice_table**
   - section_type: data_table
   - section_purpose: 發票列表，含付款狀態追蹤與重試

### Tab 3 — 營收報表

8. **revenue_kpi_cards**
   - section_type: stats_cards
   - section_purpose: 四大營收關鍵指標

9. **revenue_charts**
   - section_type: charts_group
   - section_purpose: 多維度營收圖表視覺化

10. **export_controls**
    - section_type: action_bar
    - section_purpose: 資料匯出按鈕

---

## [SECTION COMPONENT SPEC]

### Section: page_header

- **layout**: 全寬單列，`flex justify-between items-center`
- **elements**:
  - page_title: H1 / required / "財務結算管理"
  - last_updated: Text Caption / required / "最後更新：{相對時間}" / icon: RefreshCw
- **states**:
  - default: 顯示標題與更新時間
- **copy_constraints**: 標題固定文案

### Section: tab_navigation

- **layout**: 全寬 Tab bar，shadcn/ui `<Tabs>`，底部分隔線 `border-b border-gray-200`
- **elements**:
  - tab_settlement: Tab / required / icon: Wallet / "結算管理" / 預設選中
  - tab_invoices: Tab / required / icon: FileText / "發票管理" / 逾期發票數 >0 時顯示紅色圓點通知
  - tab_revenue: Tab / required / icon: BarChart3 / "營收報表"
- **states**:
  - active: 選中 Tab 底部 2px Primary 色 `border-b-2 border-[#2563EB] text-[#2563EB]`
  - inactive: `text-gray-500 hover:text-gray-700`
  - badge: 發票 Tab 有紅色通知點時 `relative` + 右上角 `absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full`
- **copy_constraints**: Tab 名稱最多 6 字

---

### Tab 1: 結算管理

### Section: settlement_period_selector

- **layout**: 單列水平排列，`flex items-center gap-4 p-4 bg-white rounded-xl shadow-sm border border-gray-200`
- **elements**:
  - month_selector: Select / required / 下拉選月份 / 格式 "2026年04月" / 預設當月 / 可選過去 12 個月
  - settlement_cycle: SegmentedControl / required / "月結（5號）" | "雙週結" | "週結" / 預設依系統設定
  - period_summary: Text Body / required / "結算期間：{start_date} - {end_date}"
  - total_amount_badge: Badge Large / required / "本期總額：NT$ {amount}" / `bg-blue-50 text-[#2563EB] text-lg font-semibold px-4 py-2 rounded-lg`
- **states**:
  - default: 顯示當月結算概覽
  - loading: total_amount Skeleton
  - changing: 切換月份時整個 Tab 內容 loading

### Section: settlement_table

- **layout**: 全寬 DataTable，shadcn/ui `<Table>`，表頭固定 + 批次操作列
- **elements**:
  - batch_action_bar: Toolbar / required / 置於表格上方，`flex items-center gap-3 py-3`
    - select_all_checkbox: Checkbox / required / 全選/取消全選
    - selected_count: Text / required / "已選取 {count} 筆"（有選取時顯示）
    - batch_confirm_btn: Button Primary / required / "批次確認" / 僅在選取 draft 狀態項目時啟用
    - batch_pay_btn: Button Secondary / required / "批次標記已付款" / 僅在選取 confirmed 狀態項目時啟用
  - settlement_rows: DataTable / required / 欄位如下：
    - col_checkbox: Checkbox / required / 行選取
    - col_technician: AvatarText / required / 技師頭像 + 姓名 / 可點擊跳轉至技師詳情頁
    - col_period: Text / required / 結算期間 "MM/dd - MM/dd"
    - col_total_earnings: Text Number / required / "NT$ {amount}" / 由「工資 + 獎金 - 扣款」計算
      - hover Tooltip 顯示明細："工資 NT${a} + 獎金 NT${b} - 扣款 NT${c}"
    - col_labor: Text Number / required / 工資小計
    - col_bonus: Text Number / required / 獎金小計 / 綠色 `text-green-600`
    - col_penalty: Text Number / required / 扣款小計 / 紅色 `text-red-600`
    - col_status: StatusBadge / required /
      - 草稿（draft）：`bg-gray-100 text-gray-600` "草稿"
      - 已確認（confirmed）：`bg-blue-100 text-blue-700` "已確認"
      - 已付款（paid）：`bg-green-100 text-green-700` "已付款"
    - col_actions: ActionButtons / required /
      - "查看明細" — 開啟 Settlement Detail Modal
      - "確認" — 僅 draft 狀態顯示，PATCH 為 confirmed
      - "標記已付款" — 僅 confirmed 狀態顯示，PATCH 為 paid
  - table_footer: Row / required / 合計列：總工資、總獎金、總扣款、總金額 / `font-semibold bg-gray-50`
- **states**:
  - default: 顯示結算列表，奇偶行交替色
  - hover: 整列 `bg-blue-50`
  - loading: 8 列 Skeleton rows
  - empty: "本期無結算資料"
  - error: ErrorState + 重試按鈕
  - selected: 選取列 `bg-blue-100`
  - batch_processing: 批次操作中顯示進度列 "處理中... {n}/{total}"
- **copy_constraints**: 金額格式統一為 "NT$ {三位一撇}" 如 "NT$ 15,800"

### Section: settlement_detail_modal

- **layout**: Modal 大型（max-w-3xl），shadcn/ui `<Dialog>`，可捲動
- **elements**:
  - modal_title: H2 / required / "{technician_name} 結算明細 — {period}"
  - summary_row: StatCards / required / 水平排列四張小卡
    - total_labor: "工資合計" + NT$ {amount}
    - total_bonus: "獎金合計" + NT$ {amount} / 綠色
    - total_penalty: "扣款合計" + NT$ {amount} / 紅色
    - net_amount: "淨結算額" + NT$ {amount} / `text-lg font-bold`
  - order_breakdown_table: DataTable / required / 工單逐筆明細：
    - col_order_id: Link / required / 工單編號（可點擊跳轉）
    - col_service_type: Badge / required / 服務類型
    - col_commission_rate: Text / required / 佣金比例（一般維修 70% / 安裝 60% / 客供材料 80%）
    - col_order_amount: Text / required / 工單金額
    - col_commission: Text / required / 佣金金額（= 工單金額 × 佣金比例）
  - bonus_list: List / required / 獎金明細
    - "+NT$100 高評價獎金" — 評分 ≥ 4.8 的工單
    - "+NT$50 快速完工獎金" — 比預估時間快 20% 以上
  - penalty_list: List / required / 扣款明細
    - "-NT$500 重工扣款" — 同一問題二次維修
    - "-NT$300 客訴扣款" — 收到客戶投訴
  - final_amount: H3 / required / "最終結算金額：NT$ {amount}" / `text-[#2563EB] font-bold text-xl`
  - close_btn: Button Ghost / required / "關閉"
  - print_btn: Button Secondary / optional / icon: Printer / "列印"
- **states**:
  - default: 顯示完整明細
  - loading: Modal 內容 Skeleton
  - empty_bonus: 獎金區塊顯示 "本期無獎金"
  - empty_penalty: 扣款區塊顯示 "本期無扣款"

---

### Tab 2: 發票管理

### Section: invoice_filter_bar

- **layout**: 單列水平排列，`flex flex-wrap items-center gap-3`
- **elements**:
  - search_input: Input / required / icon: Search / placeholder: "搜尋發票編號或客戶名稱..." / debounce 300ms
  - status_filter: Select / required / 選項：全部、待付款（pending）、已付款（paid）、爭議中（disputed）、逾期（overdue）/ 預設「全部」
  - payment_method_filter: Select / optional / 選項：全部、信用卡、銀行轉帳、超商付款
  - date_range_filter: DateRangePicker / required / 預設本月
  - overdue_only_toggle: Toggle / optional / "僅顯示逾期" / 啟用時列表僅顯示逾期發票
- **states**:
  - default: 所有篩選器預設值
  - active: 有篩選時顯示清除按鈕
  - loading: 下拉選項載入中

### Section: invoice_table

- **layout**: 全寬 DataTable，shadcn/ui `<Table>`
- **elements**:
  - invoice_rows: DataTable / required / 欄位如下：
    - col_invoice_id: Text Code / required / 發票編號 / 等寬字體 `font-mono`
    - col_work_order_id: Link / required / 關聯工單編號 / 可點擊跳轉
    - col_customer_name: Text / required / 客戶名稱
    - col_amount: Text Number / required / "NT$ {amount}"
    - col_payment_status: StatusBadge / required /
      - 待付款（pending）：`bg-yellow-100 text-yellow-700` "待付款"
      - 已付款（paid）：`bg-green-100 text-green-700` "已付款"
      - 爭議中（disputed）：`bg-purple-100 text-purple-700` "爭議中"
      - 逾期（overdue）：`bg-red-100 text-red-700` "逾期"
    - col_payment_method: Text / required / 付款方式
    - col_issued_at: Text / required / 開立日期 yyyy/MM/dd
    - col_due_date: Text / required / 到期日 yyyy/MM/dd / 逾期時紅字
    - col_actions: ActionButtons / required /
      - "檢視詳情" — 開啟發票詳情 Modal
      - "重試付款" — 僅付款失敗發票顯示 / 附帶重試次數 "(已重試 {n}/3 次)"
      - "標記爭議" — 開啟爭議標記 Modal
  - overdue_highlight: Row styling / required / 逾期發票整列紅色底色 `bg-red-50 border-l-4 border-red-500`
- **states**:
  - default: 顯示發票列表
  - hover: 整列 `bg-blue-50`（逾期列 hover 為 `bg-red-100`）
  - loading: 8 列 Skeleton rows
  - empty: "無符合條件的發票"
  - error: ErrorState + 重試按鈕
  - retry_processing: 重試按鈕顯示 Spinner + "重試中..."
  - retry_exhausted: 已重試 3 次後按鈕 disabled + Tooltip "已達最大重試次數（3 次，每次間隔 24 小時），請聯繫技術支援"
- **copy_constraints**: 發票編號最多 20 字元，客戶名稱最多 30 字元

---

### Tab 3: 營收報表

### Section: revenue_kpi_cards

- **layout**: 1 行 4 列等寬卡片，`grid grid-cols-4 gap-6`，Style D — 圖表驅動
- **elements**:
  - monthly_revenue_card: KPICard / required /
    - label: "本月營收"
    - value: "NT$ {amount}" / H2 / `text-[#2563EB]`
    - trend: 對比上月 +/-% / 上升綠 ↑ / 下降紅 ↓
    - sparkline: Recharts mini line chart / 過去 7 天趨勢
    - icon: DollarSign / `bg-blue-100 text-blue-600 p-2 rounded-lg`
  - avg_order_value_card: KPICard / required /
    - label: "平均工單金額"
    - value: "NT$ {amount}"
    - trend: 對比上月 %
    - icon: Calculator / `bg-green-100 text-green-600 p-2 rounded-lg`
  - payment_success_card: KPICard / required /
    - label: "付款成功率"
    - value: "{percentage}%"
    - trend: 對比上月 %
    - color_code: ≥95% 綠 / 90-94% 琥珀 / <90% 紅
    - icon: CheckCircle / 動態色碼背景
  - outstanding_balance_card: KPICard / required /
    - label: "未收帳款"
    - value: "NT$ {amount}" / 金額 > 閾值時紅色
    - sub_text: "共 {count} 筆未收"
    - icon: AlertTriangle / `bg-amber-100 text-amber-600 p-2 rounded-lg`
- **states**:
  - default: 四張 KPI 卡片正常顯示數值 + 趨勢
  - loading: Skeleton（數值 + sparkline 區域）
  - error: 個別卡片可獨立顯示 "載入失敗" + 重試 icon

### Section: revenue_charts

- **layout**: 上方一大圖 + 下方兩欄圖，`grid gap-6`，每張圖表 `bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - time_granularity_selector: SegmentedControl / required / "日" | "週" | "月" / 預設「月」/ 置於圖表區上方
  - date_range_picker: DateRangePicker / required / 預設過去 6 個月
  - revenue_combo_chart: Recharts ComposedChart / required / 全寬
    - Bar: 營收金額 / `fill="#2563EB"`
    - Line: 工單數量（右軸）/ `stroke="#F59E0B"`
    - X 軸：時間（依粒度切換）
    - Y 軸左：營收金額 NT$
    - Y 軸右：工單數量
    - Tooltip: 顯示日期 + 營收 + 工單數
    - Legend: 「營收」+「工單數」
    - 標題："營收趨勢"
  - brand_pie_chart: Recharts PieChart / required / 下方左欄
    - 各品牌營收佔比
    - 色碼系列：Primary 衍生色階
    - Label: 品牌名 + 百分比
    - 中央顯示總營收金額（Donut 樣式）
    - 標題："品牌營收佔比"
  - service_type_breakdown: Recharts BarChart horizontal / required / 下方右欄
    - 水平長條圖
    - 分類：一般維修 / 安裝 / 客供材料維修 / 其他
    - 每個長條顯示金額 + 工單數
    - 色碼：一般維修 `#2563EB` / 安裝 `#F59E0B` / 客供材料 `#10B981` / 其他 `#8B5CF6`
    - 標題："服務類型營收分佈"
- **states**:
  - default: 三張圖表正常呈現
  - loading: 圖表位置 Skeleton 方塊 + pulse 動畫
  - empty: "選定期間無營收資料" + 調整日期範圍建議
  - error: 個別圖表獨立錯誤 + 重試
  - hover: Recharts Tooltip 互動，Pie chart sector 放大效果
  - granularity_change: 切換日/週/月時圖表平滑動畫過渡（Recharts `animationDuration={500}`）

### Section: export_controls

- **layout**: 右對齊，`flex justify-end gap-3 pt-4`
- **elements**:
  - export_csv_btn: Button Secondary / required / icon: FileDown / "匯出 CSV"
  - export_excel_btn: Button Secondary / required / icon: FileSpreadsheet / "匯出 Excel"
  - export_scope_note: Text Caption / optional / "匯出範圍依當前篩選條件"
- **states**:
  - default: 按鈕可用
  - exporting: 按鈕 disabled + Spinner + "匯出中..."
  - success: Toast "檔案已下載"
  - error: Toast "匯出失敗，請重試"
  - no_data: 按鈕 disabled + Tooltip "無資料可匯出"

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入** → 預設顯示「結算管理」Tab → 呼叫 `GET /api/v1/settlements?month=current` → 表格渲染
2. **切換 Tab** → URL hash 同步（`#settlement` / `#invoices` / `#revenue`）→ Lazy load 對應 Tab 資料
3. **結算 — 選擇月份** → 切換月份下拉 → 重新呼叫 settlements API → 表格更新
4. **結算 — 查看明細** → 點擊「查看明細」→ 開啟 Modal → 呼叫明細 API → 顯示工單逐筆佣金
5. **結算 — 單筆確認** → 點擊「確認」→ 確認 Dialog "確定要確認 {name} 的結算？" → `PATCH /api/v1/settlements/{id}` body: `{ status: "confirmed" }` → Optimistic update Badge → 成功 Toast / 失敗 rollback
6. **結算 — 批次確認** → 勾選多筆 draft → 點擊「批次確認」→ 確認 Dialog "確定要批次確認 {n} 筆結算？" → 逐筆 PATCH → 進度列顯示 → 全部完成 Toast / 部分失敗列出失敗項
7. **結算 — 標記已付款** → 同上流程，PATCH 為 `{ status: "paid" }`
8. **發票 — 重試付款** → 點擊「重試付款」→ 確認 Dialog → `POST /api/v1/invoices/{id}/retry` → 成功 Toast / 失敗 Toast + 更新重試次數 / 已達 3 次上限時 disabled
9. **營收 — 切換粒度** → 點擊日/週/月 → 重新呼叫 `GET /api/v1/reports/revenue?granularity=daily|weekly|monthly` → 圖表動畫更新
10. **營收 — 匯出** → 點擊匯出按鈕 → `GET /api/v1/reports/revenue/export?format=csv|xlsx` → 瀏覽器下載檔案

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | Tab 水平排列 / KPI 4 欄 / 圖表上1下2 | 完整體驗 |
| Tablet (768-1279px) | Tab 水平排列 / KPI 2×2 / 圖表全部垂直堆疊 | 結算表格隱藏 labor/bonus/penalty 分項欄 |
| Mobile (<768px) | Tab 改為下拉選擇 / KPI 單欄堆疊 / 表格改卡片列表 | 匯出按鈕移至頁面底部固定列 |

### 資料更新策略

- 結算資料：手動操作時更新，`staleTime: 60_000`
- 發票列表：`staleTime: 30_000`，切換篩選時 refetch
- 營收報表：`staleTime: 300_000`（5 分鐘），圖表資料較穩定
- KPI 卡片：`staleTime: 60_000`，每次進入 Tab 時 refetch

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/settlements` — 取得結算列表
    - Query params: `month` (yyyy-MM), `cycle` (monthly|biweekly|weekly), `status` (draft|confirmed|paid), `page`, `limit`
    - Response: `{ data: Settlement[], total: number, summary: { total_labor, total_bonus, total_penalty, net_total } }`
  - GET `/api/v1/settlements/{id}` — 取得結算明細
    - Response: `{ id, technician, period, orders: [{ order_id, service_type, commission_rate, order_amount, commission }], bonuses: [{ type, amount, description, order_id? }], penalties: [{ type, amount, description, order_id? }], net_amount }`
  - PATCH `/api/v1/settlements/{id}` — 更新結算狀態
    - Body: `{ status: "confirmed" | "paid" }`
  - GET `/api/v1/invoices` — 取得發票列表
    - Query params: `status`, `payment_method`, `date_from`, `date_to`, `search`, `page`, `limit`
    - Response: `{ data: Invoice[], total: number }`
  - POST `/api/v1/invoices/{id}/retry` — 重試發票付款
    - Response: `{ success: boolean, retry_count: number, next_retry_at?: string }`
    - 規則：最多 3 次重試，每次間隔 24 小時
  - GET `/api/v1/reports/revenue` — 取得營收報表資料
    - Query params: `granularity` (daily|weekly|monthly), `date_from`, `date_to`
    - Response: `{ timeseries: [{ date, revenue, order_count }], by_brand: [{ brand, revenue, percentage }], by_service_type: [{ type, revenue, order_count }] }`
  - GET `/api/v1/reports/kpi-dashboard` — 取得 KPI 資料
    - Response: `{ monthly_revenue: { value, trend_pct }, avg_order_value: { value, trend_pct }, payment_success_rate: { value, trend_pct }, outstanding_balance: { value, count } }`
  - GET `/api/v1/reports/revenue/export` — 匯出營收報表
    - Query params: `format` (csv|xlsx), `date_from`, `date_to`, `granularity`
    - Response: File download (binary)
- **Zustand Store**:
  - `useAccountingStore`: 管理當前 Tab、月份選擇、結算批次選取狀態
- **error_cases**:
  - 網路錯誤：Toast "網路連線異常，請檢查網路設定" + TanStack Query 自動重試 3 次
  - API 409（結算狀態衝突）：Toast "結算狀態已變更，請重新整理" + 自動 refetch
  - API 422（無效操作）：Toast "操作無效：{error_message}"，如嘗試對已付款項重新確認
  - 付款重試失敗：Toast "付款重試失敗：{reason}" + 更新重試計數
  - 匯出超時：Toast "資料量過大，匯出處理中，完成後將寄送至您的信箱"
  - 權限不足（403）：操作按鈕 disabled + Tooltip "您沒有此操作權限"

---

## [EXCEPTION TO GLOBAL RULES]

- 結算明細 Modal 允許超大寬度 `max-w-3xl`（Global 預設 Modal 為 `max-w-lg`）
- 營收報表 Tab 的圖表區域不受 Global 最大內容寬度限制，允許全寬呈現
- 匯出功能直接觸發瀏覽器下載，不走 Toast 成功提示（改用下載進度指示）

---

## [ACCEPTANCE CRITERIA]

- [ ] 三個 Tab 切換正常，URL hash 同步，直接輸入 hash URL 可跳至對應 Tab
- [ ] 結算管理 — 月份選擇切換正常，表格資料對應正確
- [ ] 結算管理 — 合計列正確計算所有列的工資、獎金、扣款、總額
- [ ] 結算管理 — 單筆確認/標記已付款 Optimistic update + 成功/失敗回饋
- [ ] 結算管理 — 批次操作含進度列，部分失敗有明確提示
- [ ] 結算明細 Modal — 佣金比例正確（一般維修 70%、安裝 60%、客供材料 80%）
- [ ] 結算明細 Modal — 獎金規則正確（+NT$100 高評價、+NT$50 快速完工）
- [ ] 結算明細 Modal — 扣款規則正確（-NT$500 重工、-NT$300 客訴）
- [ ] 發票管理 — 逾期發票紅色底色 + 左側紅色邊框正確顯示
- [ ] 發票管理 — 重試付款最多 3 次，每次間隔 24 小時，達上限後 disabled
- [ ] 發票 Tab 有逾期發票時顯示紅色通知點
- [ ] 營收報表 — 四張 KPI 卡片數值、趨勢、色碼正確
- [ ] 營收報表 — 營收趨勢圖 Bar + Line combo 正常，日/週/月切換有動畫
- [ ] 營收報表 — 品牌 Pie chart Donut 樣式，中央顯示總額
- [ ] 營收報表 — 服務類型水平 Bar chart 色碼正確
- [ ] 匯出 CSV / Excel 功能正常，檔案內容正確
- [ ] 所有金額格式 "NT$ {三位一撇}"
- [ ] 所有 Section 具備 loading / error / empty 三態
- [ ] RWD 三個斷點佈局正確
- [ ] 首次載入效能 < 2 秒
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）

---

## === EXCEPTION RULES ===

- 結算明細 Modal 允許超大寬度 `max-w-3xl`（Global 預設 Modal 為 `max-w-lg`）
- 營收報表 Tab 的圖表區域不受 Global 最大內容寬度限制，允許全寬呈現
- 匯出功能直接觸發瀏覽器下載，不走 Toast 成功提示（改用下載進度指示）

---

## === OUTPUT REQUIREMENTS ===

### Step 1: 結構確認
列出本頁面的 sections、關鍵元件、資料流策略

### Step 2: 設計決策說明
2-3 個關鍵設計決策與理由

### Step 3: 實作方案
完整 React/Next.js 程式碼（使用 shadcn/ui + Tailwind CSS）

### 品質檢查
- [ ] 色彩系統一致性
- [ ] 字體層級正確
- [ ] 元件風格統一（shadcn/ui）
- [ ] 響應式設計完整
- [ ] 所有狀態已處理（Loading / Error / Empty / Disabled）
- [ ] 無障礙支援（鍵盤 + ARIA）
- [ ] 效能指標達標

---
執行優先順序：Global 規範 > Page 特定需求 > Exception
Assembly 日期：2026-04-21
Brand System 版本：v1.0
