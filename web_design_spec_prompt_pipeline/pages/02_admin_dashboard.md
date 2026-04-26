# Page-Level Prompt: Admin Dashboard 管理後台儀表板

> 管理者登入後的首頁，以 KPI 卡片為核心，即時呈現工單、技師、AI 診斷等營運關鍵指標。

---

## [PAGE META]

- **page_name**: Admin Dashboard
- **route_path**: `/dashboard`
- **page_type**: dashboard
- **ia_pages**: A1
- **openapi_ops**: listWorkOrders
- **asyncapi_ops**: subscribeSlaAlerts
- **primary_goal**: 以 Style A（KPI Card Dashboard）即時呈現工單量、完工率、逾時工單、在線技師等營運關鍵指標，讓管理者一眼掌握系統運作狀態
- **secondary_goal**: 透過趨勢圖表與最近工單列表，快速發現異常並跳轉至細節頁面處理
- **target_users**:
  - 主要：品牌／經銷商管理員（每日多次查看）
  - 次要：營運主管（每週檢視 SLA 與 AI 準確度趨勢）
- **entry_point**: 登入後預設導向 / 側邊欄點擊「儀表板」/ 點擊左上角 Logo
- **expected_time_on_page**: 30 秒 - 3 分鐘（快速瀏覽 KPI 後進入工單或技師管理）

---

## [STRUCTURE: SECTIONS]

1. **kpi_cards**
   - section_type: stats_cards
   - section_purpose: 以 4 張 KPI 卡片呈現今日核心營運數據（今日工單數 / 完工率 / 逾時工單 / 在線技師）

2. **secondary_kpi_cards**
   - section_type: stats_cards
   - section_purpose: 以 2 張輔助 KPI 卡片呈現 AI 診斷準確率與 SLA 達標率

3. **charts_row**
   - section_type: charts
   - section_purpose: 左側工單趨勢折線圖 + 右側技師狀態圓餅圖，視覺化近期營運走勢

4. **recent_work_orders**
   - section_type: data_table
   - section_purpose: 顯示最近 10 筆工單摘要，可展開查看詳情，快速掌握最新動態

5. **sidebar_navigation**
   - section_type: navigation
   - section_purpose: 固定左側導航欄，提供全站功能入口

6. **page_header**
   - section_type: header
   - section_purpose: 頁面標題、目前日期時間、全域搜尋與通知鈴鐺

7. **realtime_status_bar**
   - section_type: status_indicator
   - section_purpose: 顯示 WebSocket 連線狀態，確保管理者知曉資料是否為即時

---

## [SECTION COMPONENT SPEC]

### Section: sidebar_navigation

- **layout**: 固定左側欄，寬度 240px，背景色 #1E293B（Secondary），高度 100vh，sticky 定位
- **elements**:
  - brand_logo: Image / required / 平台 Logo，高度 40px，上方 padding 24px
  - nav_items: NavItem[] / required / 圖標 + 文字，完整項目清單依 `E5x--frontend-information-arch.md` 7.3 節 `adminNavigation` 定義：
    1. 儀表板 (LayoutDashboard) [V1]
    2. 對話管理 (MessageSquare) [V1]
    3. 問題卡 (ClipboardList) [V1]
    4. 知識庫 (BookOpen) [V1] → 子項：案例庫、手冊管理、SOP 審核 (badge: pending_count)
    5. 派工管理 (Truck) [V2] → 子項：工單列表、派工佇列監控 (badge: stuck_count)
    6. 技師管理 (Users) [V2]
    7. 客戶主檔 (UserCircle) [V2]
    8. 帳務與結算 (Receipt) [V2] → 子項：月結算總覽、退款審批 (badge)、保固索賠 (badge)、爭議仲裁 (badge)
    9. 庫存 (Package) [V2] (badge: low_stock_count)
    10. 報表中心 (BarChart3) [V2] → 子項：KPI 儀表板、技師排行、營收報表、SOP 績效
    11. 稽核與權限 (ShieldCheck) [V2] → 子項：RBAC 管理、稽核日誌
    12. 系統設定 (Settings) [V1] → 子項：個人/安全、租戶設定 (V3)
  - active_indicator: LeftBorder / required / 當前頁面左側 3px #2563EB 指示條
  - user_avatar: Avatar / required / 底部顯示登入者頭像 + 名稱 + 角色
  - collapse_toggle: IconButton / optional / 收合側邊欄為 64px 純圖標模式
- **states**:
  - default: 展開 240px，顯示圖標 + 文字，當前頁面項目高亮（背景 rgba(255,255,255,0.08)）
  - hover: nav_item 背景變為 rgba(255,255,255,0.12)，游標 pointer
  - collapsed: 寬度 64px，僅顯示圖標，hover 時 tooltip 顯示文字
  - loading: 無特殊載入態（靜態導航）
  - mobile: 完全隱藏，改用底部 Tab Bar
- **copy_constraints**: 導航項目名稱最多 6 個中文字

### Section: page_header

- **layout**: 全寬單列，左對齊標題 + 右對齊工具列，高度 64px，背景 #FFFFFF，底部 1px border #E2E8F0
- **elements**:
  - page_title: H1 / required / "儀表板"，font: Inter 24px/600
  - current_datetime: Body SM / required / "2026年4月21日 週二" 格式
  - global_search: SearchInput / optional / placeholder "搜尋工單、技師、客戶..."，寬度 320px
  - notification_bell: IconButton / required / 鈴鐺圖標 + 未讀紅點 badge（數字）
  - refresh_button: IconButton / optional / 手動重新整理所有資料
- **states**:
  - default: 顯示標題 + 日期 + 工具列
  - loading: 無特殊載入態
  - notification_active: 鈴鐺圖標旁顯示紅色圓點 + 未讀數字
  - search_focused: 搜尋框展開至 480px，顯示搜尋建議下拉
- **copy_constraints**: 頁面標題最多 10 字；搜尋 placeholder 最多 20 字

### Section: kpi_cards

- **layout**: 4 欄等寬網格（Desktop 12-col grid 每張 3-col），間距 24px，上方 margin 24px
- **elements**:
  - today_orders: KPICard / required / 標題 "今日工單數"，數值使用 text.kpi（36px/700 Inter），副標 vs 昨日 ±N%，圖標 ClipboardList，卡片背景 #FFFFFF，左側 4px accent border #2563EB
  - completion_rate: KPICard / required / 標題 "完工率"，數值 36px/700 + "%"，副標 vs 昨日 ±N%，圖標 CheckCircle，accent border #10B981（綠色），數值 ≥90% 綠色 / 70-89% 琥珀色 / <70% 紅色
  - overdue_orders: KPICard / required / 標題 "逾時工單"，數值 36px/700，副標 "佔總工單 N%"，圖標 AlertTriangle，accent border #EF4444（紅色），數值 >0 時數字紅色閃爍動畫
  - online_technicians: KPICard / required / 標題 "在線技師"，數值 36px/700 + " / {total}"，副標 "可派遣 N 人"，圖標 Users，accent border #F59E0B（Amber）
- **states**:
  - default: 白色卡片，圓角 8px，shadow-sm，左側 4px 色條，數值即時顯示
  - hover: shadow-md，卡片輕微上移 translateY(-2px)，游標 pointer，點擊可跳轉至對應列表頁
  - loading: Skeleton 動畫（標題行 + 數值行 + 副標行），維持卡片外框
  - error: 卡片內顯示 "資料載入失敗" + 重試圖標按鈕，邊框變為 #FEE2E2
  - empty: 數值顯示 "—"，副標顯示 "暫無資料"
  - realtime_update: 數值變更時短暫 scale(1.05) + 色彩 pulse 動畫（0.3s ease-out）
- **copy_constraints**: KPI 標題最多 6 字；副標最多 15 字；數值最大 5 位數

### Section: secondary_kpi_cards

- **layout**: 2 欄等寬網格（Desktop 12-col grid 每張 6-col），間距 24px，與主 KPI 卡片間距 16px
- **elements**:
  - ai_accuracy: KPICard / required / 標題 "AI 診斷準確率"，數值 36px/700 + "%"，副標 "近 7 日 / 樣本 N 筆"，圖標 Brain（或 Sparkles），accent border #8B5CF6（紫色），數值 ≥85% 綠色 / 70-84% 琥珀色 / <70% 紅色
  - sla_compliance: KPICard / required / 標題 "SLA 達標率"，數值 36px/700 + "%"，副標 "本月目標 95%"，圖標 Shield，accent border #2563EB，內含迷你進度條（目標線 vs 實際值）
- **states**:
  - default: 同 kpi_cards 樣式，白色卡片，圓角 8px，shadow-sm
  - hover: shadow-md，translateY(-2px)，游標 pointer
  - loading: Skeleton 動畫
  - error: "資料載入失敗" + 重試按鈕
  - empty: 數值 "—"，副標 "資料不足，尚無法計算"
- **copy_constraints**: 標題最多 8 字；副標最多 20 字

### Section: charts_row

- **layout**: 2 欄非等寬佈局 — 左側 2/3（8-col）工單趨勢圖 + 右側 1/3（4-col）技師狀態圖，間距 24px
- **elements**:
  - work_order_trend_chart: RechartsLineChart / required / 標題 "工單趨勢"，X 軸為日期（近 14 天），Y 軸為工單數量，雙折線：新建工單（#2563EB）+ 完成工單（#10B981），區域填充半透明漸層，右上角時間範圍切換（7天 / 14天 / 30天），Tooltip 顯示具體數值
  - technician_status_chart: RechartsPieChart / required / 標題 "技師狀態分佈"，扇區：在線空閒（#10B981）/ 執行中（#2563EB）/ 離線（#94A3B8）/ 請假（#F59E0B），中央顯示總人數，圖例在下方水平排列
- **states**:
  - default: 圖表完整渲染，白色卡片包裹，圓角 8px，shadow-sm，padding 24px
  - hover: 折線圖 hover 顯示 crosshair + tooltip；圓餅圖 hover 扇區放大 + tooltip
  - loading: 卡片內顯示圖表 Skeleton（矩形佔位 + 閃爍動畫）
  - error: "圖表載入失敗" + 重試按鈕，替代整個圖表區域
  - empty: 折線圖顯示空座標軸 + "暫無資料"；圓餅圖顯示灰色空心圓 + "暫無技師資料"
- **copy_constraints**: 圖表標題最多 8 字；Tooltip 數值標籤最多 15 字

### Section: recent_work_orders

- **layout**: 全寬資料表格，白色卡片包裹，圓角 8px，shadow-sm，最多顯示 10 列
- **elements**:
  - section_title: H2 / required / "最近工單"，右側 "查看全部 →" 連結導向 `/work-orders`
  - table_header: TableHead / required / 欄位：工單編號、客戶名稱、鎖型型號、狀態、優先度、建立時間、指派技師
  - table_rows: TableRow[] / required / 每列對應一筆工單摘要
    - order_id: Body SM Mono / required / 格式 "WO-YYYYMMDD-XXXX"
    - customer_name: Body SM / required / 最多 10 字
    - lock_model: Body SM / required / 品牌 + 型號
    - status: Badge / required / 待指派(灰) / 已指派(藍) / 進行中(琥珀) / 已完成(綠) / 逾時(紅)
    - priority: Badge / required / 一般(灰) / 急件(琥珀) / 緊急(紅)
    - created_at: Caption / required / 相對時間 "N 分鐘前" 或絕對時間
    - assigned_technician: AvatarName / optional / 技師頭像 + 姓名，未指派時顯示 "—"
  - expand_row: Collapsible / optional / 展開後顯示：問題摘要、AI 初步診斷、客戶地址
  - pagination_info: Caption / required / "顯示最近 10 筆，共 {total} 筆"
- **states**:
  - default: 表格正常顯示，奇偶列交替背景（#FFFFFF / #F8FAFC）
  - hover: 列背景變為 #EFF6FF（淺藍），游標 pointer
  - loading: 10 列 Skeleton rows（每列 7 個 Skeleton 元素）
  - error: 表格區域顯示 "工單載入失敗" + 重試按鈕
  - empty: 表格區域顯示插圖 + "目前沒有工單記錄" + CTA「建立工單」
  - expanded: 展開列下方顯示額外資訊區塊，背景 #F8FAFC，左側 3px #2563EB 指示條
- **copy_constraints**: 工單編號固定格式 16 字元；客戶名稱最多 10 字；問題摘要最多 50 字

### Section: realtime_status_bar

- **layout**: page_header 右側小型狀態指示器，與通知鈴鐺同列
- **elements**:
  - connection_indicator: StatusDot / required / 綠色圓點 = WebSocket 連線中；琥珀色 = 降級為 polling；紅色 = 離線
  - connection_label: Caption / optional / hover 時 tooltip 顯示 "即時連線" / "每 30 秒更新" / "連線中斷"
- **states**:
  - connected: 綠色圓點 + 微弱 pulse 動畫
  - polling_fallback: 琥珀色圓點 + tooltip "WebSocket 連線失敗，已切換為每 30 秒輪詢"
  - disconnected: 紅色圓點 + 顯示 "離線" 文字 + 重新連線按鈕
  - reconnecting: 琥珀色圓點 + 旋轉動畫
- **copy_constraints**: tooltip 最多 30 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. 頁面載入 → 並行請求 `/api/v1/dashboard/overview` + `/api/v1/dashboard/kpi` + `/api/v1/work-orders?limit=10&sort=-created_at` → 各 Section 依序渲染（KPI 優先）
2. WebSocket 連線建立 → 訂閱 KPI 即時更新頻道 → KPI 數值變更時觸發 pulse 動畫
3. WebSocket 連線失敗 → 自動降級為 30 秒 polling → 狀態指示器轉為琥珀色
4. 點擊 KPI 卡片「今日工單數」→ 導航至 `/work-orders?filter=today`
5. 點擊 KPI 卡片「逾時工單」→ 導航至 `/work-orders?filter=overdue`
6. 點擊 KPI 卡片「在線技師」→ 導航至 `/technicians?status=online`
7. 點擊圖表時間範圍切換（7天 / 14天 / 30天）→ 重新請求對應範圍資料 → 圖表平滑過渡動畫
8. 點擊工單列展開 → Collapsible 動畫展開顯示詳情
9. 點擊工單編號或 "查看全部" → 導航至 `/work-orders` 或 `/work-orders/{id}`
10. 手動點擊 refresh 按鈕 → 所有 API 重新請求 → 顯示短暫 loading 態

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 左側 Sidebar 240px 展開 + 主區域 12-col grid，KPI 4 欄並排，圖表 8+4 分割 | 完整體驗，所有資訊一目了然 |
| Tablet (768-1279px) | Sidebar 收合為 64px 圖標模式 + 主區域 8-col grid，KPI 2x2 網格，圖表上下堆疊（各全寬） | 圖表區改為縱向排列；工單表格隱藏「鎖型型號」欄 |
| Mobile (<768px) | Sidebar 隱藏改為底部 Tab Bar + 主區域 4-col grid，KPI 單欄堆疊，圖表全寬堆疊 | 工單表格改為卡片列表模式；圖表可左右滑動；secondary KPI 收合至可展開區域 |

### 資料更新策略

- KPI 數值：WebSocket 即時推送（首選），降級為 30 秒 polling
- 圖表資料：頁面載入時請求一次，切換時間範圍時重新請求，不自動更新
- 最近工單列表：WebSocket 推送新工單時 prepend 至列表頂部（維持最多 10 筆），降級為 60 秒 polling
- 快取策略：TanStack Query staleTime 設為 30s（KPI）/ 5min（圖表）/ 1min（工單列表），背景 refetch 啟用
- 頁面切回（visibilitychange）：自動觸發所有 query invalidation

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/dashboard/overview` — 取得儀表板綜合資料（圖表資料 + 技師分佈），支援 query param `range=7d|14d|30d`
  - GET `/api/v1/dashboard/kpi` — 取得 6 項 KPI 即時數值（今日工單數、完工率、逾時工單、在線技師、AI 準確率、SLA 達標率）+ 對比基準值
  - GET `/api/v1/work-orders?limit=10&sort=-created_at` — 取得最近 10 筆工單摘要列表
  - WS `/ws/dashboard` — WebSocket 頻道，推送 KPI 即時變更事件與新工單通知
- **request_headers**:
  - Authorization: Bearer {access_token}
  - X-Tenant-ID: {tenant_id}（多租戶隔離）
- **error_cases**:
  - 網路錯誤：顯示頂部 Toast "網路連線異常，資料可能非最新"，使用 TanStack Query 快取資料繼續顯示，背景持續重試
  - API 錯誤（5xx）：對應 Section 顯示 inline 錯誤訊息 + 重試按鈕，其餘 Section 不受影響（獨立 error boundary）
  - API 錯誤（4xx）：顯示具體錯誤訊息（如 "查詢參數錯誤"）
  - 權限不足（401/403）：導向登入頁 `/login`，保留當前路由作為 redirect 參數
  - WebSocket 斷線：自動重連（指數退避 1s → 2s → 4s → 最大 30s），3 次失敗後切換 polling 模式
  - 資料格式異常：前端 Zod schema 驗證失敗時，記錄錯誤至 console + Sentry，顯示 "資料異常" 提示

---

## [EXCEPTION TO GLOBAL RULES]

- KPI 卡片數值使用 36px/700 字重（text.kpi 特規），超出一般 Design System 的 Body 字級範圍，僅限於此頁面 KPI 區塊使用
- 逾時工單數值的紅色閃爍動畫為此頁面專屬警示效果，其餘頁面不得使用閃爍動畫
- WebSocket 即時更新的 pulse 動畫（scale + color transition）僅限 Dashboard KPI 卡片

---

## [ACCEPTANCE CRITERIA]

- [ ] 所有 7 個 Section 功能正常，畫面完整渲染
- [ ] 4 張主要 KPI 卡片數值正確顯示，text.kpi（36px/700）樣式套用正確
- [ ] 2 張輔助 KPI 卡片（AI 準確率、SLA 達標率）正確顯示
- [ ] KPI 數值根據閾值正確變色（綠 / 琥珀 / 紅）
- [ ] 逾時工單 > 0 時紅色閃爍動畫正常觸發
- [ ] WebSocket 連線成功時 KPI 即時更新，pulse 動畫正常播放
- [ ] WebSocket 斷線時自動降級為 30 秒 polling，狀態指示器正確反映連線狀態
- [ ] 工單趨勢折線圖正確渲染雙折線 + 區域填充 + Tooltip + 時間範圍切換
- [ ] 技師狀態圓餅圖正確渲染 4 種狀態 + 中央總數 + 圖例
- [ ] 最近工單表格顯示 10 筆，展開功能正常，狀態 Badge 顏色正確
- [ ] 點擊 KPI 卡片正確導航至對應篩選條件的列表頁
- [ ] Loading / Error / Empty 三態在所有 Section 均已實作
- [ ] RWD 三個斷點（Desktop / Tablet / Mobile）佈局行為正確
- [ ] Sidebar 展開 240px / 收合 64px / Mobile 隱藏行為正確
- [ ] API 錯誤時各 Section 獨立顯示錯誤，不影響其他區塊
- [ ] 首次載入完成時間 < 2 秒（含 API 回應）
- [ ] 符合 Design System 色彩規範（Primary #2563EB / Accent #F59E0B / BG #F8FAFC）
- [ ] 多租戶隔離正確，僅顯示當前租戶資料


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
