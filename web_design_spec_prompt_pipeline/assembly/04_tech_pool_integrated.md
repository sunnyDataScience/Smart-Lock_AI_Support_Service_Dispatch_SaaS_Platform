# Assembly Prompt: Technician Case Pool 技師接單池

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

本次任務：根據上方 Global Guideline，設計並實作「Technician Case Pool 技師接單池」。這是技師端 PWA 的核心頁面，**Mobile-First 設計**。

### [PAGE META]

- **page_name**: Technician Case Pool 技師接單池
- **route_path**: `/pool`
- **page_type**: map（全螢幕地圖 + BottomSheet）
- **primary_goal**: 讓外勤技師在手機上即時查看附近可接工單，透過滑動手勢快速接單或跳過
- **secondary_goal**: 提供離線支援，確保網路不穩定環境下仍可接單與回報
- **target_users**:
  - 主要：外勤技師（全天使用，在外移動中操作）
  - 使用情境：單手操作、戶外陽光下、可能網路不穩定
- **entry_point**: 技師 App 底部 Tab Bar「接單池」/ 推播通知點擊
- **expected_time_on_page**: 持續開啟（背景地圖 + 定期查看新工單）
- **device_constraint**: 僅限 Mobile（<480px）。Tablet/Desktop 訪問此路由 → 自動重導向至 Admin 管理面板 `/dashboard`

---

### [STRUCTURE: SECTIONS]

共 5 個主要 Section：

1. **fullscreen_map** — 全螢幕地圖背景
   - section_type: map
   - section_purpose: 以 Google Maps 全螢幕顯示技師位置與附近可接工單

2. **bottom_sheet** — 底部滑動面板（三段式）
   - section_type: bottom_sheet
   - section_purpose: 覆蓋在地圖上方，以滑動手勢展開/收合，顯示工單列表與詳情

3. **top_status_bar** — 頂部狀態列
   - section_type: status_bar
   - section_purpose: 顯示技師上線狀態、連線狀態、離線模式提示

4. **offline_banner** — 離線模式橫幅
   - section_type: banner
   - section_purpose: 網路斷線時顯示離線提示與同步狀態

5. **new_order_toast** — 新工單推播提示
   - section_type: toast
   - section_purpose: WebSocket 推送新工單時，頂部彈出提示

---

### [SECTION COMPONENT SPEC]

#### Section 1: fullscreen_map

- **layout**: 全螢幕 100vw x 100vh，z-index 0，使用 @vis.gl/react-google-maps
- **elements**:
  - tech_location_dot: 自訂 Marker / required
    - 藍色脈衝圓點（Blue pulse dot）
    - 外圈：24px 半透明藍色圓（#2563EB/20）+ pulse 動畫（1.5s infinite）
    - 內圈：12px 實心藍色圓（#2563EB）
    - 代表技師本人目前 GPS 位置
    - 地圖 camera 初始置中於此點
  - order_pins: 自訂 Marker[] / required
    - 紅色圓形標記（#EF4444），大小 32x32
    - 每個 pin 下方顯示距離標籤（Caption 字級，背景半透明黑，圓角 SM）
    - 格式："1.2 km" 或 "800 m"
    - 點擊 → BottomSheet 展開至 full 顯示該工單詳情
  - cluster_markers: MarkerClusterer / required
    - 同區域多筆工單聚合為 cluster
    - 顯示數量數字
    - 點擊 → 地圖 zoom in 展開個別 pins
  - map_controls:
    - 右下角：定位按鈕（重新置中至技師位置），圓形白色按鈕 48x48，shadow-md
    - 右下角：zoom in/out（地圖原生控制）
    - 地圖樣式：淺色自訂主題（降低干擾），隱藏 POI 標籤
- **states**:
  - default: 地圖載入完成，顯示技師藍點 + 附近工單紅 pin
  - loading: 灰色佔位 + 中央 spinner "載入地圖中..."
  - error: "地圖載入失敗" + 重試按鈕（全螢幕居中）
  - gps_denied: "請開啟定位權限以使用接單池" + 前往設定按鈕
  - no_orders: 僅顯示技師藍點，無紅 pin

#### Section 2: bottom_sheet

三段式 BottomSheet，覆蓋在地圖上方，支援觸控拖曳手勢：

**三段位置：**
- **collapsed（收合）**: 高度 96px，底部安全區域上方
- **half（半展開）**: 高度 50vh
- **full（全展開）**: 高度 90vh（保留頂部狀態列可見）

**手勢行為：**
- 向上滑動：collapsed → half → full
- 向下滑動：full → half → collapsed
- 快速向下滑：直接回到 collapsed
- 使用 `framer-motion` 或 CSS `touch-action` + JS 實現，彈性回彈效果

##### BottomSheet: collapsed 態

- **layout**: 96px 高度橫條，圓角 XL (12px) 頂部，shadow-lg，bg-white
- **elements**:
  - drag_handle: 居中灰色橫條 / required — 40x4px 圓角，bg #CBD5E1，上方 padding 8px
  - order_count: H3 (20px/600) / required — "{N} 件可接工單"
  - nearest_hint: Caption / optional — "最近 {距離} | {地址簡稱}"
- **states**:
  - default: 顯示可接工單數量
  - empty: "目前附近沒有可接工單"，文字色 Text Secondary #64748B
  - new_order: 數量 badge 短暫亮起 Accent #F59E0B + 震動回饋

##### BottomSheet: half 態

- **layout**: 50vh 高度，上方圓角 XL，shadow-lg，bg-white，內容可垂直滾動
- **elements**:
  - drag_handle: 同 collapsed
  - section_title: H3 "附近工單" + 排序切換（距離 / 時間 / 優先度）
  - order_card_list: 垂直捲動卡片列表 / required
    - 按距離由近到遠排序（預設）
    - 每張卡片：
      - order_card: 白色卡片，圓角 LG (8px)，shadow-sm，padding 16px，margin-bottom 8px
      - 內容：
        - 第一行：工單編號 (Caption Mono) + 優先度 Badge（右對齊）
        - 第二行：客戶名稱 (Body Bold) + 鎖型型號 (Caption)
        - 第三行：地址 (Caption, Text Secondary, 單行 ellipsis)
        - 第四行：距離標籤 (Badge outline) + SLA 倒數 (Badge, 色彩同 Kanban)
        - 第五行：問題摘要 (Caption, 最多 2 行)
  - **swipe_gesture**（核心互動）:
    - 向右滑動 → 顯示綠色背景 + Check 圖標 → 鬆手觸發「接受工單」
    - 向左滑動 → 顯示灰色背景 + X 圖標 → 鬆手觸發「跳過工單」
    - 滑動閾值：水平位移 >80px 才觸發
    - 滑動回饋：卡片跟隨手指平移 + 背景色漸變
    - 接受成功：卡片向右飛出 + Toast "已接受工單 WO-XXXX" + 列表刷新
    - 跳過成功：卡片向左飛出 + 列表刷新（靜默，無 Toast）
- **states**:
  - default: 卡片列表可滾動
  - loading: 3 張 Skeleton 卡片
  - error: "無法載入工單列表" + 重試按鈕
  - empty: 插圖 + "附近暫無可接工單" + "系統會在有新工單時通知你"
  - swiping: 卡片平移 + 背景色顯示

##### BottomSheet: full 態

- **layout**: 90vh 高度，顯示單筆工單完整詳情，適用於從 half 態點擊卡片或從地圖 pin 點擊
- **elements**:
  - drag_handle: 同上
  - back_button: IconButton 左箭頭 / required — 返回 half 態列表
  - order_detail: 完整工單資訊 / required
    - 工單編號 + 狀態 Badge
    - 客戶資訊：姓名、電話（可點擊撥號 `tel:`）、完整地址（可點擊開啟 Google Maps 導航 `geo:`）
    - 鎖型品牌與型號
    - 問題描述（完整文字）
    - AI 診斷建議（如有）：問題分類 + 建議處理方式 + 所需工具
    - SLA 資訊：截止時間 + 倒數計時器
    - 預估路程時間 + 距離
  - action_buttons: 固定底部操作列 / required
    - 主按鈕 "接受工單": 高度 48px，最小觸控區域 44x44px，bg Accent #F59E0B，hover #D97706，文字白色 Bold，全寬，圓角 LG
    - 次按鈕 "跳過": 高度 48px，bg #F1F5F9，文字 Text Secondary，全寬，圓角 LG
    - 兩按鈕垂直堆疊，間距 8px，底部 padding 含安全區域 `pb-safe`
  - call_customer_btn: IconButton / optional — 電話圖標，點擊撥號
  - navigate_btn: IconButton / optional — 導航圖標，點擊開啟 Google Maps
- **states**:
  - default: 完整資訊 + 操作按鈕
  - loading: Skeleton 全頁
  - accepting: "接受工單" 按鈕 disabled + spinner + "接單中..."
  - accepted: 成功動畫（綠色 CheckCircle 放大 + "接單成功！"）→ 1.5s 後自動跳轉至工單詳情頁
  - error: 底部 inline 錯誤 "接單失敗：{原因}" + 重試按鈕

#### Section 3: top_status_bar

- **layout**: 頁面頂部，全寬，高度 44px，半透明白色背景 bg-white/80 backdrop-blur，z-index 高於地圖
- **elements**:
  - tech_status_toggle: shadcn/ui `<Switch>` / required
    - 上線 / 離線切換
    - 上線：綠色 + "上線中"
    - 離線：灰色 + "已離線"（離線時不接收新工單推送）
  - connection_dot: StatusDot / required — 綠(WebSocket) / 琥珀(polling) / 紅(離線)
  - current_time: Caption / optional — "HH:MM"
- **states**:
  - online: Switch 綠色，接收工單推送
  - offline_by_choice: Switch 灰色，不接收推送，BottomSheet 顯示 "你目前為離線狀態，不會收到新工單"
  - disconnected: 紅色 dot + "連線中斷" 文字

#### Section 4: offline_banner

- **layout**: top_status_bar 下方，全寬橫幅，bg Warning #F59E0B/10，border-bottom 1px #F59E0B
- **elements**:
  - offline_icon: WifiOff 圖標 / required
  - offline_text: Body SM Bold / required — "離線模式"
  - sync_status: Caption / required — "有 {N} 筆待同步操作" 或 "所有資料已同步"
  - retry_btn: 小型 Button / optional — "重新連線"
- **visibility**: 僅在偵測到網路離線時顯示（`navigator.onLine === false` 或 WebSocket 斷線 >10s）
- **states**:
  - offline: 顯示橫幅 + 離線操作佇列數
  - syncing: "同步中..." + spinner
  - back_online: "已恢復連線" 綠色橫幅 → 2s 後自動消失

#### Section 5: new_order_toast

- **layout**: 頂部彈出 Toast，全寬 padding 16px，bg-white，shadow-lg，圓角 LG
- **elements**:
  - toast_icon: Bell 圖標 + Accent 色
  - toast_title: Body Bold "新工單！"
  - toast_body: Caption — "距離你 {N} km — {客戶名稱} — {鎖型型號}"
  - toast_action: "查看" 按鈕 → BottomSheet 展開至 full 顯示該工單
- **behavior**:
  - 自動顯示 5 秒後消失（向上滑出）
  - 點擊 "查看" 立即展開詳情
  - 點擊 Toast 外區域關閉
  - 搭配裝置震動回饋（`navigator.vibrate(200)`）
  - 同時觸發聲音提示（短促叮咚音效，可在設定中關閉）

---

### [OFFLINE SUPPORT]

此頁面必須支援離線操作，使用 Service Worker + IndexedDB：

- **快取策略**:
  - 地圖 tiles：Cache First（Service Worker 攔截，離線時使用已快取的地圖區塊）
  - 工單列表：Network First → Fallback to IndexedDB cache
  - 靜態資源（JS/CSS/圖片）：Cache First
- **離線可執行操作**:
  - 瀏覽已快取的工單列表
  - 接受工單（操作寫入 IndexedDB 佇列，上線後自動同步）
  - 查看工單詳情（已快取的）
  - 回報技師位置（GPS 持續記錄，上線後批次上傳）
- **同步機制**:
  - 偵測到 `online` 事件 → 自動同步佇列中的操作
  - 同步衝突處理：若工單已被其他技師接走 → Toast "此工單已被其他技師接受" + 從列表移除
  - 同步佇列顯示於 offline_banner 的待同步數量
- **離線模式 UI**:
  - 頂部顯示 offline_banner（Section 4）
  - 地圖停止更新位置 pin（使用最後已知位置）
  - 工單列表仍可瀏覽但資料可能非最新
  - "接受工單" 按鈕文字改為 "離線接單（上線後同步）"

---

### [INTERACTION & STATE FLOW]

1. 頁面載入 → 請求 GPS 權限 → 取得技師位置 → 初始化地圖 camera → `GET /api/v1/pool?lat={}&lng={}&radius=10km`
2. 地圖渲染完成 → 顯示藍色脈衝圓點（技師）+ 紅色 pin（附近工單）+ 距離標籤
3. BottomSheet 初始為 collapsed → 顯示 "N 件可接工單"
4. 向上滑 BottomSheet → half 態 → 卡片列表按距離排序
5. 在 half 態向右滑卡片 → 綠色背景 → 鬆手 → `POST /api/v1/pool/{id}/accept` → 接單成功 Toast
6. 在 half 態向左滑卡片 → 灰色背景 → 鬆手 → 卡片飛出（前端跳過，不呼叫 API）
7. 在 half 態點擊卡片 → BottomSheet 展開至 full → 顯示完整詳情
8. 在 full 態點擊 "接受工單" → submitting → `POST /api/v1/pool/{id}/accept` → 成功動畫 → 跳轉
9. 點擊地圖紅 pin → BottomSheet 展開至 full + 對應工單詳情
10. 背景持續上報技師位置 → `POST /api/v1/technicians/location` 每 30 秒
11. WebSocket 推送新工單 → new_order_toast 彈出 + BottomSheet collapsed 數量更新 + 地圖新增 pin
12. 網路離線 → offline_banner 顯示 → 離線操作寫入 IndexedDB → 恢復後自動同步

---

### [DATA & API]

- **uses_api**: true
- **endpoints**:
  - `GET /api/v1/pool` — 取得技師附近可接工單（query params: lat, lng, radius, sort_by）
  - `GET /api/v1/pool/{id}` — 單筆工單完整詳情
  - `POST /api/v1/pool/{id}/accept` — 接受工單
  - `POST /api/v1/technicians/location` — 上報技師 GPS 位置（body: { lat, lng, accuracy, timestamp }）
  - `WS /ws/pool` — WebSocket 頻道，推送新工單通知、工單被搶走通知、指派變更
- **request_headers**:
  - `Authorization: Bearer {access_token}`
  - `X-Technician-ID: {technician_id}`
- **快取策略**:
  - 工單列表: TanStack Query staleTime 30s + WebSocket invalidation
  - 工單詳情: staleTime 1min
  - 離線快取: IndexedDB via idb-keyval 或 Dexie.js
- **error_cases**:
  - GPS 權限拒絕 → 全螢幕提示 "請開啟定位權限" + 設定連結
  - 接單失敗（已被搶走）→ Toast "此工單已被其他技師接受" + 列表移除該卡片
  - 接單失敗（其他）→ inline error + 重試按鈕
  - 網路離線 → 進入離線模式（Section 4）
  - WebSocket 斷線 → polling fallback 30s + 琥珀色狀態點

---

### [RWD 行為]

| 斷點 | 行為 |
|------|------|
| Mobile (<480px) | **唯一支援斷點** — 全螢幕地圖 + BottomSheet，觸控優化 |
| Tablet (768-1024px) | 自動重導向至 `/dashboard`（管理面板） |
| Desktop (>1024px) | 自動重導向至 `/dashboard`（管理面板） |

**Mobile 觸控優化規範：**
- 所有可點擊元素最小觸控區域：44x44px
- 按鈕高度：48px
- 卡片 padding：16px
- 文字最小字級：Body 14px（Caption 11px 僅用於次要資訊）
- 底部操作按鈕含安全區域：`padding-bottom: env(safe-area-inset-bottom)`
- 滑動手勢靈敏度：閾值 80px，加速度感應

---

### [ACCEPTANCE CRITERIA]

- [ ] 全螢幕 Google Maps 正確載入，技師藍色脈衝圓點顯示
- [ ] 紅色 pin 正確顯示附近可接工單 + 距離標籤
- [ ] Cluster marker 聚合與展開功能正常
- [ ] BottomSheet 三段式（96px / 50vh / 90vh）手勢滑動流暢
- [ ] BottomSheet collapsed 顯示工單數量
- [ ] BottomSheet half 卡片列表按距離排序，滾動流暢
- [ ] 向右滑接單（綠色背景 + API 呼叫 + Toast）
- [ ] 向左滑跳過（灰色背景 + 卡片飛出）
- [ ] BottomSheet full 工單完整詳情 + 大型按鈕
- [ ] "接受工單" 按鈕 48px 高度，44x44 最小觸控區域
- [ ] "跳過" 按鈕功能正常
- [ ] 電話撥號 `tel:` + Google Maps 導航 `geo:` 連結正常
- [ ] 離線模式：Service Worker 快取 + IndexedDB 佇列 + 離線橫幅
- [ ] 離線接單：操作寫入佇列，上線後自動同步
- [ ] 同步衝突處理：工單已被搶走時正確提示
- [ ] WebSocket 新工單推送 → Toast + 震動 + 列表更新
- [ ] 技師位置每 30 秒上報
- [ ] 技師上線/離線切換功能正常
- [ ] GPS 權限拒絕時正確提示
- [ ] Tablet/Desktop 訪問自動重導向
- [ ] Loading / Error / Empty 三態完整
- [ ] 所有觸控區域 ≥ 44x44px
- [ ] 底部安全區域（notch 裝置）正確處理

---

## === EXCEPTION RULES ===

1. **全螢幕地圖覆寫**：此頁面使用 100vw x 100vh 全螢幕地圖，完全覆寫標準 Grid 系統的 padding/margin/max-width。無 Sidebar、無頁面容器邊距、無 12-col grid。
2. **BottomSheet 覆蓋標準佈局**：BottomSheet 以 absolute/fixed 定位覆蓋在地圖上方，不遵循標準頁面內容流。z-index 層級：地圖 0 → BottomSheet 10 → top_status_bar 20 → offline_banner 30 → Toast 40。
3. **僅限 Mobile**：此頁面不提供 Tablet/Desktop 響應式佈局。非 Mobile 裝置直接重導向。這是刻意設計，非遺漏。
4. **Tech PWA Grid 覆寫**：使用 Tech PWA 專用 Grid（480px/1col/16px pad）而非 Admin Grid（1440px/12col/24px gap）。
5. **觸控優先**：此頁面所有互動以觸控手勢為主（滑動、拖曳、點擊），不需要鍵盤導航支援（Mobile 裝置無外接鍵盤場景）。但仍需支援螢幕閱讀器（VoiceOver/TalkBack）。

---

## === OUTPUT REQUIREMENTS ===

### Step 1: 結構確認
列出本頁面的 5 個 sections、關鍵元件、資料流策略：
- fullscreen_map → Google Maps 全螢幕（@vis.gl/react-google-maps，GPS 即時追蹤）
- bottom_sheet → 三段式滑動面板（collapsed 96px / half 50vh / full 90vh，framer-motion 手勢）
- top_status_bar → 上線切換 + 連線狀態（Zustand store）
- offline_banner → 離線模式提示（Service Worker + IndexedDB 佇列）
- new_order_toast → 新工單推播（WebSocket + 震動 API）

### Step 2: 設計決策說明
提供 2-3 個關鍵設計決策與理由：
1. 三段式 BottomSheet 而非獨立頁面切換：保持地圖始終可見，技師可同時參考地理位置與工單資訊
2. 滑動接單手勢（類 Tinder）：單手操作最佳化，降低認知負擔，比點擊按鈕更快
3. 離線優先架構：外勤場景網路不穩定為常態，必須保障核心功能（瀏覽 + 接單）離線可用

### Step 3: 實作方案
Option A: 完整 React/Next.js 程式碼（使用 shadcn/ui + Tailwind）

請產出以下檔案結構：
```
app/(technician)/pool/
├── page.tsx                        # 頁面主元件 + 裝置重導向檢查
├── components/
│   ├── FullscreenMap.tsx            # Google Maps 全螢幕
│   ├── TechLocationDot.tsx          # 藍色脈衝圓點 Marker
│   ├── OrderPin.tsx                 # 紅色工單 Pin + 距離標籤
│   ├── BottomSheet/
│   │   ├── BottomSheet.tsx          # 三段式容器（framer-motion）
│   │   ├── CollapsedView.tsx        # collapsed 態：工單數量
│   │   ├── HalfView.tsx             # half 態：卡片列表
│   │   ├── FullView.tsx             # full 態：完整詳情
│   │   └── SwipeableCard.tsx        # 可滑動工單卡片
│   ├── TopStatusBar.tsx             # 頂部狀態列
│   ├── OfflineBanner.tsx            # 離線橫幅
│   └── NewOrderToast.tsx            # 新工單推播 Toast
├── hooks/
│   ├── usePoolOrders.ts             # 工單列表 TanStack Query
│   ├── useGeolocation.ts            # GPS 位置追蹤 + 上報
│   ├── useBottomSheet.ts            # BottomSheet 手勢狀態
│   ├── usePoolWebSocket.ts          # WebSocket 訂閱
│   └── useOfflineSync.ts            # 離線佇列 + 同步
├── stores/
│   └── techStatusStore.ts           # Zustand：技師上線狀態
├── sw/
│   └── pool-service-worker.ts       # Service Worker 離線快取
└── types.ts                         # TypeScript 型別
```

### 品質檢查
- [ ] 色彩系統一致性（Primary #2563EB 藍點 / Danger #EF4444 紅 pin / Accent #F59E0B 接單按鈕）
- [ ] 字體層級正確（H3 工單數量、Body 卡片內容、Caption 距離標籤）
- [ ] 元件風格統一（shadcn/ui Switch, Badge, Button, Toast）
- [ ] Mobile-Only 設計完整（全螢幕地圖 + BottomSheet，無 Desktop 佈局）
- [ ] 所有狀態已處理（Loading / Error / Empty / Offline / GPS Denied / Swiping / Accepting）
- [ ] 無障礙支援（VoiceOver/TalkBack 螢幕閱讀器相容，觸控區域 ≥44x44px）
- [ ] 效能指標達標（地圖 FCP < 2s / BottomSheet 手勢 60fps / Service Worker 離線可用）
- [ ] 離線支援完整（Service Worker + IndexedDB + 同步佇列 + 衝突處理）

---

執行優先順序：Global 規範 > Page 特定需求 > Exception
Assembly 日期：2026-04-21
Brand System 版本：v1.0
