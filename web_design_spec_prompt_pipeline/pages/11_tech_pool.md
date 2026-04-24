# Page-Level Prompt: 技師端 — 案件池（地圖模式）

> 技師 PWA 首頁。以全螢幕地圖為核心，搭配 BottomSheet 瀏覽可接工單。Style C（類似 ServiceM8）。

---

## [PAGE META]

- **page_name**: 案件池 Case Pool
- **route_path**: `/pool`
- **page_type**: map + list (hybrid)
- **ia_pages**: T1
- **openapi_ops**: listWorkOrderPool, acceptWorkOrder
- **asyncapi_ops**: subscribeWorkOrderUpdates, subscribeTechnicianPool
- **primary_goal**: 讓技師快速瀏覽附近可接工單，並一鍵搶單
- **secondary_goal**: 透過地圖直覺理解工單地理分佈，優化路線規劃
- **target_users**:
  - 主要：已登入且在線的外派技師（每日多次使用）
  - 次要：無（此為純技師端頁面）
- **entry_point**: 底部導航第 1 個 Tab「案件池」/ Push Notification 點擊 / PWA 首頁開啟
- **expected_time_on_page**: 1–5 分鐘（瀏覽 → 接單 → 離開）

---

## [STRUCTURE: SECTIONS]

1. **map_layer**
   - section_type: map_fullscreen
   - section_purpose: 全螢幕 Google Maps 顯示技師位置與可接工單地理分佈

2. **map_popup_card**
   - section_type: overlay_card
   - section_purpose: 點擊地圖 Pin 時顯示工單摘要，引導查看詳情

3. **bottom_sheet_collapsed**
   - section_type: bottom_sheet (collapsed state)
   - section_purpose: 最小化狀態，提示可接工單數量，可上拉展開

4. **bottom_sheet_half**
   - section_type: bottom_sheet (half state)
   - section_purpose: 顯示按距離排序的工單卡片列表，支援滑動手勢操作

5. **bottom_sheet_full**
   - section_type: bottom_sheet (full state)
   - section_purpose: 完整工單詳情，含客戶聯絡、導航、接單/跳過操作

6. **offline_banner**
   - section_type: status_banner
   - section_purpose: 離線模式提示，告知技師目前使用快取資料

7. **bottom_navigation**
   - section_type: navigation
   - section_purpose: 三 Tab 底部導航列（案件池 active）

---

## [SECTION COMPONENT SPEC]

### Section: map_layer

- **layout**: 全螢幕（viewport 100vw × 100vh），地圖填滿整個畫面，z-index: 0
- **elements**:
  - google_map: `@vis.gl/react-google-maps` Map / required / 預設縮放 zoom=13，中心點為技師當前 GPS 座標
  - technician_marker: CustomMarker / required / 藍色脈衝圓點（#2563EB，外圈半透明動畫），每 30 秒更新 GPS 座標，POST 至 `/api/v1/technicians/me/location`
  - work_order_pins: CustomMarker[] / required / 紅色 Pin（#EF4444），下方顯示距離標籤（例："2.3 km"），字體 Inter 11px Bold 白底黑字圓角 Badge
  - cluster_markers: MarkerClusterer / required / 當多個 Pin 在同一視野範圍重疊時，合併顯示為圓形 cluster（數字 = 工單數量），背景 #EF4444，字體白色 Bold
  - my_location_fab: FAB / required / 右下角（距 BottomSheet 上方 16px），圓形 48×48px，圖示 MyLocation，點擊回到技師位置並 re-center 地圖
- **states**:
  - default: 地圖載入完成，顯示技師位置 + 工單 Pin
  - loading: 地圖 skeleton（淺灰背景 + 中央 Spinner）
  - gps_denied: 地圖顯示但無技師位置，頂部 Toast：「請開啟定位權限以使用完整功能」，含「前往設定」按鈕（min 44×44px）
  - no_orders: 地圖僅顯示技師位置，BottomSheet collapsed 文字改為「目前沒有可接工單」
  - offline: 顯示快取的 map tiles，右上角灰色遮罩 + 「離線模式」標籤
- **copy_constraints**: 距離標籤最多 7 字元（例："12.5 km"）

### Section: map_popup_card

- **layout**: 浮動卡片，寬度 280px，圓角 12px，陰影 shadow-lg，出現在所點擊 Pin 的正上方
- **elements**:
  - wo_number: Caption / required / 工單編號（例："WO-20260421-0032"），字體 Inter 12px，色 text.secondary (#64748B)
  - address_line: Body SM Bold / required / 地址（最多 2 行，overflow ellipsis），字體 Noto Sans TC 14px Bold
  - brand_model: Badge / required / 鎖具品牌/型號（例："Yale YDM-7116"），背景 #E2E8F0，字體 12px
  - estimated_duration: Caption / required / 預估工時（例："約 1.5 小時"），圖示 Clock
  - urgency_badge: Badge / conditional / 緊急程度：
    - `normal`：不顯示
    - `urgent`：橘色 Badge「急件」（#F59E0B 底白字）
    - `emergency`：紅色 Badge「Red Code」（#EF4444 底白字，脈衝動畫）
  - view_detail_btn: Button Ghost / required / 「查看詳情」，字體 #2563EB，min touch 44×44px，點擊展開 BottomSheet Full
  - close_btn: IconButton / required / 右上角 X，24×24px 圖示，touch area 44×44px
- **states**:
  - default: 卡片淡入動畫（200ms）
  - loading: 卡片框架 + skeleton lines
  - tap_outside: 卡片淡出關閉
- **copy_constraints**: 地址最多 40 字，超出 ellipsis

### Section: bottom_sheet_collapsed

- **layout**: 固定底部面板，高度 96px（含 safe-area-inset-bottom），寬度 100%（max-width 480px），圓角上方 16px，背景白色，陰影 shadow-2xl，z-index: 10
- **elements**:
  - pull_indicator: DragHandle / required / 頂部居中，寬 40px 高 4px 圓角灰色條，距頂 8px
  - order_count_text: H3 / required / 「{N} 件可接工單」，字體 Noto Sans TC 18px SemiBold，色 text.primary (#1E293B)，居中
  - subtitle_hint: Caption / optional / 「上拉查看列表」，字體 12px，色 text.tertiary (#94A3B8)
- **states**:
  - default: 顯示工單數量
  - zero_orders: 文字改為「目前沒有可接工單」，色 text.tertiary
  - new_order_pulse: 數字更新時短暫放大動畫（scale 1.2 → 1.0, 300ms）
- **gestures**:
  - 上拉（swipe up）→ 展開至 half 或 full（依拉動距離）
  - 點擊 pull_indicator → 展開至 half
- **copy_constraints**: 數量顯示 0–999

### Section: bottom_sheet_half

- **layout**: 底部面板，高度 50% viewport，圓角上方 16px，背景白色，z-index: 10
- **elements**:
  - pull_indicator: DragHandle / required / 同 collapsed
  - header_row: Flex Row / required / 左：「可接工單」H3 字體，右：排序按鈕（距離/時間/緊急程度）min 44×44px
  - sort_selector: DropdownMenu / required / 排序選項：最近距離（預設）、最新發布、緊急優先，每個選項 min 高度 44px
  - order_card_list: ScrollableList / required / 垂直可捲動，padding-bottom 預留 bottom_navigation 高度
  - order_card: Card / repeated / 全寬，圓角 8px，內間距 16px，margin-bottom 8px，包含：
    - address_text: Body MD Bold / required / 客戶地址（粗體，最多 2 行），Noto Sans TC 15px SemiBold
    - brand_model_badge: Badge / required / 鎖具品牌型號，背景 #F1F5F9，字體 12px
    - problem_summary: Body SM / required / 問題摘要（最多 2 行，overflow ellipsis），色 text.secondary，14px
    - distance_chip: Chip / required / 距離值 + 圖示 MapPin，例「2.3 km」
    - duration_chip: Chip / required / 預估工時 + 圖示 Clock，例「1.5h」
    - urgency_indicator: Badge / conditional /
      - `normal`：綠色左邊框 4px
      - `urgent`：橘色左邊框 4px + 「急件」橘色 Badge
      - `emergency`：紅色左邊框 4px + 「Red Code」紅色 Badge 脈衝動畫
    - commission_estimate: Caption / optional / 預估佣金（例："預估 $1,200"），色 #059669，字體 12px
- **states**:
  - default: 依距離排序的工單卡片列表
  - loading: 3 張 skeleton 卡片
  - empty: 插圖 + 「目前沒有可接工單，稍後再來看看」+ 「重新整理」按鈕 min 44×44px
  - error: 錯誤訊息 + 重試按鈕
  - refreshing: 頂部下拉 Spinner（pull-to-refresh）
- **gestures**:
  - 卡片向右滑（swipe right ≥ 80px）→ 露出綠色背景 + Checkmark 圖示 + 「接單」文字 → 釋放觸發接單確認 Dialog
  - 卡片向左滑（swipe left ≥ 80px）→ 露出灰色背景 + Skip 圖示 + 「跳過」文字 → 釋放觸發跳過（卡片淡出，30 分鐘後重新出現）
  - 卡片點擊 → BottomSheet 展開至 full，顯示該工單詳情
  - 上拉 → 展開至 full
  - 下拉 → 收合至 collapsed
  - 列表頂部下拉 → pull-to-refresh
- **copy_constraints**: 問題摘要最多 60 字，地址最多 40 字

### Section: bottom_sheet_full

- **layout**: 底部面板，高度 90% viewport，圓角上方 16px，背景白色，z-index: 10，內容可垂直捲動
- **elements**:
  - pull_indicator: DragHandle / required / 同上
  - close_btn: IconButton / required / 右上角 ChevronDown，touch area 44×44px，點擊收合至 half
  - wo_header: Flex Row / required /
    - wo_number: Caption / required / 工單編號
    - urgency_badge: Badge / conditional / 同 map_popup_card
    - created_time: Caption / required / 發單時間（relative，例「3 分鐘前」）
  - divider_1: Separator / required
  - address_section: SectionBlock / required /
    - section_label: Caption / required / 「服務地址」
    - address_text: Body LG Bold / required / 完整地址，Noto Sans TC 16px SemiBold
    - navigate_btn: Button Outline / required / 圖示 Navigation + 「導航前往」，min 48×44px，點擊開啟 Google Maps 導航（`comgooglemaps://` 或 fallback `https://maps.google.com/`）
  - device_section: SectionBlock / required /
    - section_label: Caption / required / 「鎖具資訊」
    - brand_model_card: Card / required / 品牌 Logo（如有）+ 型號名稱 + 安裝年份（如有）
    - problem_card_summary: CollapsibleCard / required /
      - header: 「問題摘要」+ 展開/收合 ChevronDown
      - body: 症狀描述 + AI 診斷推理摘要（ProblemCard 內容），最多 200 字
  - service_info_section: SectionBlock / required /
    - estimated_duration: InfoRow / required / 圖示 Clock + 「預估工時」+ 時長值
    - service_type: InfoRow / required / 圖示 Wrench + 「服務類型」+ 類型值（一般維修/安裝/客供安裝）
    - commission_rate: InfoRow / required / 圖示 DollarSign + 「佣金比例」+ 比例值（一般 70% / 安裝 60% / 客供 80%）
    - estimated_commission: InfoRow / required / 圖示 Wallet + 「預估佣金」+ 金額（加粗，色 #059669）
  - customer_section: SectionBlock / required /
    - section_label: Caption / required / 「客戶資訊」
    - customer_name: Body MD / required / 客戶姓名
    - phone_btn: Button Primary / required / 圖示 Phone + 電話號碼，full-width，min 高 48px，點擊觸發 `tel:` 撥號
    - special_notes: Body SM / optional / 特殊備註（例："大樓需要門禁卡"），背景 #FEF3C7，padding 12px，圓角 8px
  - divider_2: Separator / required
  - action_buttons: ButtonGroup / required / 固定底部（sticky），背景白色 + 上方陰影，padding 16px + safe-area-inset-bottom
    - skip_btn: Button Outline / required / 「跳過」，灰色邊框，寬度 35%，min 高 48px，touch area ≥ 44×44px
    - accept_btn: Button Primary / required / 「接受工單」，背景 #2563EB，寬度 65%，min 高 48px，字體 16px Bold
- **states**:
  - default: 完整工單資訊
  - loading: skeleton sections
  - accepting: accept_btn 顯示 Spinner + 「接單中...」，disabled
  - accepted_success: 全屏 Toast「已成功接單！」（綠色 Checkmark 動畫），1.5 秒後自動跳轉至 `/my-orders/{id}`
  - accepted_conflict: Dialog「此工單已被其他技師接走」+ 「返回列表」按鈕
  - accept_failed: Toast error「接單失敗，請重試」
  - offline_queued: accept_btn 改為「離線接單（上線後同步）」，背景 #6B7280
- **copy_constraints**: 問題摘要最多 200 字，特殊備註最多 100 字

### Section: offline_banner

- **layout**: 固定頂部（sticky top），全寬，高度 40px，z-index: 20，位於 status bar 下方
- **elements**:
  - offline_icon: Icon / required / WifiOff，16px
  - offline_text: Body SM / required / 「離線模式 — 顯示快取資料」，Noto Sans TC 13px
  - retry_btn: TextButton / optional / 「重試連線」，min touch 44×44px
- **states**:
  - hidden: 網路正常時不顯示
  - visible: 無網路時滑入（slideDown 200ms），背景 #FEF3C7，文字 #92400E
  - reconnecting: 文字改為「正在重新連線...」+ Spinner
  - reconnected: 背景轉綠 #D1FAE5 + 「已恢復連線」，2 秒後淡出

### Section: bottom_navigation

- **layout**: 固定底部，高度 56px + safe-area-inset-bottom，全寬（max-width 480px），背景白色，上方 1px border #E2E8F0，z-index: 30
- **elements**:
  - tab_pool: NavTab / required / 圖示 Map + 「案件池」，active 狀態色 #2563EB，touch area 全寬/3 × 56px（≥ 44×44px）
  - tab_my_orders: NavTab / required / 圖示 ClipboardList + 「我的工單」，inactive 色 #94A3B8，touch area 同上
  - tab_account: NavTab / required / 圖示 Wallet + 「帳戶」，inactive 色 #94A3B8，touch area 同上
  - notification_dot: Dot / conditional / 紅色圓點 8px，出現在「我的工單」tab 上方，有新狀態更新時顯示
- **states**:
  - default: tab_pool 為 active（#2563EB 文字 + 圖示），其餘 inactive（#94A3B8）
  - badge: notification_dot 在有未讀通知的 tab 上顯示

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入**：
   - 請求 GPS 權限 → 取得技師座標 → POST `/api/v1/technicians/me/location` 更新位置
   - 同步呼叫 GET `/api/v1/work-orders/pool` 取得可接工單列表
   - 渲染地圖 + 標記 Pin + BottomSheet collapsed
   - 建立 WebSocket 連線，監聽新工單推送

2. **瀏覽工單**：
   - 上拉 BottomSheet → half → 瀏覽卡片列表
   - 點擊地圖 Pin → 顯示 Popup Card → 點「查看詳情」→ BottomSheet full
   - 點擊列表卡片 → BottomSheet full

3. **接單流程**：
   - 方式 A：卡片右滑 → 確認 Dialog「確定接受此工單？」→ 確認 → PATCH `/api/v1/work-orders/{id}/status` body: `{status: "accepted"}` → 成功 → 跳轉 `/my-orders/{id}`
   - 方式 B：BottomSheet full → 點「接受工單」→ 同上
   - 衝突處理：若 409 Conflict → 顯示「已被其他技師接走」Dialog

4. **跳過工單**：
   - 卡片左滑 → 卡片淡出移除 → POST `/api/v1/work-orders/{id}/skip` → 該工單 30 分鐘內不再出現

5. **新工單推送**：
   - WebSocket 收到 `new_order` 事件 → 地圖新增 Pin（彈入動畫）+ BottomSheet count 更新（脈衝動畫）+ 頂部 Toast「新工單！{地址簡稱}」
   - 如 App 在背景 → Push Notification → 點擊通知 → 開啟 App 至 `/pool` 並自動聚焦該工單 BottomSheet full

6. **GPS 持續更新**：
   - 每 30 秒 `navigator.geolocation.getCurrentPosition()` → POST 更新位置 → 更新地圖藍點 + 重算各工單距離

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Mobile (<480px) | 全螢幕地圖 + BottomSheet（主要設計） | 標準體驗，所有手勢操作 |
| Tablet (481–768px) | 同 Mobile，BottomSheet max-width 480px 居中 | 地圖面積更大，BottomSheet 不延伸 |
| Desktop (769px+) | 不支援（技師端為純 Mobile PWA） | 顯示「請使用手機操作」提示頁 |

### 資料更新策略

- **工單列表**：WebSocket 即時推送新增/移除，每 60 秒 polling fallback
- **技師位置**：每 30 秒 GPS 更新 + POST 上報
- **距離計算**：前端根據技師座標即時計算 Haversine 距離，排序隨位置更新
- **快取策略**：Service Worker 快取最近 map tiles（zoom 10–16）+ 最新一次工單列表 JSON

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/work-orders/pool` — 取得所有可接工單（含座標、品牌型號、緊急程度、預估工時）。查詢參數：`lat`, `lng`, `radius_km`（預設 30）, `sort_by`（distance|created_at|urgency）
  - POST `/api/v1/technicians/me/location` — 上報技師 GPS 座標。Body: `{ lat, lng, accuracy, timestamp }`
  - PATCH `/api/v1/work-orders/{id}/status` — 接單。Body: `{ status: "accepted" }`
  - POST `/api/v1/work-orders/{id}/skip` — 跳過工單。Body: `{ reason?: string }`
  - WebSocket `wss://.../ws/technician/{tech_id}/pool` — 即時推送：`new_order`, `order_taken`, `order_cancelled`
- **error_cases**:
  - 網路錯誤：顯示 offline_banner，使用 IndexedDB 快取的工單列表，接單操作加入離線佇列（Background Sync API）
  - API 錯誤（5xx）：Toast「伺服器忙碌中，請稍後再試」+ 自動重試（exponential backoff，最多 3 次）
  - 權限不足（401/403）：導向登入頁 `/login`
  - 接單衝突（409）：Dialog「此工單已被其他技師接走」，自動從列表移除該工單
  - GPS 失敗：Toast 提示 + 使用上次已知位置，距離改顯示「距離未知」

---

## [EXCEPTION TO GLOBAL RULES]

- **全螢幕地圖佈局**：此頁面不使用標準 page container padding（16px），地圖邊到邊全寬全高渲染
- **無 Top AppBar**：此頁面不顯示頂部導航列，空間完全讓給地圖
- **BottomSheet 覆蓋 BottomNav**：BottomSheet 在 half/full 狀態時 z-index 高於 BottomNav（z-10 vs z-30），但 BottomNav 始終可見於 BottomSheet 下方（BottomSheet 預留 bottom padding = 56px + safe-area）
- **Service Worker 地圖快取**：使用 Workbox 的 `CacheFirst` 策略快取 Google Maps tiles，此為技師端特有

---

## [ACCEPTANCE CRITERIA]

- [ ] Google Maps 正確載入並顯示技師藍色脈衝圓點
- [ ] 可接工單以紅色 Pin 顯示於地圖，含距離標籤
- [ ] 多個 Pin 重疊時自動 cluster，顯示數量
- [ ] 點擊 Pin 顯示 Popup Card，含工單摘要 + 「查看詳情」按鈕
- [ ] BottomSheet 三態（collapsed 96px / half 50% / full 90%）手勢切換流暢
- [ ] 卡片右滑露出綠色「接單」，釋放觸發接單確認
- [ ] 卡片左滑露出灰色「跳過」，釋放移除卡片
- [ ] 點擊卡片展開 BottomSheet Full，顯示完整工單詳情
- [ ] 「接受工單」成功後跳轉至 `/my-orders/{id}`
- [ ] 409 衝突正確顯示「已被其他技師接走」
- [ ] WebSocket 即時推送新工單，地圖新增 Pin + 列表更新
- [ ] GPS 每 30 秒更新，藍點移動 + 距離重算
- [ ] 離線模式：顯示快取資料 + 「離線模式」Banner + 接單操作離線佇列
- [ ] 所有可點擊元素 touch target ≥ 44×44px
- [ ] 操作按鈕（接單/跳過）高度 ≥ 48px
- [ ] BottomNav 正確顯示 3 Tab，案件池 active 高亮
- [ ] PWA：可加到主畫面 + Service Worker 快取 map tiles
- [ ] Loading / Error / Empty 三態完備
- [ ] 緊急工單（emergency）顯示 Red Code 脈衝 Badge
- [ ] 電話按鈕可觸發系統撥號，導航按鈕開啟 Google Maps


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
