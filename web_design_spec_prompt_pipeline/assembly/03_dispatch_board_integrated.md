# Assembly Prompt: Dispatch Board 派工台

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

本次任務：根據上方 Global Guideline，設計並實作「Dispatch Board 派工台」。這是整個平台的核心頁面。

### [PAGE META]

- **page_name**: Dispatch Board 派工台
- **route_path**: `/work-orders/dispatch`
- **page_type**: dashboard / kanban（混合型態）
- **primary_goal**: 以列表、看板、地圖三種視角管理所有工單的派工流程，支援拖曳派工與 AI 推薦指派
- **secondary_goal**: 即時追蹤技師位置與工單 SLA 倒數，確保派工效率與服務時效
- **target_users**:
  - 主要：派工專員（全天使用，核心工作頁面）
  - 次要：品牌管理員（監控工單狀態與技師分佈）
- **entry_point**: 側邊欄「工單管理 → 派工台」/ Dashboard 快捷操作「前往派工台」
- **expected_time_on_page**: 5-30 分鐘（持續操作，非快速瀏覽）

---

### [STRUCTURE: SECTIONS]

共 8 個主要 Section：

1. **view_mode_switcher** — 視圖模式切換
   - section_type: tab_switcher
   - section_purpose: 在列表、看板、地圖三種視圖間切換
   - 三個 Tab：列表視圖（List）/ 看板視圖（Kanban）/ 地圖視圖（Map）

2. **filter_toolbar** — 篩選工具列
   - section_type: filter_bar
   - section_purpose: 篩選工單狀態、優先度、技師、日期範圍、搜尋

3. **list_view** — 列表視圖
   - section_type: data_table
   - section_purpose: 以表格方式顯示所有工單，支援排序、篩選、批量操作

4. **kanban_view** — 看板視圖
   - section_type: kanban_board
   - section_purpose: 以 5 欄看板呈現工單流程狀態，支援 @dnd-kit 拖曳派工

5. **map_view** — 地圖視圖
   - section_type: map_split
   - section_purpose: Google Maps 分割畫面，左側工單列表 + 右側地圖，釘選未指派工單與技師位置

6. **manual_assign_modal** — 手動指派 Modal
   - section_type: modal
   - section_purpose: 選擇指派技師，顯示 AI 推薦排名與評分細項

7. **order_detail_drawer** — 工單詳情側滑面板
   - section_type: drawer
   - section_purpose: 不離開派工台即可檢視工單完整詳情

8. **realtime_status_bar** — 即時狀態列
   - section_type: status_indicator
   - section_purpose: WebSocket 連線狀態 + 最後更新時間 + 在線技師數

---

### [SECTION COMPONENT SPEC]

#### Section 1: view_mode_switcher

- **layout**: 頁面頂部，與 filter_toolbar 同列，左對齊
- **elements**:
  - tab_group: shadcn/ui `<Tabs>` / required
    - Tab 1: 圖標 List + "列表" — 預設選中
    - Tab 2: 圖標 Columns3 + "看板"
    - Tab 3: 圖標 MapPin + "地圖"
  - active_tab 狀態存儲於 URL query param `?view=list|kanban|map`（Zustand + URL sync）
- **states**:
  - default: 目前 tab 底部 2px #2563EB 指示線 + 文字 Primary 色
  - hover: 背景 #F1F5F9
  - transition: 切換時 content 區域 fade-in 動畫 150ms

#### Section 2: filter_toolbar

- **layout**: 頁面頂部，view_mode_switcher 右側，水平排列篩選器
- **elements**:
  - status_filter: shadcn/ui `<Select>` multi / required
    - 選項：全部 / 待指派 / 已派工 / 進行中 / 已完工 / 異常
    - 預設選中：全部
  - priority_filter: shadcn/ui `<Select>` / optional
    - 選項：全部 / 緊急 / 急件 / 一般
  - technician_filter: shadcn/ui `<Select>` searchable / optional
    - 搜尋技師姓名，可多選
  - date_range: shadcn/ui `<DateRangePicker>` / optional
    - 預設：今日
  - search_input: shadcn/ui `<Input>` / required
    - placeholder "搜尋工單編號、客戶名稱..."
    - debounce 300ms
  - reset_btn: shadcn/ui `<Button>` variant="ghost" / optional
    - "清除篩選"
- **states**:
  - default: 篩選器一字排開
  - active_filter: 有篩選條件時顯示 badge 數字 + 清除按鈕
  - mobile: 收折為 "篩選" 按鈕，點擊展開 Sheet

#### Section 3: list_view（view=list 時顯示）

- **layout**: 全寬資料表格，支援列排序、行選取、批量操作
- **elements**:
  - table: shadcn/ui `<Table>` / required
    - 欄位：
      - checkbox（批量選取）
      - 工單編號（WO-YYYYMMDD-XXXX，Mono 字體，可點擊開啟 Drawer）
      - 客戶名稱
      - 鎖型品牌型號
      - 問題摘要（最多 30 字，overflow ellipsis）
      - 狀態 Badge（語義色）
      - 優先度 Badge
      - SLA 倒數（綠色 >2h / 琥珀色 30min-2h / 紅色 <30min + pulse）
      - 指派技師（Avatar + Name，未指派顯示「指派」按鈕）
      - 操作（DropdownMenu: 指派、查看、編輯、取消）
    - 預設排序：優先度 DESC → SLA 倒數 ASC
  - batch_action_bar: 選取列時頂部浮現操作列
    - "已選取 N 筆" + 批量指派按鈕 + 批量變更狀態
  - pagination: shadcn/ui `<Pagination>` / required
    - 每頁 20 筆，顯示總頁數
- **states**:
  - default: 表格正常渲染，奇偶列背景交替
  - hover: 列背景 #EFF6FF
  - loading: Skeleton rows
  - error: inline 錯誤 + 重試
  - empty: "沒有符合篩選條件的工單" + CTA 清除篩選
  - selected: checkbox 勾選 + 列背景 #DBEAFE

#### Section 4: kanban_view（view=kanban 時顯示）

- **layout**: 5 欄水平看板，每欄等寬，水平可滾動，使用 @dnd-kit/core 實現拖曳
- **columns（5 欄）**:
  1. 待指派 (Pending) — 標題色 #6366F1 — 欄頂 badge 顯示工單數
  2. 已派工 (Assigned) — 標題色 #8B5CF6
  3. 進行中 (Active) — 標題色 #3B82F6
  4. 已完工 (Completed) — 標題色 #10B981
  5. 異常 (Exception) — 標題色 #EF4444
- **kanban_card**: 每張卡片元素
  - order_id: Caption Mono / required — "WO-XXXX"
  - customer_name: Body SM Bold / required
  - lock_model: Caption / required — 品牌 + 型號
  - tech_avatar: Avatar 24x24 / optional — 已指派時顯示技師頭像
  - sla_countdown: Badge / required
    - 綠色：剩餘 >2 小時
    - 琥珀色：剩餘 30 分鐘 - 2 小時
    - 紅色 + pulse 動畫：剩餘 <30 分鐘
  - priority_dot: 右上角小圓點 — 一般(不顯示) / 急件(琥珀) / 緊急(紅)
  - 卡片樣式：bg-white，圓角 LG (8px)，shadow-sm，padding 12px，間距 8px
- **drag_behavior（@dnd-kit）**:
  - 拖曳中：卡片 shadow-kanban（0 8px 16px rgba(37,99,235,0.15)），opacity 0.9，scale(1.02)
  - 放置區：目標欄位頂部顯示藍色虛線 placeholder
  - 放置成功：optimistic UI 立即移動卡片 → 呼叫 PATCH API → 失敗時 rollback + Toast "狀態更新失敗，已復原"
  - 拖曳限制：只能往「合法下一狀態」拖曳（待指派→已派工、已派工→進行中、進行中→已完工/異常）
  - 待指派→已派工：放置時自動彈出 Manual Assign Modal
- **states**:
  - default: 5 欄並排，每欄內卡片垂直排列，欄內可垂直滾動
  - loading: 每欄顯示 3 張 Skeleton 卡片
  - error: 看板區域 inline 錯誤 + 重試
  - empty_column: 欄內顯示虛線框 + "沒有工單"
  - dragging: 卡片浮起 + 拖曳陰影 + 目標欄 highlight
- **copy_constraints**: 卡片客戶名稱最多 8 字；問題摘要不在卡片上顯示（hover tooltip 或展開）

#### Section 5: map_view（view=map 時顯示）

- **layout**: 分割畫面 — 左側 40%（工單列表面板）+ 右側 60%（Google Maps），可拖曳調整分割比例
- **map_elements（@vis.gl/react-google-maps）**:
  - unassigned_pins: 紅色圓形標記 / required
    - 代表未指派工單的客戶位置
    - 點擊 → 彈出 Popup 顯示工單摘要 + 「指派」按鈕
    - 多筆同區域 → cluster 聚合標記
  - technician_pins: 藍色圓形標記 / required
    - 代表技師目前位置（GPS 即時更新）
    - 圖標含技師頭像縮圖
    - 點擊 → 彈出 Popup 顯示技師資訊（姓名、狀態、目前工單、技能標籤）
    - 空閒技師：藍色實心；執行中：藍色半透明；離線：灰色
  - route_line: Polyline / optional
    - 選中工單 + 技師時，顯示路線預覽（虛線）
- **left_panel_elements**:
  - 工單卡片列表，按距離排序
  - 每張卡片：工單編號 + 客戶名稱 + 地址 + 狀態 Badge + SLA 倒數
  - 點擊卡片 → 地圖飛至對應位置 + 高亮 pin
  - 卡片上「指派」按鈕 → 開啟 Manual Assign Modal
- **interaction**:
  - 點擊紅色 pin → 左側對應卡片高亮滾動至可視區
  - 點擊藍色技師 pin → 顯示可指派此技師的工單清單
  - 拖曳紅色 pin 至藍色技師 pin → 觸發快速指派 → 開啟確認 Dialog
- **states**:
  - default: 地圖載入完成，顯示所有 pins
  - loading: 左側 Skeleton 卡片 + 右側地圖載入動畫
  - error: 地圖載入失敗 → 顯示靜態區域圖 + 重試按鈕
  - empty: "目前沒有可顯示的工單" + 調整篩選建議

#### Section 6: manual_assign_modal

- **layout**: shadcn/ui `<Dialog>` 居中 Modal，寬度 600px，max-height 80vh，可滾動
- **elements**:
  - modal_title: H2 "指派技師" + 工單編號
  - order_summary: 卡片 / required
    - 客戶名稱、地址、鎖型型號、問題摘要、SLA 剩餘時間
  - candidate_list: 列表 / required — 顯示 Top 5 推薦技師
    - 每位技師顯示：
      - Avatar 40x40 + 姓名 + 技能標籤（Badge 陣列）
      - AI 推薦排名：第 1 名旁顯示 ⭐ AI 推薦 Badge（背景 #F59E0B/10，文字 #D97706）
      - 綜合評分（百分制）
      - 評分細項展開（Collapsible）：距離分數 / 技能匹配 / 歷史評價 / 負載平衡
      - 目前狀態：空閒（綠色）/ 執行中（藍色 + "預計 HH:MM 完工"）/ 離線（灰色，不可選）
      - 預估到達時間
    - 選中狀態：左側 3px #2563EB 指示條 + 背景 #EFF6FF
  - assign_note: shadcn/ui `<Textarea>` / optional — 備註欄位
  - action_buttons:
    - "確認指派" — Primary Button #2563EB，disabled 直到選擇技師
    - "取消" — Ghost Button
- **states**:
  - loading: candidate_list 顯示 5 列 Skeleton
  - error: "無法取得推薦技師" + 重試
  - empty: "目前無可用技師" + 建議稍後再試
  - submitting: "確認指派" 按鈕 disabled + spinner
  - success: Modal 關閉 + Toast "已成功指派 {技師名} 至 {工單編號}"

#### Section 7: order_detail_drawer

- **layout**: shadcn/ui `<Sheet>` 右側滑入，寬度 480px
- **elements**:
  - 工單完整資訊：編號、狀態、優先度、建立時間、SLA 截止時間
  - 客戶資訊：姓名、電話、地址、鎖型品牌型號
  - AI 診斷結果：問題分類 + 信心指數 + 建議處理方式
  - 指派技師：頭像 + 姓名 + 聯絡方式（已指派時）
  - 操作歷程：Timeline 元件，顯示工單狀態變更紀錄
  - 操作按鈕：指派/重新指派、變更狀態、編輯、取消工單
- **states**:
  - loading: Skeleton 全頁
  - error: inline 錯誤 + 重試

#### Section 8: realtime_status_bar

- **layout**: 頁面頂部右側，與 filter_toolbar 同列
- **elements**:
  - ws_status: StatusDot（綠/琥珀/紅）+ tooltip
  - last_updated: Caption "最後更新 HH:MM:SS"
  - online_count: Caption "在線技師 N 人"
- **states**: 同 Dashboard realtime_status_bar 規範

---

### [WORK ORDER STATE MAPPING]

13 種工單狀態對應 6 種語義色：

| 狀態 | 語義色 | Hex | 看板欄位 |
|------|--------|-----|---------|
| 待客服確認 | Pending | #6366F1 | 待指派 |
| 待指派 | Pending | #6366F1 | 待指派 |
| 已指派-待接受 | Assigned | #8B5CF6 | 已派工 |
| 已接受-待出發 | Assigned | #8B5CF6 | 已派工 |
| 前往中 | Active | #3B82F6 | 進行中 |
| 抵達現場 | Active | #3B82F6 | 進行中 |
| 維修中 | Active | #3B82F6 | 進行中 |
| 待客戶確認完工 | Active | #3B82F6 | 進行中 |
| 已完工 | Success | #10B981 | 已完工 |
| 已結案 | Success | #10B981 | 已完工 |
| 客戶取消 | Danger | #EF4444 | 異常 |
| 逾時未處理 | Danger | #EF4444 | 異常 |
| 需重新指派 | Warning | #F59E0B | 異常 |

---

### [INTERACTION & STATE FLOW]

1. 頁面載入 → 預設 List View → `GET /api/v1/work-orders?page=1&limit=20` → 表格渲染
2. 切換至 Kanban View → `GET /api/v1/work-orders?group_by=kanban_status` → 5 欄看板渲染
3. 切換至 Map View → 並行請求工單列表 + `GET /api/v1/technicians/locations` → 地圖 + 列表渲染
4. WebSocket 連線 → 訂閱工單狀態變更 + 技師位置更新頻道
5. Kanban 拖曳卡片 → optimistic UI 更新 → `PATCH /api/v1/work-orders/{id}/status` → 成功保持 / 失敗 rollback + Toast
6. 拖曳至「已派工」欄 → 自動彈出 Manual Assign Modal → `GET /api/v1/work-orders/{id}/candidates` → 載入 Top 5 推薦
7. Modal 選擇技師 + 確認 → `PATCH /api/v1/work-orders/{id}/assign` → 成功 Toast + 卡片更新技師頭像
8. 地圖 Pin 點擊 → Popup 顯示摘要 → 「指派」按鈕 → 同 Step 6
9. 列表行點擊 → 右側 Drawer 滑出顯示詳情
10. 篩選器變更 → debounce 300ms → API 重新查詢 → 所有視圖同步更新
11. WebSocket 新工單通知 → Kanban「待指派」欄頂部插入 + 閃爍提示 + 桌面通知（需授權）

---

### [DATA & API]

- **uses_api**: true
- **endpoints**:
  - `GET /api/v1/work-orders` — 工單列表（支援 query params: page, limit, status, priority, technician_id, date_from, date_to, search, sort, group_by）
  - `PATCH /api/v1/work-orders/{id}/status` — 更新工單狀態
  - `PATCH /api/v1/work-orders/{id}/assign` — 指派技師（body: { technician_id, note? }）
  - `GET /api/v1/work-orders/{id}/candidates` — 取得 Top 5 AI 推薦技師（含評分細項）
  - `GET /api/v1/work-orders/{id}` — 工單完整詳情
  - `GET /api/v1/technicians/locations` — 所有技師目前 GPS 位置
  - `WS /ws/dispatch` — WebSocket 頻道，推送：工單狀態變更、新工單、技師位置更新、SLA 即將到期警示
- **request_headers**:
  - `Authorization: Bearer {access_token}`
  - `X-Tenant-ID: {tenant_id}`
- **快取策略（TanStack Query）**:
  - 工單列表: staleTime 30s，WebSocket invalidation
  - 技師位置: staleTime 10s，WebSocket 即時更新
  - 候選技師: staleTime 0（每次開啟 Modal 重新請求）
  - 工單詳情: staleTime 1min
- **error_cases**:
  - 拖曳 API 失敗 → rollback UI + Toast "狀態更新失敗，已復原原始狀態"
  - 指派 API 失敗 → Modal 保持開啟 + inline error "指派失敗：{原因}" + 重試按鈕
  - 地圖載入失敗 → fallback 靜態圖 + 重試
  - WebSocket 斷線 → 降級 polling（工單 30s / 位置 15s）

---

### [RWD 行為]

| 斷點 | 可用視圖 | 佈局差異 |
|------|---------|---------|
| Desktop (>1024px) | 列表 + 看板 + 地圖，三種皆可 | Sidebar 240px + 全功能體驗；Kanban 使用 full viewport width |
| Tablet (768-1024px) | 列表 + 地圖（隱藏看板 Tab） | Sidebar 收合 64px；地圖改為上下分割（上 50% 地圖 + 下 50% 列表）；表格隱藏部分欄位 |
| Mobile (<768px) | 僅列表 | Sidebar 隱藏改底部 Tab Bar；表格改為卡片列表；篩選器收折為 Sheet；Manual Assign Modal 改為全螢幕 Sheet |

---

### [ACCEPTANCE CRITERIA]

- [ ] 三種視圖（列表 / 看板 / 地圖）切換正常，URL query param 同步
- [ ] 列表視圖：表格排序、篩選、分頁、批量操作功能完整
- [ ] 看板視圖：5 欄正確渲染，@dnd-kit 拖曳流暢
- [ ] 拖曳至「已派工」→ 自動彈出指派 Modal
- [ ] 拖曳限制：僅允許合法狀態轉換
- [ ] Optimistic UI：拖曳立即生效，API 失敗時正確 rollback
- [ ] Kanban 卡片：工單編號、客戶、鎖型、技師頭像、SLA 倒數皆正確
- [ ] SLA 倒數色彩：綠(>2h) / 琥珀(30min-2h) / 紅+pulse(<30min)
- [ ] 地圖視圖：紅色 pin（未指派）+ 藍色 pin（技師）正確渲染
- [ ] 地圖 pin 點擊 → Popup → 指派功能正常
- [ ] Manual Assign Modal：Top 5 候選人 + AI 推薦 Badge + 評分細項
- [ ] 13 種工單狀態正確對應 6 種語義色
- [ ] WebSocket 即時更新：新工單、狀態變更、技師位置
- [ ] 篩選器功能完整，支援多條件組合
- [ ] Order Detail Drawer 右側滑出，資訊完整
- [ ] Loading / Error / Empty 三態所有 Section 已處理
- [ ] RWD 三斷點佈局正確（Desktop 全功能 / Tablet 無看板 / Mobile 僅列表）
- [ ] 效能：Kanban 100+ 卡片不卡頓；地圖 50+ pins 渲染正常
- [ ] 無障礙：拖曳操作提供鍵盤替代方案（Enter 選取 + 方向鍵移動）

---

## === EXCEPTION RULES ===

1. **Kanban 全視口寬度**：看板視圖突破標準 1440px max-width 限制，使用 `w-screen` 全視口寬度以容納 5 欄看板。Sidebar 仍保持 240px，看板區域佔據剩餘全部寬度。各欄最小寬度 240px，超出時水平滾動。
2. **Kanban 專屬陰影**：拖曳中的卡片使用 shadow-kanban（`0 8px 16px rgba(37,99,235,0.15)`），此陰影值為品牌系統特規，僅限 Kanban 拖曳使用。
3. **地圖分割畫面**：地圖視圖的分割佈局突破標準 12-col grid，改為左右百分比分割（40/60），分割線可拖曳調整。
4. **Mobile 視圖限制**：Mobile 斷點下隱藏看板與地圖 Tab，僅保留列表視圖，此為刻意降級而非遺漏。

---

## === OUTPUT REQUIREMENTS ===

### Step 1: 結構確認
列出本頁面的 8 個 sections、關鍵元件、資料流策略：
- view_mode_switcher → Tabs 元件（Zustand + URL sync）
- filter_toolbar → 多重篩選器（debounce 300ms → API query）
- list_view → Table + Pagination（TanStack Query，staleTime 30s）
- kanban_view → 5 欄 DnD Board（@dnd-kit/core，optimistic UI + rollback）
- map_view → Google Maps split view（@vis.gl/react-google-maps + 技師位置 WebSocket）
- manual_assign_modal → AI 推薦候選人（GET candidates，staleTime 0）
- order_detail_drawer → Sheet 詳情面板（GET work-order detail）
- realtime_status_bar → WebSocket 狀態指示

### Step 2: 設計決策說明
提供 2-3 個關鍵設計決策與理由：
1. 三種視圖設計：列表適合批量操作、看板適合流程追蹤、地圖適合空間派工，覆蓋所有派工場景
2. Optimistic UI + Rollback：拖曳派工需要零延遲回饋，但必須保障資料一致性
3. AI 推薦 Badge：第一名候選人特別標示，降低派工專員決策成本

### Step 3: 實作方案
Option A: 完整 React/Next.js 程式碼（使用 shadcn/ui + Tailwind）

請產出以下檔案結構：
```
app/(admin)/work-orders/dispatch/
├── page.tsx                        # 頁面主元件 + view mode routing
├── components/
│   ├── ViewModeSwitcher.tsx         # Tabs 切換
│   ├── FilterToolbar.tsx            # 篩選工具列
│   ├── ListView/
│   │   ├── ListView.tsx             # 列表視圖容器
│   │   ├── WorkOrderTable.tsx       # 工單表格
│   │   └── BatchActionBar.tsx       # 批量操作列
│   ├── KanbanView/
│   │   ├── KanbanView.tsx           # 看板視圖容器
│   │   ├── KanbanColumn.tsx         # 單欄元件
│   │   ├── KanbanCard.tsx           # 工單卡片
│   │   └── useDndDispatch.ts        # @dnd-kit 拖曳邏輯 hook
│   ├── MapView/
│   │   ├── MapView.tsx              # 地圖視圖容器
│   │   ├── DispatchMap.tsx          # Google Maps 元件
│   │   ├── MapOrderPanel.tsx        # 左側工單面板
│   │   └── PinPopup.tsx             # Pin 彈出資訊
│   ├── ManualAssignModal.tsx        # 手動指派 Modal
│   ├── OrderDetailDrawer.tsx        # 工單詳情 Drawer
│   └── RealtimeStatusBar.tsx        # 即時狀態列
├── hooks/
│   ├── useWorkOrders.ts             # 工單列表 TanStack Query
│   ├── useDispatchWebSocket.ts      # WebSocket 訂閱
│   ├── useTechnicianLocations.ts    # 技師位置 hook
│   └── useAssignCandidates.ts       # AI 推薦候選人 hook
├── stores/
│   └── dispatchViewStore.ts         # Zustand：view mode + filter state
└── types.ts                         # TypeScript 型別（WorkOrder, KanbanColumn, Candidate 等）
```

### 品質檢查
- [ ] 色彩系統一致性（6 語義色正確對應 13 種工單狀態）
- [ ] 字體層級正確（H1 標題、Body 表格、Caption 時間、Mono 工單編號）
- [ ] 元件風格統一（shadcn/ui Table, Tabs, Select, Dialog, Sheet, Badge）
- [ ] 響應式設計完整（Desktop 三視圖 / Tablet 二視圖 / Mobile 一視圖）
- [ ] 所有狀態已處理（Loading / Error / Empty / Dragging / Selected / Disabled）
- [ ] 無障礙支援（鍵盤拖曳替代 / ARIA live region 狀態變更通知 / 色彩對比 ≥4.5:1）
- [ ] 效能指標達標（Kanban 虛擬滾動 / 地圖 marker clustering / debounce 篩選 / lazy load 視圖）

---

執行優先順序：Global 規範 > Page 特定需求 > Exception
Assembly 日期：2026-04-21
Brand System 版本：v1.0
