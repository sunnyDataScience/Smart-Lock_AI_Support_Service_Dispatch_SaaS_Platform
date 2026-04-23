# Page-Level Prompt: 技師管理（列表 + 詳情）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 技師管理頁面涵蓋列表總覽與個別技師詳細資料，為派工引擎的核心資料來源。

---

## [PAGE META]

- **page_name**: 技師管理 Technician Management
- **route_path**: `/technicians`（列表）、`/technicians/[id]`（詳情）
- **page_type**: list + detail
- **primary_goal**: 管理所有技師資料、技能認證、排班與績效，確保派工引擎有正確的技師資訊
- **secondary_goal**: 即時掌握技師可用狀態，支援手動調度與佣金結算
- **target_users**:
  - 主要：平台管理員（每日使用）
  - 次要：品牌客服主管（檢視技師能力與評分）
- **entry_point**: 左側導覽列「技師管理」/ 工單頁面點擊技師名稱 / Dashboard 技師狀態卡片
- **expected_time_on_page**: 列表頁 1-3 分鐘（快速篩選）、詳情頁 3-8 分鐘（排班與績效檢視）

---

## [STRUCTURE: SECTIONS]

### 列表頁 `/technicians`

1. **page_header**
   - section_type: header_bar
   - section_purpose: 頁面標題、技師總數統計、新增技師按鈕

2. **filter_bar**
   - section_type: filter_controls
   - section_purpose: 多維度篩選技師列表（可用狀態、技能品牌、服務區域、評分範圍）

3. **technician_table**
   - section_type: data_table
   - section_purpose: 顯示所有技師摘要資訊，支援排序與快捷操作

4. **pagination_bar**
   - section_type: pagination
   - section_purpose: 分頁控制與每頁筆數選擇

### 詳情頁 `/technicians/[id]`

5. **detail_header**
   - section_type: breadcrumb_header
   - section_purpose: 麵包屑導覽 + 技師名稱 + 狀態 Badge + 返回列表按鈕

6. **profile_card**
   - section_type: info_card
   - section_purpose: 技師基本資料與大頭照

7. **skill_certification_matrix**
   - section_type: editable_table
   - section_purpose: 展示技師所有品牌型號的技能等級與認證狀態

8. **weekly_schedule_grid**
   - section_type: interactive_grid
   - section_purpose: 視覺化排班管理，支援點擊編輯

9. **performance_charts**
   - section_type: charts_group
   - section_purpose: 多圖表呈現技師績效趨勢

10. **availability_card**
    - section_type: status_card
    - section_purpose: 即時切換技師可用狀態

11. **active_orders_list**
    - section_type: mini_card_list
    - section_purpose: 顯示技師目前進行中的工單

12. **commission_summary**
    - section_type: stats_card
    - section_purpose: 本月佣金摘要與待結算金額

13. **penalty_bonus_log**
    - section_type: timeline_list
    - section_purpose: 獎懲紀錄一覽

---

## [SECTION COMPONENT SPEC]

### Section: page_header

- **layout**: 全寬單列，左側標題 + 右側操作按鈕，`flex justify-between items-center`
- **elements**:
  - page_title: H1 / required / "技師管理"
  - technician_count: Badge / required / "共 {total} 位技師"，灰底白字
  - available_count: Badge / required / "可用 {count}"，綠底白字 `bg-green-500`
  - busy_count: Badge / required / "忙碌 {count}"，琥珀底 `bg-amber-500`
  - offline_count: Badge / required / "離線 {count}"，灰底 `bg-gray-400`
  - add_technician_btn: Button Primary / required / icon: UserPlus / "新增技師" / 開啟新增技師 Modal
- **states**:
  - default: 顯示所有統計 Badge
  - loading: 數字部分 Skeleton pulse
- **copy_constraints**: 標題固定文案

### Section: filter_bar

- **layout**: 單列水平排列，`flex flex-wrap gap-3`，篩選條件超過一行時換行
- **elements**:
  - availability_filter: Select / required / 選項：全部、可用（available）、忙碌（busy）、離線（offline）/ 預設「全部」
  - skill_brand_filter: Multi-Select / required / 下拉多選品牌（動態載入品牌列表：Yale、Schlage、Kwikset、August、Samsung 等）/ 帶搜尋功能
  - region_filter: Multi-Select / required / 下拉多選服務區域（動態載入區域列表）/ 帶搜尋功能
  - rating_range_filter: Dual Range Slider / required / 範圍 1.0 - 5.0 / 步進 0.1 / 預設 1.0-5.0 / 顯示選取值
  - clear_filters_btn: Button Ghost / optional / icon: X / "清除篩選" / 僅在有篩選條件時顯示
  - search_input: Input / required / icon: Search / placeholder: "搜尋技師姓名或電話..." / debounce 300ms
- **states**:
  - default: 所有篩選器顯示預設值
  - active: 有啟用篩選時，對應篩選器顯示 Primary 色邊框 `border-[#2563EB]`，清除按鈕出現
  - loading: 篩選器下拉選項載入中顯示 Spinner
- **copy_constraints**: 篩選標籤最多 8 字

### Section: technician_table

- **layout**: 全寬 DataTable，shadcn/ui `<Table>` 元件，固定表頭 `sticky top-0`
- **elements**:
  - col_avatar: Avatar / required / 40×40px 圓形 / 無頭像時顯示姓名首字
  - col_name: Text Body MD / required / 可排序 / 點擊進入詳情頁 `/technicians/[id]` / `text-[#2563EB] hover:underline cursor-pointer`
  - col_skill_set: TagBadge[] / required / 每個技能顯示品牌+型號 Badge / 超過 3 個時折疊顯示 "+{n} 更多" / Badge 樣式 `bg-blue-50 text-blue-700 text-xs rounded-full px-2 py-0.5`
  - col_service_regions: TagBadge[] / required / 區域 Badge / 超過 2 個時折疊 / Badge 樣式 `bg-gray-100 text-gray-600 text-xs rounded-full px-2 py-0.5`
  - col_rating: StarRating / required / 1-5 星 + 數字（如 ★ 4.7）/ 可排序 / 星星色 `text-[#F59E0B]`
  - col_availability: StatusBadge / required / 可用=綠色圓點+「可用」`bg-green-100 text-green-700`、忙碌=琥珀色圓點+「忙碌」`bg-amber-100 text-amber-700`、離線=灰色圓點+「離線」`bg-gray-100 text-gray-500`
  - col_active_orders: Number Badge / required / 進行中工單數 / 0 時顯示灰色「0」，>5 時紅底警示 `bg-red-100 text-red-700`
  - col_monthly_completion: Text / required / 本月完成數 + 趨勢箭頭（↑ 綠 / ↓ 紅 / → 灰）
  - col_actions: ActionMenu / required / 三點選單 `<DropdownMenu>` 包含：
    - "切換可用狀態" — 快速切換 available/offline
    - "查看排班" — 跳至詳情頁排班區塊
    - "編輯資料" — 開啟編輯 Modal
    - "停用帳號" — 危險操作，紅字，需二次確認
- **states**:
  - default: 顯示資料列，奇偶行交替背景色 `odd:bg-white even:bg-gray-50`
  - hover: 整列底色 `bg-blue-50`
  - loading: 10 列 Skeleton rows，每列高度 56px
  - empty: 表格中央 EmptyState 插圖 + "找不到符合條件的技師" + "清除篩選" 連結
  - error: ErrorState + "載入失敗，請重試" + 重試按鈕
  - sorting: 排序欄位表頭顯示箭頭方向指示
- **copy_constraints**: 技師名稱最多 20 字元，技能 Badge 文字最多 15 字元

### Section: pagination_bar

- **layout**: 全寬，`flex justify-between items-center`
- **elements**:
  - page_info: Text Caption / required / "顯示 {from}-{to} 筆，共 {total} 筆"
  - page_size_selector: Select / required / 選項：10、25、50 / 預設 25
  - page_nav: Pagination / required / 上一頁 / 頁碼按鈕 / 下一頁 / shadcn/ui `<Pagination>`
- **states**:
  - default: 顯示分頁資訊
  - disabled: 首頁時「上一頁」disabled，末頁時「下一頁」disabled
  - single_page: 僅一頁時隱藏分頁導覽

### Section: detail_header

- **layout**: 全寬單列，`flex items-center gap-3`
- **elements**:
  - breadcrumb: Breadcrumb / required / "技師管理 > {technician_name}" / 第一層可點擊回列表
  - status_badge: StatusBadge / required / 同列表頁可用狀態 Badge 樣式
  - back_btn: Button Ghost / required / icon: ArrowLeft / "返回列表"
- **states**:
  - default: 顯示完整麵包屑
  - loading: 技師名稱 Skeleton

### Section: profile_card

- **layout**: 水平卡片，`flex gap-6 p-6 bg-white rounded-xl shadow-sm border border-gray-200`
- **elements**:
  - avatar: Avatar / required / 80×80px 圓形 / 支援上傳更換 / 無頭像時顯示姓名首字 + 背景色
  - name: H2 / required / 技師姓名
  - phone: Text Body / required / icon: Phone / 電話號碼 / 可點擊撥打 `tel:`
  - email: Text Body / required / icon: Mail / 電子郵件 / 可點擊 `mailto:`
  - joined_date: Text Caption / required / icon: Calendar / "加入日期：{yyyy/MM/dd}"
  - overall_rating: StarRating Large / required / 大型星星 + 數字 + "({review_count} 則評價)" / 星星色 `text-[#F59E0B]`
  - edit_profile_btn: Button Secondary / required / icon: Pencil / "編輯資料" / 開啟編輯 Modal
- **states**:
  - default: 顯示所有資料
  - loading: 所有欄位 Skeleton
  - editing: Modal overlay 編輯表單（姓名、電話、郵件、頭像上傳）

### Section: skill_certification_matrix

- **layout**: 全寬表格，`bg-white rounded-xl shadow-sm border border-gray-200 p-6` 內嵌 DataTable
- **elements**:
  - section_title: H3 / required / "技能認證矩陣"
  - add_skill_btn: Button Secondary / required / icon: Plus / "新增技能" / 開啟新增技能 Modal
  - skill_table: DataTable / required / 欄位如下：
    - col_brand_model: Text / required / "{品牌}：{型號}" 格式 / 如 "Yale：YDM-7116"
    - col_proficiency: StarRating Editable / required / 1-5 星 / 點擊可修改 / 星星色 `text-[#F59E0B]`
    - col_cert_expiry: Text / required / 認證到期日 yyyy/MM/dd
    - col_days_remaining: Text / computed / 距到期天數
    - col_status: StatusBadge / required /
      - 有效（valid）：`bg-green-100 text-green-700` "有效"
      - 即將到期（expiring_soon，≤30天）：`bg-amber-100 text-amber-700` "即將到期"
      - 已過期（expired）：`bg-red-100 text-red-700` "已過期"
    - col_actions: IconButton / required / 編輯 icon: Pencil / 刪除 icon: Trash（紅色，需確認）
- **states**:
  - default: 顯示技能列表，有效排最前，已過期排最後
  - loading: Skeleton rows
  - empty: "尚未登錄任何技能認證" + "新增技能" CTA
  - expiring_warning: 即將到期項目整列背景 `bg-amber-50`
  - expired_warning: 已過期項目整列背景 `bg-red-50` + 刪除線文字
- **copy_constraints**: 品牌名稱最多 20 字元，型號最多 20 字元

### Section: weekly_schedule_grid

- **layout**: 全寬互動式網格，`bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - section_title: H3 / required / "每週排班"
  - week_selector: DatePicker / required / 選擇週次 / 預設本週 / 上下週箭頭切換
  - schedule_grid: Grid / required / 7 欄（週一至週日）× 時段列（08:00-20:00，每格 1 小時）
    - 每個時段格子為可點擊區塊
    - 時段類型色碼：
      - 一般班（regular）：`bg-blue-100 border-blue-300 text-blue-700`
      - 待命班（on_call）：`bg-purple-100 border-purple-300 text-purple-700`
      - 加班（overtime）：`bg-orange-100 border-orange-300 text-orange-700`
      - 請假（leave）：`bg-gray-200 border-gray-400 text-gray-500` + 斜線圖案
    - 色碼圖例 Legend 顯示於網格上方
  - save_btn: Button Primary / required / "儲存排班" / 有變更時啟用
  - reset_btn: Button Ghost / optional / "重置" / 有變更時顯示
- **states**:
  - default: 顯示本週排班，已排時段填色
  - hover: 時段格子 hover 時加深背景色 + 顯示 Tooltip（時段類型名稱）
  - editing: 點擊空格 → 彈出小型下拉選擇時段類型 → 選擇後格子即時填色
  - click_filled: 點擊已填格 → 彈出選項：變更類型 / 清除
  - dirty: 有未儲存變更時，儲存按鈕亮起 Primary 色，標題旁顯示「未儲存」amber Badge
  - loading: 整個網格 Skeleton
  - saving: 儲存按鈕顯示 Spinner + "儲存中..."
  - error: Toast 錯誤訊息 "排班儲存失敗，請重試"
- **copy_constraints**: 時段格子內文字最多 4 字元（如「一般」「待命」）

### Section: performance_charts

- **layout**: 2×2 網格，`grid grid-cols-2 gap-6`，每張圖表包裹於 `bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - section_title: H3 / required / "績效分析"
  - period_selector: SegmentedControl / required / 選項：近 3 個月、近 6 個月、近 1 年 / 預設近 3 個月
  - completion_trend_chart: Recharts LineChart / required /
    - X 軸：月份
    - Y 軸：完成工單數
    - Line 色：`#2563EB`（Primary）
    - 資料點 hover 顯示 Tooltip
    - 標題："月完成量趨勢"
  - rating_trend_chart: Recharts LineChart / required /
    - X 軸：月份
    - Y 軸：平均評分（1.0-5.0）
    - Line 色：`#F59E0B`（Accent）
    - Reference line 在 4.0 處 `stroke-dasharray="5 5" stroke="#10B981"`
    - 標題："評分趨勢"
  - rejection_rate_chart: Recharts BarChart / required /
    - X 軸：月份
    - Y 軸：拒單率 %
    - Bar 色：`#EF4444` 拒單 / `#10B981` 接單
    - 標題："拒單率"
  - ontime_rate_gauge: Recharts RadialBarChart / required /
    - 單一數值儀表，顯示準時率百分比
    - 色碼：≥90% 綠 `#10B981`、70-89% 琥珀 `#F59E0B`、<70% 紅 `#EF4444`
    - 中央大字顯示百分比數值
    - 標題："準時率"
- **states**:
  - default: 四張圖表正常呈現
  - loading: 每張圖表位置顯示 Skeleton 方塊
  - empty: 圖表區域顯示 "資料不足，需至少一個月的工單紀錄"
  - error: 個別圖表可獨立顯示錯誤 + 重試
  - hover: Recharts Tooltip 顯示具體數值

### Section: availability_card

- **layout**: 卡片，`bg-white rounded-xl shadow-sm border border-gray-200 p-4`，位於右側 1/3 區塊頂部
- **elements**:
  - card_title: H4 / required / "可用狀態"
  - status_indicator: StatusDot Large / required / 大型圓點 + 狀態文字
    - 可用：綠色脈動動畫 `animate-pulse` + "可用"
    - 忙碌：琥珀色靜態 + "忙碌中"
    - 離線：灰色靜態 + "離線"
  - toggle_switch: Switch / required / shadcn/ui `<Switch>` / 切換可用/離線
  - last_active: Text Caption / required / "最後上線：{相對時間}" 如 "5 分鐘前"
  - auto_offline_note: Text Caption / optional / "系統將在無回應 30 分鐘後自動切為離線"
- **states**:
  - default: 顯示當前狀態
  - toggling: Switch 動畫中 + 短暫 disabled
  - busy_locked: 有進行中工單時，無法切換為離線，Switch disabled + Tooltip "有進行中工單，無法切換"
  - success: Toast "狀態已更新"
  - error: Toast "狀態更新失敗，請重試"

### Section: active_orders_list

- **layout**: 卡片列表，`bg-white rounded-xl shadow-sm border border-gray-200 p-4`，最多顯示 5 張 mini card
- **elements**:
  - card_title: H4 / required / "進行中工單" + Badge 數量 `bg-[#2563EB] text-white text-xs rounded-full px-2`
  - order_mini_cards: MiniCard[] / required / 每張包含：
    - order_id: Text Caption / required / 工單編號，可點擊跳轉至工單詳情
    - customer_name: Text Body SM / required / 客戶名稱
    - service_type: Badge / required / 服務類型（一般維修/安裝/客供材料）
    - status_badge: StatusBadge / required / 工單狀態（13 態之當前態）
    - time_elapsed: Text Caption / required / "已進行 {時間}"
  - view_all_orders_link: Link / optional / "查看所有工單 →" / 顯示於有 >5 張工單時
- **states**:
  - default: 顯示工單 mini cards
  - loading: 3 張 Skeleton mini cards
  - empty: "目前無進行中工單" + icon: CheckCircle 綠色
  - card_hover: mini card hover 時 `shadow-md` + 淺藍底 `bg-blue-50`

### Section: commission_summary

- **layout**: 卡片，`bg-white rounded-xl shadow-sm border border-gray-200 p-4`
- **elements**:
  - card_title: H4 / required / "佣金摘要"
  - current_month_label: Text Caption / required / "{yyyy}年{MM}月"
  - total_earnings: H2 Number / required / "NT$ {amount}" / 大字綠色 `text-green-600`
  - earnings_breakdown: List / required /
    - "一般維修佣金 (70%)": NT$ {amount}
    - "安裝佣金 (60%)": NT$ {amount}
    - "客供材料佣金 (80%)": NT$ {amount}
    - "獎金加項": NT$ +{amount} / 綠色
    - "扣款減項": NT$ -{amount} / 紅色
  - pending_settlement: Text / required / "待結算：NT$ {amount}" / `text-amber-600`
  - settlement_type: Badge / required / 結算週期：月結（5號）/ 雙週結 / 週結
  - next_settlement_date: Text Caption / required / "下次結算日：{yyyy/MM/dd}"
- **states**:
  - default: 顯示佣金明細
  - loading: 所有金額 Skeleton
  - zero_state: 金額顯示 "NT$ 0" + "本月尚無已完成工單"

### Section: penalty_bonus_log

- **layout**: 卡片內時間軸列表，`bg-white rounded-xl shadow-sm border border-gray-200 p-4`，最多顯示 10 筆
- **elements**:
  - card_title: H4 / required / "獎懲紀錄"
  - log_entries: TimelineItem[] / required / 每筆包含：
    - timestamp: Text Caption / required / 日期時間
    - type_badge: Badge / required /
      - 獎金：`bg-green-100 text-green-700` icon: TrendingUp
      - 扣款：`bg-red-100 text-red-700` icon: TrendingDown
    - description: Text Body SM / required / 獎懲原因（如 "高評價獎金 +NT$100"、"重工扣款 -NT$500"）
    - amount: Text / required / 正數綠色 `text-green-600`、負數紅色 `text-red-600`
    - related_order: Link / optional / 關聯工單編號，可點擊跳轉
  - view_all_link: Link / optional / "查看完整紀錄 →"
- **states**:
  - default: 時間軸列表，最新在上
  - loading: 5 筆 Skeleton
  - empty: "無獎懲紀錄" + icon: Shield 灰色

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入** → 呼叫 `GET /api/v1/technicians?page=1&limit=25` → 表格渲染 + 頁面標題統計 Badge 更新
2. **篩選操作** → 變更任一篩選器 → debounce 300ms → 重新呼叫 API（附帶 query params）→ 表格更新 + URL query string 同步（支援書籤/分享）
3. **排序操作** → 點擊表頭 → 切換 asc/desc → 重新呼叫 API（server-side sorting）
4. **快捷切換可用狀態** → 點擊三點選單 "切換可用狀態" → 呼叫 `PATCH /api/v1/technicians/{id}` body: `{ availability: "available" | "offline" }` → Optimistic update 列表 Badge → 成功 Toast / 失敗 rollback + Error Toast
5. **進入詳情頁** → 點擊技師名稱 → 路由 `/technicians/[id]` → 並行呼叫 4 支 API → 左側 2/3 與右側 1/3 同步渲染
6. **編輯排班** → 點擊排班格子 → 彈出類型選擇下拉 → 選擇後格子即時變色 → 點擊「儲存排班」→ `PATCH /api/v1/technicians/{id}/schedule` → 成功 Toast / 失敗 rollback
7. **修改技能熟練度** → 點擊星星 → Optimistic update → `PATCH /api/v1/technicians/{id}` body: `{ skills: [...] }` → 成功靜默 / 失敗 rollback + Error Toast
8. **切換績效時間範圍** → 點擊 SegmentedControl → 重新呼叫 `GET /api/v1/technicians/{id}/performance?period=3m|6m|1y` → 圖表動畫更新

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 列表：全寬表格 / 詳情：左 2/3 + 右 1/3 側邊 | 完整體驗，所有欄位可見 |
| Tablet (768-1279px) | 列表：隱藏 monthly_completion 與 service_regions 欄位 / 詳情：改為單欄堆疊，右側區塊移至左側下方 | 表格水平捲動提示 |
| Mobile (<768px) | 列表：改為卡片式列表（每技師一張卡片）/ 詳情：單欄堆疊，排班網格水平捲動 | 篩選器收合為「篩選」按鈕 + 底部 Sheet |

### 資料更新策略

- 技師列表：進入頁面時載入，篩選/排序/分頁時重新載入，TanStack Query `staleTime: 30_000`
- 技師可用狀態：WebSocket 推送即時更新（`ws://*/technicians/status`），收到事件時 invalidate query
- 詳情頁排班：僅手動操作時更新，無自動刷新
- 績效圖表：`staleTime: 300_000`（5 分鐘），切換時間範圍時重新載入
- 進行中工單：`refetchInterval: 60_000`（1 分鐘自動更新）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/technicians` — 取得技師列表（支援分頁、篩選、排序）
    - Query params: `page`, `limit`, `availability`, `skills`, `regions`, `rating_min`, `rating_max`, `sort_by`, `sort_order`, `search`
    - Response: `{ data: Technician[], total: number, page: number, limit: number }`
  - PATCH `/api/v1/technicians/{id}` — 更新技師資料（基本資料、技能、可用狀態）
    - Body: `{ availability?, name?, phone?, email?, skills?: { brand, model, proficiency, cert_expiry }[] }`
  - GET `/api/v1/technicians/{id}` — 取得技師詳細資料
    - Response: `{ id, name, avatar_url, phone, email, joined_date, rating, review_count, availability, skills[], service_regions[], active_orders_count, commission_summary }`
  - GET `/api/v1/technicians/{id}/schedule` — 取得技師排班
    - Query params: `week_start` (ISO date)
    - Response: `{ week_start, slots: { day: 0-6, hour: 0-23, type: "regular"|"on_call"|"overtime"|"leave" }[] }`
  - PATCH `/api/v1/technicians/{id}/schedule` — 更新技師排班
    - Body: `{ week_start, slots: { day, hour, type }[] }`
  - GET `/api/v1/technicians/{id}/performance` — 取得技師績效資料
    - Query params: `period` (3m|6m|1y)
    - Response: `{ monthly_completions: { month, count }[], rating_trend: { month, avg }[], rejection_rate: { month, rate }[], ontime_rate: number }`
  - GET `/api/v1/technicians/{id}/orders?status=active` — 取得進行中工單
  - GET `/api/v1/technicians/{id}/commission` — 取得佣金摘要
  - GET `/api/v1/technicians/{id}/penalty-bonus` — 取得獎懲紀錄
- **Zustand Store**:
  - `useTechnicianListStore`: 管理篩選條件、排序、分頁狀態
  - `useTechnicianDetailStore`: 管理排班編輯 dirty state
- **error_cases**:
  - 網路錯誤：Toast "網路連線異常，請檢查網路設定" + 自動重試 3 次（TanStack Query retry）
  - API 404（技師不存在）：詳情頁顯示 "找不到此技師" + 返回列表按鈕
  - API 403（權限不足）：Toast "您沒有權限執行此操作" + 操作按鈕 disabled
  - API 409（排班衝突）：Toast "排班時段衝突，請確認" + 標示衝突格子為紅色邊框
  - API 422（資料驗證失敗）：表單欄位顯示行內錯誤訊息

---

## [EXCEPTION TO GLOBAL RULES]

- 排班網格在 Mobile 斷點下允許水平捲動，不受 Global 最大寬度限制
- 績效圖表在 Mobile 斷點下改為垂直堆疊單欄（`grid-cols-1`），不維持 2×2 佈局
- 技師可用狀態使用 WebSocket 即時推送，不同於其他頁面的 polling 策略

---

## [ACCEPTANCE CRITERIA]

- [ ] 列表頁所有欄位正確顯示，篩選、排序、分頁功能正常
- [ ] 可用狀態 Badge 顏色正確：available=綠 / busy=琥珀 / offline=灰
- [ ] 篩選條件同步至 URL query string，支援書籤與分享
- [ ] 快捷切換可用狀態採用 Optimistic update，成功/失敗有 Toast 回饋
- [ ] 詳情頁左 2/3 與右 1/3 佈局正確，4 支 API 並行載入
- [ ] 技能認證矩陣正確顯示三態：valid/expiring_soon/expired，色碼與排序正確
- [ ] 排班網格可點擊編輯，未儲存時顯示「未儲存」警示，離開頁面有確認提示
- [ ] 績效圖表四張均使用 Recharts，Tooltip、Legend 正確，時間範圍切換有動畫
- [ ] 準時率儀表依 ≥90%/70-89%/<70% 顯示綠/琥珀/紅色
- [ ] 佣金摘要正確顯示三種佣金比例（70%/60%/80%）與獎懲明細
- [ ] 獎懲紀錄最多 10 筆，金額正負數色碼正確
- [ ] 所有 Section 具備 loading / error / empty 三態
- [ ] RWD 三個斷點佈局正確（Desktop 分欄 / Tablet 簡化 / Mobile 卡片化）
- [ ] WebSocket 技師狀態即時更新正常運作
- [ ] 首次載入效能 < 2 秒（含所有 API 呼叫）
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
