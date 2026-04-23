# Page-Level Prompt: 問題卡片管理（Problem Cards）

> 管理 AI 對話產生的問題卡片，包含列表瀏覽與詳情檢視。對應 `guides/vibe_coding_build_strategy.md` → Step 5。

---

## [PAGE META]

- **page_name**: Problem Cards Management
- **route_path**: `/problem-cards`（列表）、`/problem-cards/[id]`（詳情）
- **page_type**: list + detail
- **primary_goal**: 讓管理員瀏覽、篩選、管理 AI 對話產生的問題卡片，追蹤診斷與解決進度
- **secondary_goal**: 快速識別需人工介入的高熵卡片，適時升級至 L3 派工
- **target_users**:
  - 主要：品牌管理員（每日巡查問題卡片狀態）
  - 次要：技術主管（檢視 L2/L3 升級案件）
- **entry_point**: 左側導覽列「問題卡片」選項 / Dashboard 統計卡片點擊 / 工單頁面反向連結
- **expected_time_on_page**: 列表頁 1-3 分鐘（篩選瀏覽）；詳情頁 3-8 分鐘（深入診斷審閱）

---

## [STRUCTURE: SECTIONS]

### 列表頁（`/problem-cards`）

1. **page_header**
   - section_type: header
   - section_purpose: 顯示頁面標題、總數統計摘要

2. **filter_bar**
   - section_type: filter
   - section_purpose: 提供多維度篩選條件，快速縮小搜尋範圍

3. **problem_cards_table**
   - section_type: data_table
   - section_purpose: 以表格形式呈現所有問題卡片，支援排序與分頁

### 詳情頁（`/problem-cards/[id]`）

4. **detail_header**
   - section_type: header
   - section_purpose: 顯示卡片 ID、症狀摘要標題、返回列表導覽

5. **detail_main_content**
   - section_type: content_panel
   - section_purpose: 展示問題卡片完整內容，包含 FMEA 診斷鏈與解決嘗試歷程

6. **detail_metadata_sidebar**
   - section_type: sidebar
   - section_purpose: 顯示元資料、狀態操作、關聯資源

7. **linked_conversation**
   - section_type: collapsible_panel
   - section_purpose: 展示與此問題卡片關聯的原始對話串

---

## [SECTION COMPONENT SPEC]

### Section: page_header

- **layout**: 全寬單欄，左對齊標題、右對齊統計徽章
- **elements**:
  - page_title: H1 / required / "問題卡片管理"
  - total_count_badge: Badge / required / 顯示目前篩選結果的總卡片數，例："共 {count} 張卡片"
  - status_summary: StatGroup / optional / 以小型徽章群顯示各狀態數量（open: N / diagnosing: N / resolved: N / escalated: N）
  - breadcrumb: Breadcrumb / required / 首頁 > 問題卡片
- **states**:
  - default: 顯示標題與統計
  - loading: 標題靜態顯示，統計數字以 Skeleton 佔位
- **copy_constraints**: 頁面標題固定不超過 10 字

### Section: filter_bar

- **layout**: 單行水平排列，可換行（Mobile 堆疊）
- **elements**:
  - status_filter: Select / optional / 選項：全部（預設）、待處理（open）、診斷中（diagnosing）、已解決（resolved）、已升級（escalated）
  - resolution_level_filter: Select / optional / 選項：全部（預設）、L1、L2、L3
  - brand_filter: Select / optional / 動態載入品牌列表，支援搜尋
  - date_range_filter: DateRangePicker / optional / 預設近 30 天，可自訂範圍
  - search_input: SearchInput / optional / 搜尋症狀摘要關鍵字，placeholder: "搜尋症狀描述..."
  - reset_button: Button Ghost / optional / "清除篩選"
- **states**:
  - default: 所有篩選器顯示預設值
  - active: 已套用的篩選器以 Primary（#2563EB）色標示，右側顯示已套用數量徽章
  - loading: 品牌下拉載入中顯示 Spinner
  - disabled: 無可用品牌時 brand_filter 為 disabled
- **copy_constraints**: 各篩選標籤最多 8 字

### Section: problem_cards_table

- **layout**: 全寬表格，水平捲動支援（Mobile）
- **elements**:
  - table_header: TableHead / required / 各欄位名稱可點擊排序
  - col_card_id: TableColumn / required / 格式 `pc_{uuid8}`，等寬字體顯示
  - col_symptom_summary: TableColumn / required / 症狀摘要，最多顯示 2 行，超出 truncate + tooltip
  - col_status: TableColumn / required / 狀態徽章：open=Indigo（#6366F1）、diagnosing=Blue（#2563EB）、resolved=Emerald（#10B981）、escalated=Red（#EF4444）
  - col_resolution_level: TableColumn / required / L1/L2/L3 徽章，漸層色深表示層級
  - col_completeness_score: TableColumn / required / 0-1 進度條（ProgressBar），≥0.8 為 Emerald，0.5-0.79 為 Amber，<0.5 為 Red
  - col_brand: TableColumn / required / 品牌名稱文字
  - col_model: TableColumn / required / 型號名稱文字
  - col_created_at: TableColumn / required / 相對時間格式（如「2 小時前」），hover 顯示完整時間 tooltip
  - entropy_badge: Badge / conditional / 當 entropy_flag=true 時，在 card_id 旁顯示 Amber（#F59E0B）警告徽章 "需人工確認"
  - pagination: Pagination / required / 每頁 20 筆，顯示頁碼與總頁數
  - row_click_area: ClickableRow / required / 整行可點擊，導航至 `/problem-cards/[id]`
- **states**:
  - default: 表格顯示資料，偶數行淺灰背景（#F8FAFC）
  - hover: 行背景色變為 #EFF6FF（淺藍），cursor: pointer
  - loading: 表格 Skeleton（10 行佔位）
  - error: 表格區域顯示錯誤訊息 + 重試按鈕
  - empty: 置中圖示 + "找不到符合條件的問題卡片" + 清除篩選建議連結
  - sorting: 點擊欄位表頭切換排序方向，顯示箭頭圖示
- **copy_constraints**: 症狀摘要表格內最多 60 字元

### Section: detail_header

- **layout**: 全寬單欄，含返回導覽
- **elements**:
  - back_link: Link / required / "← 返回問題卡片列表" / 導航至 `/problem-cards`
  - breadcrumb: Breadcrumb / required / 首頁 > 問題卡片 > {card_id}
  - card_id: H3 Mono / required / 顯示 `pc_{uuid8}` 卡片 ID
  - symptom_title: H1 / required / 症狀摘要作為頁面主標題
  - entropy_warning: AlertBanner / conditional / 當 entropy_flag=true 時，顯示 Amber 橫幅："⚠ 此問題卡片已觸發熵值偵測，需人工確認診斷內容"
- **states**:
  - default: 顯示卡片標題與 ID
  - loading: Skeleton 佔位（ID + 標題）
  - error: 顯示 "無法載入問題卡片" + 返回按鈕
- **copy_constraints**: 症狀摘要最多 120 字元

### Section: detail_main_content

- **layout**: 佔頁面左側 2/3 寬度，垂直堆疊四個子區塊
- **elements**:
  - symptom_summary_block: Card / required / H2 "症狀描述" + 完整症狀文字
  - domain_attributes_block: Card / required / H2 "裝置屬性" + JSONB 鍵值對渲染
    - attr_brand: KeyValue / required / 品牌
    - attr_model: KeyValue / required / 型號
    - attr_symptom_category: KeyValue / required / 症狀分類
    - attr_error_code: KeyValue / optional / 錯誤代碼（若有）
    - attr_additional: KeyValue[] / optional / 其餘 JSONB 欄位動態渲染
  - resolution_timeline_block: Card / required / H2 "解決嘗試歷程"
    - timeline: VerticalTimeline / required / L1 → L2 → L3 階段性展示
    - timeline_node: TimelineNode / required / 每個節點包含：層級標籤（L1/L2/L3）、嘗試內容摘要、信心分數（ConfidenceBadge: 0-1 數值 + 色碼，≥0.8 Emerald, 0.5-0.79 Amber, <0.5 Red）、時間戳
    - escalation_arrow: Icon / conditional / 升級時顯示向下箭頭 + 升級原因
  - fmea_visualization_block: Card / required / H2 "FMEA 診斷推理鏈"
    - fmea_chain: FlowDiagram / required / 四層視覺化：Symptom → Failure → Failure Mode → Defect
    - fmea_node_symptom: ChainNode / required / 藍色（#2563EB）節點，顯示症狀描述
    - fmea_node_failure: ChainNode / required / 靛藍色（#6366F1）節點，顯示故障描述
    - fmea_node_failure_mode: ChainNode / required / 琥珀色（#F59E0B）節點，顯示故障模式
    - fmea_node_defect: ChainNode / required / 紅色（#EF4444）節點，顯示缺陷描述
    - fmea_connector: Arrow / required / 各節點間的連接箭頭，含簡短推理標註
- **states**:
  - default: 四個子區塊依序顯示
  - loading: 各區塊獨立 Skeleton 載入
  - error: 個別區塊顯示錯誤提示 + 重試
  - empty (domain_attributes): 顯示 "尚未記錄裝置屬性"
  - empty (resolution_timeline): 顯示 "尚無解決嘗試紀錄"
  - empty (fmea): 顯示 "尚未產生 FMEA 推理鏈"
- **copy_constraints**: 症狀描述無長度上限但建議段落化；時間軸節點摘要最多 200 字

### Section: detail_metadata_sidebar

- **layout**: 佔頁面右側 1/3 寬度，垂直堆疊卡片，sticky 定位（桌面版）
- **elements**:
  - status_card: Card / required
    - status_badge: Badge / required / 使用語意色彩：open=Indigo, diagnosing=Blue, resolved=Emerald, escalated=Red
    - completeness_ring: RadialProgress / required / 環形進度圖顯示 completeness_score（0-1），環色同信心分數色碼
    - completeness_label: Caption / required / "{score}% 完成度"
  - timestamps_card: Card / required
    - created_at: KeyValue / required / "建立時間" + 完整日期時間
    - updated_at: KeyValue / required / "最後更新" + 完整日期時間 + 相對時間
  - customer_info_card: Card / required
    - customer_name: Body MD / required / 客戶名稱
    - customer_phone: Body SM / optional / 聯絡電話
    - customer_email: Body SM / optional / 電子郵件
    - conversation_channel: Badge / required / 對話來源管道（LINE / Web / ...）
  - linked_work_order_card: Card / conditional / 僅 L3 升級後顯示
    - work_order_id: Link / required / 工單 ID，可點擊導航至 `/work-orders/[id]`
    - work_order_status: Badge / required / 工單目前狀態
    - assigned_technician: Body SM / optional / 指派技師姓名
  - action_buttons: ButtonGroup / required
    - btn_mark_resolved: Button Primary / conditional / "標記已解決"（僅 open/diagnosing 狀態顯示）
    - btn_escalate_l3: Button Destructive / conditional / "升級至 L3 派工"（僅 L1/L2 階段顯示）
    - btn_link_case: Button Outline / optional / "關聯知識案例"
- **states**:
  - default: 依條件顯示所有可用元素
  - loading: 各卡片獨立 Skeleton
  - hover (action_buttons): 按鈕標準 hover 效果（色彩加深）
  - disabled (btn_mark_resolved): 已為 resolved 或 escalated 狀態時停用
  - disabled (btn_escalate_l3): 已為 escalated 狀態時停用
  - confirm_dialog (btn_escalate_l3): 點擊升級時彈出確認對話框："確定要升級至 L3 並建立派工單嗎？此操作將通知技術主管。"
  - confirm_dialog (btn_mark_resolved): 點擊標記已解決時彈出確認對話框："確定標記此問題為已解決？"
  - success: 操作成功後顯示 Toast 通知
  - error: 操作失敗顯示 Toast 錯誤訊息 + 重試
- **copy_constraints**: 按鈕文案最多 10 字；客戶名稱最多 30 字

### Section: linked_conversation

- **layout**: 全寬，位於 detail_main_content 下方，可收合面板
- **elements**:
  - toggle_header: CollapsibleHeader / required / "關聯對話紀錄（{message_count} 則訊息）" + 展開/收合 chevron
  - conversation_thread: MessageList / required / 按時間排序顯示對話訊息
    - message_item: MessageBubble / required / 包含：角色（user/assistant/system）、訊息內容、時間戳
    - user_message: 右對齊，背景 #EFF6FF
    - assistant_message: 左對齊，背景 #F8FAFC
    - system_message: 置中，灰色斜體
  - view_full_link: Link / optional / "在對話管理中檢視完整紀錄 →"
- **states**:
  - default: 預設收合，僅顯示 toggle_header
  - expanded: 展開顯示完整對話，最多顯示最近 50 則，超過可「載入更多」
  - loading: 展開時顯示 Skeleton 訊息列
  - empty: "此問題卡片尚未關聯對話紀錄"
- **copy_constraints**: 訊息內容完整顯示，不做 truncate

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. 頁面載入 → 呼叫 `GET /api/v1/problem-cards` 取得列表 → 預設以 `created_at` 降序排列
2. 使用者調整篩選條件 → 觸發 debounced API 查詢（300ms）→ 表格重新載入
3. 使用者點擊表格行 → 導航至 `/problem-cards/[id]`
4. 詳情頁載入 → 呼叫 `GET /api/v1/problem-cards/{id}` 取得完整資料
5. 使用者點擊「標記已解決」→ 彈出確認對話框 → 確認 → `PATCH /api/v1/problem-cards/{id}` 更新 status=resolved → Toast 成功 → 狀態徽章即時更新
6. 使用者點擊「升級至 L3 派工」→ 彈出確認對話框 → 確認 → `PATCH /api/v1/problem-cards/{id}` 更新 status=escalated + 建立工單 → Toast 成功 → 顯示 linked_work_order_card
7. 使用者點擊「關聯知識案例」→ 開啟搜尋 Modal → 選擇案例 → 建立關聯
8. 使用者展開關聯對話 → lazy load 對話內容

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 列表：全寬表格，所有欄位可見；詳情：左 2/3 + 右 1/3 sidebar | 完整體驗，sidebar sticky 定位 |
| Tablet (768-1279px) | 列表：表格隱藏 model 與 created_at 欄，水平捲動；詳情：主內容全寬，sidebar 收合至底部 | 詳情頁 sidebar 改為可展開抽屜 |
| Mobile (<768px) | 列表：改為卡片式列表（每張卡片一筆資料）；詳情：單欄堆疊，sidebar 元素堆疊於主內容下方 | 取消表格，FMEA 圖改為垂直流程 |

### 資料更新策略

- 列表頁：切換篩選條件時即時查詢；離開再返回時使用 TanStack Query staleTime 5 分鐘快取
- 詳情頁：載入時取得最新資料；執行 PATCH 操作後使用 `invalidateQueries` 重新取得
- 狀態變更：樂觀更新（Optimistic Update），失敗時自動回滾並顯示錯誤 Toast
- 背景更新：不使用 WebSocket，依賴使用者手動重整或 refetchOnWindowFocus

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/problem-cards` — 取得問題卡片列表（支援分頁、篩選、排序 query params: `?status=open&level=L1&brand=xx&from=2026-01-01&to=2026-04-21&page=1&per_page=20&sort=created_at&order=desc&q=keyword`）
  - GET `/api/v1/problem-cards/{id}` — 取得單一問題卡片完整詳情（含 domain_attributes、resolution_attempts、fmea_chain、linked_conversation）
  - PATCH `/api/v1/problem-cards/{id}` — 更新問題卡片（支援欄位：status、resolution_level、linked_case_id）
- **error_cases**:
  - 網路錯誤：顯示行內錯誤橫幅 + 「重試」按鈕，保留已輸入的篩選狀態
  - API 404（卡片不存在）：詳情頁顯示 "找不到此問題卡片" + 返回列表連結
  - API 409（狀態衝突）：Toast 提示 "此卡片狀態已被其他管理員更新，請重新載入"
  - API 403（權限不足）：Toast 提示 "您沒有執行此操作的權限" + 按鈕恢復原狀
  - API 422（驗證錯誤）：Toast 顯示具體欄位錯誤訊息
  - API 500：顯示通用錯誤訊息 + 錯誤 ID + 「聯絡技術支援」連結

---

## [EXCEPTION TO GLOBAL RULES]

- FMEA 四層視覺化使用自訂 FlowDiagram 元件，不受 shadcn/ui 標準卡片樣式限制，需自行定義節點色彩與連線樣式
- 詳情頁 sidebar 使用 sticky 定位（`position: sticky; top: 80px`），需確保與全域導覽列高度配合
- 對話氣泡元件（MessageBubble）使用非標準佈局（左右對齊依角色），不套用全域 Card 圓角規範

---

## [ACCEPTANCE CRITERIA]

- [ ] 列表頁所有 3 個 Section（header、filter、table）功能正常
- [ ] 詳情頁所有 4 個 Section（header、main、sidebar、conversation）功能正常
- [ ] 四種狀態徽章（open/diagnosing/resolved/escalated）正確顯示語意色彩
- [ ] completeness_score 進度條/環形圖正確渲染 0-1 數值並依閾值變色
- [ ] entropy_flag=true 時，列表頁顯示 Amber 徽章、詳情頁顯示警告橫幅
- [ ] FMEA 四層推理鏈視覺化（Symptom → Failure → Failure Mode → Defect）正確渲染
- [ ] 解決歷程時間軸（L1 → L2 → L3）含信心分數正確顯示
- [ ] 篩選條件變更後表格即時更新且保留分頁狀態
- [ ] 「標記已解決」與「升級至 L3」操作含確認對話框，成功後狀態即時更新
- [ ] L3 升級後 linked_work_order_card 顯示可點擊工單連結
- [ ] 關聯對話收合/展開正常，lazy load 載入
- [ ] Loading / Error / Empty 三態在所有 Section 均已實作
- [ ] RWD 三個斷點行為正確：Desktop 表格、Tablet 精簡表格、Mobile 卡片列表
- [ ] 樂觀更新機制正常運作，失敗時回滾並提示
- [ ] 頁面首次載入回應時間 < 2 秒
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、字體 Inter + Noto Sans TC）


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
