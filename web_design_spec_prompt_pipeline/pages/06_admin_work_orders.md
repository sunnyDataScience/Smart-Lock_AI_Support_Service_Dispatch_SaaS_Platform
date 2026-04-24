# Page-Level Prompt: 工單管理與派工板

> 本平台最核心、最複雜的頁面。整合列表、看板、地圖三種視圖模式，支援工單全生命週期管理與智能派工操作。
> 依據 `02_smartlock_dispatch_brand_system.md` 風格 A（列表）+ B（Kanban）+ C（地圖）組合方案。

---

## [PAGE META]

- **page_name**: 工單管理與派工板 (Work Orders & Dispatch Board)
- **route_path**: `/work-orders`（列表視圖）、`/work-orders/dispatch`（看板/地圖派工板）
- **page_type**: list + kanban + map (三視圖切換)
- **ia_pages**: A11
- **openapi_ops**: listWorkOrders, assignWorkOrder, listDispatchCandidates
- **asyncapi_ops**: subscribeWorkOrderUpdates
- **primary_goal**: 讓管理員即時掌握所有工單狀態，並高效完成派工、狀態變更、批次操作
- **secondary_goal**: 透過地圖視圖優化派工地理決策；透過看板視圖視覺化工單流程瓶頸
- **target_users**:
  - 主要：客服主管、營運管理者（每日高頻使用，日均操作 50-200 次）
  - 次要：品牌商管理者（低頻查看整體工單狀態）
- **entry_point**: 側邊導航「📋 工單管理」→「工單列表」或「派工板」；Dashboard KPI 卡片點擊跳轉
- **expected_time_on_page**: 5-30 分鐘（高頻操作頁，管理員可能長時間停留監控）

---

## [STRUCTURE: SECTIONS]

1. **page_header**
   - section_type: page_title + breadcrumb
   - section_purpose: 顯示頁面標題與導航路徑

2. **toolbar**
   - section_type: filter_bar + view_toggle
   - section_purpose: 提供搜尋、篩選、日期範圍、品牌篩選與三種視圖切換

3. **list_view**
   - section_type: sortable_table
   - section_purpose: 預設視圖，以表格形式展示所有工單，支援排序、批次操作、行點擊導航

4. **kanban_view**
   - section_type: drag_drop_board
   - section_purpose: 核心派工視圖，以 5 欄看板視覺化工單流程，支援拖拉變更狀態

5. **map_view**
   - section_type: split_panel_map
   - section_purpose: 地理視圖，左側工單列表 + 右側 Google Maps，最佳化地理派工決策

6. **manual_assign_modal**
   - section_type: modal_dialog
   - section_purpose: AI 推薦技師匹配面板，顯示 Top 5 候選人與分數細節

7. **batch_action_bar**
   - section_type: sticky_action_bar
   - section_purpose: 批次選取工單後的浮動操作列

---

## [SECTION COMPONENT SPEC]

### Section: page_header

- **layout**: 全寬單列，左對齊
- **elements**:
  - breadcrumb: Breadcrumb / required / 「首頁 > 工單管理 > 工單列表」或「首頁 > 工單管理 > 派工板」
  - page_title: H1 (text.heading.xl) / required / 「工單管理」
  - subtitle_stats: Body SM / optional / 即時統計：「共 {total} 筆工單 | 待指派 {pending} | 逾時 {overdue}」，逾時數字以 `color.error` (#EF4444) 顯示
- **states**:
  - default: 顯示標題與即時統計
  - loading: 統計數字部分顯示 Skeleton（短橫條）
- **copy_constraints**: 標題固定「工單管理」4 字；統計摘要最多 60 字

---

### Section: toolbar

- **layout**: 全寬單列，水平排列，元素間距 `space.3` (12px)；當空間不足時換行（flex-wrap）
- **elements**:
  - search_input: SearchInput / required / placeholder「搜尋工單編號、客戶姓名、地址...」/ 支援即時搜尋（debounce 300ms）/ 左側 Search icon / 輸入後右側顯示清除 X 按鈕
  - status_filter: MultiSelect / required / 標籤「狀態」/ 13 個選項，每個選項前綴對應語義色圓點：
    - Indigo 圓點：已建立 (created)
    - Violet 圓點：已派工 (assigned)
    - Blue 圓點：已接受 (accepted)、進行中 (in_progress)
    - Amber 圓點：範圍變更 (scope_changed)、缺料中 (material_pending)、延遲中 (delayed)
    - Emerald 圓點：已完工 (completed)、已確認 (confirmed)、已歸檔 (archived)
    - Red 圓點：返工中 (rework_required)、已取消 (cancelled)、爭議中 (disputed)
    - 支援多選，已選中狀態顯示為 Badge pills
    - 快捷群組按鈕：「全部」「進行中」「異常」「已完成」
  - date_range_picker: DateRangePicker / required / 預設「最近 7 天」/ 快捷選項：今天、昨天、最近 7 天、最近 30 天、本月、自訂範圍
  - brand_filter: Select / required / 標籤「品牌」/ 下拉選項從 API 動態載入品牌列表 / 含「全部品牌」選項
  - view_toggle: SegmentedControl / required / 三個選項：
    - 「列表」icon: List / 對應 `/work-orders`
    - 「看板」icon: Kanban / 對應 `/work-orders/dispatch`
    - 「地圖」icon: Map / 對應 `/work-orders/dispatch?view=map`
    - 當前選中項以 `color.primary` (#2563EB) 填充，文字白色
  - create_button: Button Primary / optional / 「+ 新增工單」/ 僅管理員角色可見
- **states**:
  - default: 所有篩選器顯示預設值
  - active_filters: 篩選器旁顯示「已篩選 X 項條件」Badge + 「清除全部」連結
  - loading: 品牌下拉載入中顯示 Spinner
  - url_synced: 所有篩選條件同步至 URL query params（刷新保留、可分享連結）
- **copy_constraints**: 搜尋框 placeholder 最多 30 字
- **特殊行為**:
  - 所有篩選條件變更即時觸發列表更新（無需按搜尋鈕）
  - 篩選狀態透過 URL State 管理，支援瀏覽器前進/後退
  - Tablet 以下：搜尋框獨佔一行，篩選器收合至「篩選」按鈕展開 Drawer

---

### Section: list_view（預設視圖）

- **layout**: 全寬表格，卡片容器（白色背景 `color.bg.surface`，`radius.lg` 8px，`shadow.sm`）
- **elements**:
  - select_all_checkbox: Checkbox / required / 表頭左側全選框
  - table_header: TableHeader / required / 可排序欄位（點擊切換升序/降序/取消排序，當前排序欄顯示箭頭 icon）：
    - 「☐」: 寬 40px / Checkbox 選取欄
    - 「工單編號」: 寬 160px / 等寬字體 JetBrains Mono / 格式 `WO-YYYYMMDD-XXXX` / 可排序
    - 「客戶姓名」: 寬 120px / 可排序
    - 「地址」: 寬 auto (flex) / 超長截斷 ellipsis，hover tooltip 顯示完整地址 / 可排序
    - 「品牌/型號」: 寬 160px / 格式「{brand} {model}」/ 可排序
    - 「狀態」: 寬 120px / StatusBadge 元件 / 可排序
    - 「指派技師」: 寬 150px / Avatar (24px) + 姓名 / 未指派顯示灰色「未指派」/ 可排序
    - 「SLA 倒數」: 寬 120px / 動態倒數計時器 / 可排序
    - 「建立時間」: 寬 150px / 格式 `YYYY-MM-DD HH:mm` / 可排序，預設降序
    - 「操作」: 寬 80px / 三點選單 (MoreHorizontal icon)
  - table_row: TableRow / required / 每行高度 52px / 元素定義：
    - row_checkbox: Checkbox / 勾選後行背景變為 `color.primary.light` (#DBEAFE)
    - wo_number: 等寬字體，`color.primary` (#2563EB)，可點擊（導航至詳情頁）
    - customer_name: `text.body.md`，`color.text.primary`
    - address: `text.body.md`，`color.text.secondary`，單行截斷
    - brand_model: `text.body.md`，品牌 bold + 型號 normal
    - status_badge: StatusBadge 元件，使用 6 組語義色：
      - `created`：Indigo (#6366F1) Badge「已建立」
      - `assigned`：Violet (#8B5CF6) Badge「已派工」
      - `accepted`：Blue (#3B82F6) Badge「已接受」
      - `in_progress`：Blue (#3B82F6) Badge「進行中」
      - `scope_changed`：Amber (#F59E0B) Badge「範圍變更」
      - `material_pending`：Amber (#F59E0B) Badge「缺料中」
      - `delayed`：Amber (#F59E0B) Badge「延遲中」
      - `completed`：Emerald (#10B981) Badge「已完工」
      - `confirmed`：Emerald (#10B981) Badge「已確認」
      - `archived`：Emerald (#10B981) Badge「已歸檔」
      - `rework_required`：Red (#EF4444) Badge「返工中」
      - `cancelled`：Red (#EF4444) Badge「已取消」
      - `disputed`：Red (#EF4444) Badge「爭議中」
    - technician_cell: Avatar (24px 圓形) + 姓名；未指派時顯示灰色虛線圓 + 「未指派」灰字
    - sla_countdown: 倒數計時器元件：
      - 正常（剩餘 > 30 分鐘）：`color.text.secondary`，格式「剩餘 HH:mm」
      - 警告（剩餘 <= 30 分鐘）：`color.warning` (#F59E0B)，格式「剩餘 HH:mm」，文字 bold
      - 逾時：`color.error` (#EF4444)，格式「逾時 HH:mm」，文字 bold + pulse 動畫（opacity 0.5-1.0 循環，1.5s）
      - 已完工/已取消/已歸檔：顯示「--」灰字
    - created_at: `text.body.sm`，`color.text.secondary`
    - action_menu: IconButton Ghost / 點擊展開 Dropdown Menu：
      - 「查看詳情」→ 導航至 `/work-orders/[id]`
      - 「指派技師」→ 開啟 manual_assign_modal（僅 `created` 狀態可用）
      - 「取消工單」→ 確認 Modal →「確定要取消工單 {wo_number} 嗎？此操作無法復原。」（僅 `created`/`assigned` 狀態可用）
      - Divider
      - 「複製工單編號」→ 複製至剪貼簿 + Toast「已複製」
  - pagination: Pagination / required / 底部右對齊：
    - 每頁筆數選擇：10 / 25 / 50 / 100（預設 25）
    - 頁碼導航：上一頁 / 頁碼 / 下一頁
    - 總筆數顯示：「共 {total} 筆，第 {start}-{end} 筆」
- **states**:
  - default: 顯示工單表格，預設按建立時間降序排列
  - hover: 行背景變為 `color.bg.page` (#F8FAFC)，cursor pointer
  - selected: 勾選行背景 `color.primary.light` (#DBEAFE)，底部浮現 batch_action_bar
  - loading: 表格主體顯示 Skeleton rows（8 行），表頭保持不變
  - empty: 表格區域顯示空狀態插圖 + 標題「沒有符合條件的工單」+ 副標題「試著調整篩選條件，或新增一筆工單」+ CTA「清除篩選」Button Secondary + 「新增工單」Button Primary
  - error: 表格區域顯示錯誤狀態：紅色 Alert Banner「工單資料載入失敗（{error_message}）」+ 「重試」Button
  - sorting: 當前排序欄表頭加粗 + 箭頭 icon（升序 ↑ / 降序 ↓）
- **copy_constraints**: 地址欄截斷至 25 字（含省略號）；客戶姓名最多 10 字

---

### Section: kanban_view（核心星級功能）

- **layout**: 水平 5 欄佈局，每欄等寬（最小寬度 280px），水平捲動（Desktop 通常 5 欄剛好滿版）；欄間距 `space.4` (16px)；整體容器 padding `space.4`
- **elements**:
  - kanban_column: KanbanColumn / required / 5 欄定義：
    - **Column 1 — 待指派**:
      - header_label: 「待指派」
      - header_color: Indigo (#6366F1) 上邊框 3px
      - filter_states: [`created`]
      - count_badge: 數量 Badge，Indigo 背景白字，圓角 `radius.full`
    - **Column 2 — 已派工**:
      - header_label: 「已派工」
      - header_color: Violet (#8B5CF6) 上邊框 3px
      - filter_states: [`assigned`]
      - count_badge: Violet 背景白字
    - **Column 3 — 進行中**:
      - header_label: 「進行中」
      - header_color: Blue (#3B82F6) 上邊框 3px
      - filter_states: [`accepted`, `in_progress`]
      - count_badge: Blue 背景白字
    - **Column 4 — 已完工**:
      - header_label: 「已完工」
      - header_color: Emerald (#10B981) 上邊框 3px
      - filter_states: [`completed`]
      - count_badge: Emerald 背景白字
    - **Column 5 — 異常**:
      - header_label: 「異常」
      - header_color: Red (#EF4444) 上邊框 3px
      - filter_states: [`scope_changed`, `material_pending`, `delayed`, `rework_required`, `disputed`]
      - count_badge: Red 背景白字
    - 每欄結構：
      - column_header: 高度 48px / 左側欄名 (`text.heading.sm` 16px, 600) + 右側 count_badge (min-width 24px, 高度 24px, 圓角 full, 白字, 對應色背景)
      - column_body: 垂直捲動容器（max-height: calc(100vh - 240px)），自訂捲軸（4px 寬，圓角，淺灰色）
      - column_footer: 若該欄有更多未載入卡片，顯示「載入更多」Ghost Button
  - kanban_card: KanbanCard / required / 每張卡片結構：
    - 卡片容器：白色背景 `color.bg.surface`，`radius.lg` (8px)，`shadow.sm`，padding `space.4` (16px)，margin-bottom `space.3` (12px)，左側邊框 3px 使用對應狀態語義色
    - card_header: 水平排列
      - wo_number: `text.body.sm` (12px)，等寬字體 JetBrains Mono，`color.text.secondary`
      - status_badge: StatusBadge sm，對應 13 狀態語義色與文字
    - card_body: 垂直排列，margin-top `space.2` (8px)
      - customer_name: `text.body.md` (14px)，font-weight 600，`color.text.primary`，單行截斷
      - address: `text.body.sm` (12px)，`color.text.secondary`，單行截斷（最多 20 字 + ellipsis）
      - brand_model: `text.body.sm` (12px)，`color.text.secondary`，格式「{brand} {model}」
    - card_footer: 水平排列，justify-between，margin-top `space.3` (12px)，border-top 1px `color.border.default`，padding-top `space.2` (8px)
      - technician_info: Avatar (20px) + 姓名 (`text.body.sm`)；未指派時顯示灰色虛線圓 + 「未指派」
      - sla_timer: 倒數計時器
        - 正常（> 30min）：`text.body.sm`，`color.text.secondary`，格式「⏱ HH:mm」
        - 警告（<= 30min）：`text.body.sm`，`color.warning` (#F59E0B)，bold，格式「⏱ HH:mm」，卡片邊框變為 Amber
        - 逾時：`text.body.sm`，`color.error` (#EF4444)，bold，格式「⏱ 逾時 HH:mm」，卡片邊框變為 Red + pulse 動畫（border-color opacity 0.4-1.0 循環，1.5s）
    - card_click_area: 點擊卡片任意處（非拖拉手勢）→ 導航至 `/work-orders/[id]`
- **states**:
  - default: 5 欄顯示對應狀態工單，每欄垂直排列卡片
  - dragging_source: 被拖拉的卡片：
    - 提起時：shadow 變為 `shadow.kanban` (0 8px 16px rgba(37,99,235,0.15))
    - 原位置：留下虛線佔位框（dashed border `color.border.default`，高度等於卡片高度）
    - 卡片跟隨游標，scale(1.02)，opacity 0.95
    - z-index: 1000
  - dragging_target: 目標欄位：
    - 有效目標：欄背景變為 `color.primary.light` (#DBEAFE)，上邊框加粗至 4px
    - 插入位置：顯示 2px `color.primary` 水平指示線
    - 無效目標：欄保持不變（不可拖入），游標顯示 not-allowed
  - drop_confirm: 拖拉放下後（關鍵狀態轉換需確認 Modal）：
    - 非關鍵轉換（待指派→已派工）：直接執行 Optimistic UI
    - 關鍵轉換定義：
      - 任何狀態 → 已取消：必須確認「確定要取消工單 {wo_number} 嗎？」
      - 進行中 → 異常欄：必須確認「請選擇異常類型」+ 備註輸入框
      - 異常 → 進行中：必須確認「確認將此工單恢復為進行中？」
  - optimistic_update: 拖拉完成後：
    - 立即：卡片移至新欄位，舊欄位計數 -1，新欄位計數 +1
    - 背景：API PATCH 請求同步
    - 成功：無額外動作（已在正確位置）
    - 失敗：卡片 300ms ease 動畫回到原位 + Toast Error「狀態更新失敗：{error_message}。工單已恢復原狀態。」+ 計數回復
  - loading: 每欄顯示 3 張 Skeleton Card（高度 140px，圓角，灰色脈衝）
  - empty_column: 欄位無卡片時顯示：虛線框 + 「暫無工單」淺灰文字 + 對應 icon（如待指派欄顯示 inbox icon）
  - error: 全域錯誤 Banner + 「重試」按鈕
- **copy_constraints**: 客戶名最多 8 字；地址截斷至 20 字；品牌型號截斷至 15 字
- **拖拉規則（狀態轉換矩陣）**:
  - 待指派 → 已派工：允許（觸發指派 Modal，選擇技師後完成）
  - 已派工 → 進行中：允許（系統自動，通常由技師觸發，管理員可強制）
  - 進行中 → 已完工：允許
  - 進行中 → 異常：允許（需選擇異常類型）
  - 異常 → 進行中：允許（需確認）
  - 異常 → 已完工：允許
  - 已完工 → 異常：允許（返工場景）
  - 其他非相鄰欄位拖拉：禁止，顯示 not-allowed cursor
  - 已取消/已歸檔工單：不顯示於看板（僅列表可見）
- **鍵盤操作**:
  - Tab：在卡片間移動焦點
  - Space：拾起/放下當前焦點卡片
  - Arrow Left/Right：在拾起狀態下切換目標欄位
  - Arrow Up/Down：在欄內移動插入位置
  - Escape：取消拖拉，卡片回到原位

---

### Section: map_view

- **layout**: 水平分割面板，左 1/3（寬度 400px，min-width 320px）+ 右 2/3（剩餘寬度）；分割線可拖拉調整寬度（8px 拖拉區域）
- **elements**:
  - left_panel: ScrollableWorkOrderList / required /
    - panel_header: 「工單列表」+ 總數 Badge + 排序下拉（距離/時間/SLA）
    - work_order_items: WorkOrderListItem[] / required / 每個項目：
      - 容器：白色背景，padding `space.3` (12px)，border-bottom 1px `color.border.default`
      - wo_number: `text.body.sm`，等寬字體，`color.primary`
      - status_badge: StatusBadge sm
      - customer_name: `text.body.md`，font-weight 600
      - address: `text.body.sm`，`color.text.secondary`，2 行截斷
      - brand_model: `text.body.sm`，`color.text.secondary`
      - sla_timer: 同 Kanban 卡片規則
      - technician_name: `text.body.sm`；未指派顯示紅色「未指派」
      - assign_button: Button sm CTA (Amber) / 「指派」/ 僅 `created` 狀態顯示 / 點擊開啟 manual_assign_modal
    - item_hover: 背景變 `color.bg.page`；對應地圖 Pin 放大 1.3x + 彈出 tooltip
    - item_active: 左邊框 3px `color.primary`；地圖自動平移至對應 Pin + 開啟 Popup
    - pagination: 「載入更多」Ghost Button（infinite scroll 或手動載入）
  - right_panel: GoogleMap / required /
    - map_container: 容器 `radius.xl` (12px) 右側圓角（左側貼合分割線），overflow hidden
    - map_controls: 預設 Google Maps 控制（縮放、全螢幕、街景）+ 自訂圖層控制
    - work_order_pins: 工單圖釘 / required：
      - 未指派工單：紅色圖釘 (Red #EF4444)，圓形 marker 內顯示「!」icon
      - 已指派/進行中工單：藍色圖釘 (Blue #3B82F6)，圓形 marker
      - 已完工工單：綠色圖釘 (Emerald #10B981)，圓形 marker + 勾號
      - 異常工單：橙色圖釘 (Amber #F59E0B)，圓形 marker + 三角警告 icon
      - Pin 大小：32px（正常）/ 42px（hover/selected）
    - technician_pins: 技師圖釘 / required：
      - 圖示：藍色圓形 (Blue #3B82F6)，內含白色人形 icon，外圈 2px 白色邊框
      - 大小：36px
      - hover tooltip：技師姓名 + 「目前 {active_count} 個進行中工單」
      - 即時位置更新（WebSocket 推送，每 30 秒）
    - route_lines: 建議路線 / optional：
      - 灰色虛線 (Slate 400, #94A3B8)，線寬 2px
      - 連接技師位置與指派工單地址
      - 僅在選中特定技師或工單時顯示
    - cluster_markers: 聚合標記 / required：
      - 當縮放層級 < 13 時，鄰近 Pin 聚合為 Cluster
      - Cluster 顯示：圓形容器 + 數量文字（白字深色底）
      - 顏色：依最高優先級（紅 > 橙 > 藍 > 綠）
      - 點擊 Cluster → 地圖 zoom in 至展開所有 Pin
    - pin_popup: MapPopup / required / 點擊工單 Pin 時彈出：
      - 容器：白色背景，`shadow.lg`，`radius.lg`，padding `space.4`，max-width 320px
      - wo_number: `text.heading.sm`，等寬字體
      - status_badge: StatusBadge md
      - customer_name: `text.body.md`，bold
      - address: `text.body.sm`
      - brand_model: `text.body.sm`
      - sla_timer: 倒數計時器
      - technician_info: Avatar + 姓名（或「未指派」）
      - assign_button: Button Primary md / 「指派技師」/ 僅 `created` 狀態顯示 / 點擊開啟 manual_assign_modal
      - detail_link: Link / 「查看詳情 →」/ 導航至 `/work-orders/[id]`
      - close_button: IconButton Ghost / X icon / 右上角
- **states**:
  - default: 左側顯示篩選後工單列表，右側地圖顯示所有 Pin
  - pin_hover: Pin 放大 1.2x + tooltip（工單號 + 客戶名）
  - pin_selected: Pin 放大 1.3x + Popup 彈出 + 左側列表對應項目高亮滾動至可見
  - list_item_hover: 對應 Pin 高亮放大
  - loading: 左側 Skeleton list items；右側地圖底圖先載入，Pin 漸進出現
  - empty: 左側空狀態「該區域沒有工單」；右側地圖仍可互動
  - error: 地圖載入失敗時顯示灰色佔位圖 + 「地圖載入失敗，請檢查網路連線」+ 重試按鈕
  - map_loading: 地圖 loading 時顯示 Skeleton 矩形 + Spinner
- **copy_constraints**: Popup 內地址最多 30 字

---

### Section: manual_assign_modal（手動指派 Modal）

- **layout**: Modal lg (max-width 640px)，垂直排列
- **trigger**: 從列表行操作選單「指派技師」、Kanban 拖至「已派工」欄、地圖 Popup「指派技師」按鈕
- **elements**:
  - modal_header: 「指派技師 — {wo_number}」/ H3 (`text.heading.md`)
  - work_order_summary: 摘要卡片 / required / 背景 `color.bg.page`，padding `space.3`：
    - 客戶：{customer_name}
    - 地址：{address}
    - 品牌型號：{brand} {model}
    - 問題摘要：{symptom_summary}（截斷 2 行）
  - candidate_list_header: 「推薦技師」/ H4 + 說明文字「根據距離、技能、評分、負荷綜合評估」(`text.body.sm`，`color.text.secondary`)
  - candidate_list: TechnicianCandidateRow[] / required / 顯示 Top 5 匹配技師：
    - 每行容器：padding `space.4`，border-bottom 1px，hover 背景 `color.bg.page`
    - rank_number: 左側排名數字，#1 使用 `color.primary` 大字
    - ai_badge: 僅 #1 顯示 / Indigo (#6366F1) Badge「AI 推薦」/ 虛線邊框 + Indigo 背景 10% + Indigo 文字
    - avatar: 技師頭像 40px 圓形
    - technician_name: `text.body.md`，font-weight 600
    - rating_stars: 5 星評分，已填星 Amber (#F59E0B)，空星 Slate 200
    - score_breakdown: 4 項分數橫向排列，每項：
      - distance_score: icon MapPin + 「距離 {score}%」+ 實際距離「({distance} km)」
      - skills_score: icon Wrench + 「技能 {score}%」
      - rating_score: icon Star + 「評分 {score}%」
      - load_score: icon Activity + 「負荷 {score}%」+ 當前工單數「({current_load} 單)」
      - 分數以進度條（高度 4px，圓角，對應色填充）視覺化
    - total_score: 右側總分 Badge，格式「{total}分」，背景色依分數梯度：
      - >= 80：Emerald 背景
      - 60-79：Blue 背景
      - < 60：Amber 背景
    - current_status: `text.body.sm`，技師當前狀態：「空閒」(Emerald) / 「作業中 ({count} 單)」(Blue) / 「休息中」(Slate)
    - assign_button: Button Primary sm / 「指派」/ 每行右側
  - no_candidates_state: 無可用技師時：
    - 插圖 + 「目前沒有可用技師」
    - 建議操作：「擴大搜尋半徑」Button / 「稍後再試」Button
  - loading_state: 5 行 Skeleton Row（Avatar 圓 + 長條 + 短條）
  - modal_footer:
    - cancel_button: Button Secondary / 「取消」
    - 無「確定」按鈕（在每行點「指派」即完成）
- **states**:
  - default: 載入中 → 顯示 candidate_list
  - loading: Skeleton + Spinner + 文字「正在為您匹配最佳技師...」
  - loaded: 顯示 5 位候選技師
  - assigning: 點擊「指派」後，該行按鈕變為 Spinner + Disabled，其他行 Disabled
  - assigned_success: Modal 關閉 + Toast Success「已成功指派技師 {name} 至工單 {wo_number}」
  - assigned_failure: 按鈕恢復 + Toast Error「指派失敗：{error_message}」
  - empty: 無候選人時顯示 no_candidates_state
  - error: API 錯誤時顯示紅色 Alert + 重試按鈕
- **copy_constraints**: 問題摘要截斷至 50 字

---

### Section: batch_action_bar

- **layout**: 固定底部浮動列（sticky bottom），全寬，高度 64px，白色背景，`shadow.lg`（朝上），z-index 50
- **trigger**: 列表視圖中勾選 1 筆以上工單時從底部滑入（300ms ease-out）
- **elements**:
  - selected_count: 左側「已選取 {count} 筆工單」(`text.body.md`，`color.text.primary`)
  - select_all_link: Link / 「全選本頁 {page_count} 筆」或「全選全部 {total_count} 筆」
  - batch_assign_button: Button Primary / 「批次指派」/ icon UserPlus / 僅當所有選中工單為 `created` 狀態可用，否則 Disabled + tooltip「僅可批次指派「已建立」狀態的工單」
  - batch_cancel_button: Button Danger / 「批次取消」/ icon XCircle / 僅當所有選中工單為 `created` 或 `assigned` 狀態可用
  - clear_selection_button: Button Ghost / 「取消選取」/ icon X
- **states**:
  - visible: 有勾選時從底部滑入
  - hidden: 無勾選時滑出消失
  - batch_assigning: 點擊「批次指派」→ 開啟批次指派 Modal：
    - 選擇統一指派同一技師，或讓系統 AI 自動匹配各工單最佳技師
    - AI 自動匹配：顯示每筆工單的匹配結果預覽 → 確認後批次執行
  - batch_cancelling: 點擊「批次取消」→ 確認 Modal「確定要取消 {count} 筆工單嗎？此操作無法復原。」→ 確認後批次執行
  - processing: 按鈕變為 Spinner + 進度條「已處理 {done}/{total}」
  - partial_failure: Toast Warning「{success_count} 筆成功，{fail_count} 筆失敗」+ 失敗工單保持勾選

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入**：
   - 讀取 URL query params 恢復篩選條件
   - 並行請求：工單列表 API + 品牌列表 API
   - 根據 URL path 決定初始視圖模式（`/work-orders` = 列表，`/work-orders/dispatch` = 看板，`/work-orders/dispatch?view=map` = 地圖）
   - 載入完成後建立 WebSocket 連線

2. **視圖切換**：
   - 點擊 view_toggle → URL path 更新 → 保留所有篩選條件 → 新視圖載入對應資料
   - 列表 → 看板：不需額外請求（同一資料，不同展示）
   - 列表/看板 → 地圖：額外請求技師位置 API
   - 切換動畫：300ms fade transition

3. **篩選操作**：
   - 任一篩選條件變更 → debounce 300ms → URL query params 更新 → TanStack Query 重新請求 → 列表/看板/地圖同步更新
   - 支援組合篩選：狀態 AND 日期 AND 品牌 AND 搜尋關鍵字

4. **Kanban 拖拉派工**：
   - 拖起卡片 → shadow-kanban + 原位虛線佔位
   - 拖至有效目標欄 → 欄位高亮
   - 放下 → 判斷是否需確認 Modal
     - 不需確認 → Optimistic UI 立即更新 → 背景 API sync
     - 需確認 → 彈出確認 Modal → 確認後 Optimistic UI → 背景 API sync
   - 若拖至「待指派→已派工」→ 自動開啟 manual_assign_modal
   - API 失敗 → 回滾動畫 + Toast Error

5. **手動指派技師**：
   - 觸發 → 載入候選技師 API（傳入工單 ID）→ 返回 Top 5
   - 瀏覽候選人分數 → 點擊「指派」
   - Loading 狀態 → API PATCH → 成功：Modal 關閉 + Toast + 列表/看板/地圖即時反映
   - 失敗：Toast Error + 可重試

6. **地圖互動**：
   - 點擊工單 Pin → 彈出 Popup + 左側列表高亮
   - 點擊技師 Pin → Tooltip 顯示技師資訊
   - 左側列表 hover item → 對應 Pin 高亮放大
   - 左側列表 click item → 地圖平移 + zoom 至對應位置 + Popup
   - 縮放 → Cluster 聚合/展開

7. **批次操作**：
   - 勾選工單 → batch_action_bar 滑入
   - 點擊批次指派/取消 → 確認 → 處理 → 完成通知

8. **即時更新（WebSocket）**：
   - 新工單建立 → 列表頂部插入新行（閃爍高亮 2s）+ 看板「待指派」欄新增卡片 + 地圖新增 Pin
   - 工單狀態變更 → 列表 Badge 更新 + 看板卡片動畫移至新欄 + 地圖 Pin 顏色變更
   - 技師位置更新 → 地圖技師 Pin 平滑移動
   - 連線斷開 → 頂部 Warning Banner「即時連線中斷，資料可能未即時更新」+ 自動重連（指數退避）

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop LG (> 1440px) | 完整三視圖切換，Kanban 5 欄無需捲動 | 完整體驗，地圖分割面板 400px + 剩餘 |
| Desktop (1024-1440px) | 完整三視圖切換，Kanban 5 欄可能需水平捲動 | Kanban 欄最小寬度 260px |
| Tablet (768-1023px) | 列表 + 簡化地圖，無 Kanban 視圖 | view_toggle 僅顯示「列表」「地圖」；地圖視圖改為上下堆疊（上方地圖 50vh + 下方列表 50vh）；表格隱藏「地址」「品牌型號」欄位，點擊行展開顯示完整資訊 |
| Mobile (< 768px) | 僅列表視圖 | view_toggle 隱藏；表格改為卡片列表（每張卡片垂直排列所有欄位）；toolbar 篩選器收合至「篩選」按鈕開啟 Drawer；batch_action_bar 按鈕改為 icon only |

### 資料更新策略

- **工單列表**：TanStack Query，staleTime 30 秒，背景 refetch on window focus
- **Kanban 資料**：與列表共用 Query cache，不同展示邏輯
- **技師位置**：獨立 Query，30 秒輪詢 + WebSocket 增量更新
- **WebSocket 即時推送**：
  - Event: `work_order.created` → 新增工單
  - Event: `work_order.status_changed` → 狀態變更
  - Event: `work_order.assigned` → 技師指派
  - Event: `technician.location_updated` → 技師位置
- **Zustand Client State**：
  - `selectedWorkOrders: Set<string>` — 批次選取的工單 ID
  - `activeView: 'list' | 'kanban' | 'map'` — 當前視圖模式
  - `dragState: { cardId: string | null, sourceColumn: string | null }` — Kanban 拖拉狀態
  - `mapCenter: { lat: number, lng: number }` — 地圖中心點
  - `mapZoom: number` — 地圖縮放層級
- **URL State**：
  - `?status=created,assigned` — 篩選狀態
  - `?search=王小明` — 搜尋關鍵字
  - `?dateFrom=2026-04-01&dateTo=2026-04-21` — 日期範圍
  - `?brand=yale` — 品牌篩選
  - `?sort=created_at&order=desc` — 排序
  - `?page=1&pageSize=25` — 分頁
  - `?view=map` — 地圖視圖標記（於 dispatch 路由下）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/work-orders` — 取得工單列表（支援分頁、篩選、排序、搜尋）
    - Query params: `page`, `page_size`, `status[]`, `search`, `date_from`, `date_to`, `brand`, `sort_by`, `sort_order`
    - Response: `{ data: WorkOrder[], total: number, page: number, page_size: number }`
  - GET `/api/v1/work-orders/dispatch/candidates/{work_order_id}` — 取得指定工單的候選技師列表
    - Response: `{ candidates: TechnicianCandidate[], work_order_summary: WorkOrderSummary }`
    - TechnicianCandidate: `{ id, name, avatar_url, rating, distance_km, skills_match, current_load, total_score, score_breakdown: { distance_pct, skills_pct, rating_pct, load_pct }, is_ai_recommended, current_status }`
  - PATCH `/api/v1/work-orders/{id}/assign` — 指派技師至工單
    - Body: `{ technician_id: string }`
    - Response: `{ success: boolean, work_order: WorkOrder }`
  - PATCH `/api/v1/work-orders/{id}/status` — 變更工單狀態
    - Body: `{ status: string, note?: string, exception_type?: string }`
    - Response: `{ success: boolean, work_order: WorkOrder }`
  - POST `/api/v1/work-orders/{id}/batch-assign` — 批次指派
    - Body: `{ work_order_ids: string[], technician_id?: string, auto_match?: boolean }`
    - Response: `{ results: { work_order_id: string, success: boolean, error?: string }[] }`
  - POST `/api/v1/work-orders/batch-cancel` — 批次取消
    - Body: `{ work_order_ids: string[], reason: string }`
    - Response: `{ results: { work_order_id: string, success: boolean, error?: string }[] }`
  - GET `/api/v1/technicians/locations` — 取得所有技師即時位置
    - Response: `{ technicians: { id, name, lat, lng, active_orders_count, status }[] }`
  - GET `/api/v1/brands` — 取得品牌列表（供篩選器使用）
    - Response: `{ brands: { id, name, models: string[] }[] }`
- **WebSocket Events**:
  - Channel: `ws://api/v1/ws/work-orders`
  - Events:
    - `work_order.created`: `{ work_order: WorkOrder }`
    - `work_order.status_changed`: `{ work_order_id, old_status, new_status, actor, timestamp }`
    - `work_order.assigned`: `{ work_order_id, technician: TechnicianSummary }`
    - `technician.location_updated`: `{ technician_id, lat, lng, timestamp }`
- **error_cases**:
  - 網路錯誤：顯示頂部 Warning Banner「網路連線異常，部分資料可能未更新」+ 使用 TanStack Query 快取顯示陳舊資料
  - API 401 Unauthorized：導向登入頁
  - API 403 Forbidden：Toast Error「你沒有權限執行此操作」
  - API 404 Not Found：Toast Error「工單不存在或已被刪除」
  - API 409 Conflict：Toast Error「工單狀態已變更，請重新操作」+ 自動刷新列表
  - API 422 Validation Error：Toast Error 顯示具體驗證錯誤訊息
  - API 500 Server Error：Toast Error「伺服器錯誤，請稍後重試或聯繫管理員」+ 重試按鈕
  - WebSocket 斷線：頂部 Warning Banner + 指數退避自動重連（1s, 2s, 4s, 8s, max 30s）

---

## [EXCEPTION TO GLOBAL RULES]

- **Kanban 拖拉陰影**：使用品牌色陰影 `shadow.kanban` (0 8px 16px rgba(37,99,235,0.15))，超出標準 Shadow Token 定義
- **SLA 逾時動畫**：使用 CSS pulse 動畫（1.5s infinite），超出 Global System「禁止自訂 CSS 動畫超過 500ms」的規則，但因為是持續性狀態指示（非操作回饋），屬合理例外
- **地圖視圖全寬**：右側地圖面板不受 12 欄 Grid 最大寬度 1440px 限制，佔滿可用寬度
- **Kanban 水平捲動**：允許水平捲動以容納 5 欄，不受單頁垂直捲動的標準限制
- **WebSocket 持久連線**：此頁面維持 WebSocket 長連線，離開頁面時才斷開；與一般頁面的 REST-only 模式不同

---

## [ACCEPTANCE CRITERIA]

### 功能驗收

- [ ] 列表視圖：工單表格正確顯示所有欄位，支援升序/降序排序
- [ ] 列表視圖：搜尋框即時搜尋（debounce 300ms），結果正確
- [ ] 列表視圖：13 狀態多選篩選正確運作，狀態 Badge 顏色正確對應 6 組語義色
- [ ] 列表視圖：日期範圍篩選正確（含快捷選項）
- [ ] 列表視圖：品牌篩選正確
- [ ] 列表視圖：所有篩選條件同步至 URL，刷新後保留
- [ ] 列表視圖：分頁功能正常（切換每頁筆數、頁碼導航）
- [ ] 列表視圖：行點擊導航至工單詳情頁
- [ ] 列表視圖：行操作選單（查看、指派、取消、複製編號）功能正常
- [ ] 列表視圖：批次勾選 + batch_action_bar 顯示/隱藏正確
- [ ] 列表視圖：批次指派功能正常（AI 自動匹配 + 手動統一指派）
- [ ] 列表視圖：批次取消功能正常（含確認 Modal）
- [ ] 看板視圖：5 欄正確顯示對應狀態工單
- [ ] 看板視圖：欄頭計數 Badge 正確
- [ ] 看板視圖：卡片拖拉功能正常（@dnd-kit/core）
- [ ] 看板視圖：拖拉時 shadow-kanban 效果正確
- [ ] 看板視圖：拖拉放下後 Optimistic UI 正確（立即移動 + 背景同步）
- [ ] 看板視圖：API 失敗時卡片回滾動畫 + Toast Error
- [ ] 看板視圖：關鍵狀態轉換觸發確認 Modal
- [ ] 看板視圖：「待指派→已派工」拖拉觸發指派 Modal
- [ ] 看板視圖：狀態轉換矩陣正確（禁止的轉換顯示 not-allowed）
- [ ] 看板視圖：鍵盤操作（Space 拾起/放下、Arrow Keys 移動）
- [ ] 地圖視圖：左側工單列表正確顯示並可篩選排序
- [ ] 地圖視圖：右側 Google Maps 正確載入（@vis.gl/react-google-maps）
- [ ] 地圖視圖：工單 Pin 顏色依狀態正確（紅=未指派、藍=進行中、綠=完工、橙=異常）
- [ ] 地圖視圖：技師 Pin 正確顯示位置與 tooltip
- [ ] 地圖視圖：Cluster 聚合在低縮放層級正確運作
- [ ] 地圖視圖：點擊 Pin 彈出 Popup，內容正確
- [ ] 地圖視圖：左側列表與地圖 Pin 雙向連動（hover 高亮、click 平移）
- [ ] 地圖視圖：Popup 內「指派技師」按鈕開啟 assign Modal
- [ ] 指派 Modal：Top 5 候選技師正確顯示分數明細
- [ ] 指派 Modal：#1 候選人顯示「AI 推薦」Indigo Badge
- [ ] 指派 Modal：分數條視覺化正確
- [ ] 指派 Modal：點擊「指派」後 Loading → 成功/失敗處理正確
- [ ] 指派 Modal：無候選人時顯示空狀態 + 建議操作
- [ ] 三種視圖切換平滑（保留篩選條件、URL 更新）

### 狀態驗收

- [ ] Loading 狀態：列表 Skeleton rows、看板 Skeleton cards、地圖漸進載入
- [ ] Empty 狀態：列表空狀態（插圖 + CTA）、看板空欄（虛線框）、地圖空區域
- [ ] Error 狀態：API 錯誤顯示友善訊息 + 重試按鈕
- [ ] SLA 倒數：正常（灰字）、警告（Amber bold，<= 30min）、逾時（Red bold + pulse 動畫）

### 即時更新驗收

- [ ] WebSocket 連線建立成功
- [ ] 新工單即時出現在列表/看板/地圖
- [ ] 工單狀態變更即時反映（Badge 顏色、看板欄位移動、Pin 顏色）
- [ ] 技師位置即時更新（地圖 Pin 平滑移動）
- [ ] WebSocket 斷線顯示 Warning Banner + 自動重連

### RWD 驗收

- [ ] Desktop LG (> 1440px)：完整三視圖，Kanban 5 欄無捲動
- [ ] Desktop (1024-1440px)：三視圖，Kanban 可能水平捲動
- [ ] Tablet (768-1023px)：列表 + 簡化地圖，無看板
- [ ] Mobile (< 768px)：僅列表（卡片模式），篩選器收合

### 效能驗收

- [ ] 頁面首次載入 LCP < 2.5s
- [ ] 篩選器操作後列表更新 < 500ms
- [ ] Kanban 拖拉操作 FID < 100ms
- [ ] 地圖 Pin 100+ 個不卡頓
- [ ] 地圖 Cluster 聚合/展開 < 300ms
- [ ] CLS < 0.1（Skeleton 預留高度正確）

### 無障礙驗收

- [ ] Tab 順序：toolbar → main content → pagination / batch_action_bar
- [ ] 所有可互動元素可透過鍵盤操作
- [ ] Kanban 拖拉支援鍵盤（Space + Arrow Keys）
- [ ] StatusBadge 不僅依賴顏色，同時包含文字標籤
- [ ] 色彩對比度達 WCAG 2.1 AA 標準
- [ ] Modal 開啟時 focus trap 正確；Escape 關閉
- [ ] 地圖 Pin 有 aria-label 描述


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
