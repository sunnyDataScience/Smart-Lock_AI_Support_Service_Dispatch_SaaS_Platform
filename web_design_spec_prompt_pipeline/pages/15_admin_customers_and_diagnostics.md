# Page-Level Prompt: 客戶主檔 × AI 診斷治理（4 個子頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 本頁組涵蓋 CRM 客戶主檔、客戶詳情 5 tabs、AI 三層診斷推理檢視、SOP 績效儀表板四個子頁面，為平台「以客戶為中心」與「AI 治理可審計」的核心支柱。

---

## [PAGE META]

- **page_name**: 客戶主檔與 AI 診斷治理 Customers & Diagnostics
- **route_path**: `/admin/customers` | `/admin/customers/[id]` | `/admin/diagnostics/[conversation_id]` | `/admin/knowledge-base/sop-performance`
- **page_type**: multi_page_bundle（各子頁面獨立佈局，共享同一 Admin Shell）
- **primary_goal**:
  - 維護客戶與名下設備主檔，支援去重、合併、風險等級自動評估與保固提醒
  - 讓管理員可審視、覆寫 AI 三層診斷（L1 向量 / L2 RAG / L3 升級）推理鏈，提交訓練反饋
  - 以資料驅動評估 SOP 知識資產使用率與成效，觸發審核流程
- **secondary_goal**:
  - 建立「客戶 → 工單 → 診斷 → SOP」的閉環追溯，支撐爭議舉證與模型改善
  - 多租戶 RLS 強制隔離，確保跨租戶資料安全
- **target_users**:
  - 主要：客服主管（客戶主檔）、平台管理員（診斷覆寫）、知識運營（SOP 績效）
  - 次要：Reviewer（診斷審核權限）、財務（客戶財務紀錄）、超管（跨租戶 SOP 比較，V3.0）
- **entry_point**:
  - `/admin/customers` — 左側主導覽「客戶管理」/ 工單詳情頁「客戶」連結
  - `/admin/customers/[id]` — 客戶列表點擊行 / 工單詳情客戶資訊展開
  - `/admin/diagnostics/[conversation_id]` — 對話詳情「AI 推理追溯」按鈕 / 工單詳情「診斷追溯 PDF」預覽 / Problem Card 連結
  - `/admin/knowledge-base/sop-performance` — 左側導覽「知識庫 → SOP 績效」/ KPI Dashboard 下鑽
- **expected_time_on_page**: 客戶列表 2–5 分鐘、客戶詳情 5–15 分鐘、診斷檢視 10–30 分鐘（深度審核）、SOP 績效 5–10 分鐘

---

## [STRUCTURE: SECTIONS]

### 子頁面 A23 — 客戶主檔 `/admin/customers`

1. **customers_page_header**
   - section_type: page_header
   - section_purpose: 頁面標題 + 搜尋列 + 新增客戶 CTA + 租戶 scope 提示
2. **customers_summary_stats**
   - section_type: stat_cards
   - section_purpose: 總客戶數、活躍客戶、高風險客戶、保固即將到期數摘要
3. **customers_filter_bar**
   - section_type: filter_bar
   - section_purpose: 風險等級、設備品牌、保固狀態、偏好技師等多維篩選
4. **customers_data_table**
   - section_type: data_table
   - section_purpose: 客戶主檔列表，支援排序、分頁、列點擊跳轉詳情

### 子頁面 A24 — 客戶詳情 `/admin/customers/[id]`

5. **customer_detail_header**
   - section_type: entity_header
   - section_purpose: 客戶核心資訊 bar（頭像、名稱、風險 Badge、快捷動作：合併、封鎖、建立工單）
6. **customer_detail_tabs**
   - section_type: tab_container
   - section_purpose: 5 個 tabs（基本資料 / 名下設備 / 服務歷史 / 財務紀錄 / 備註風險）容器
7. **customer_merge_modal**
   - section_type: modal_workflow
   - section_purpose: 客戶合併工作流（選擇來源、預覽衝突、確認遷移）

### 子頁面 A32 — AI 診斷推理檢視 `/admin/diagnostics/[conversation_id]`

8. **diagnostic_header**
   - section_type: entity_header
   - section_purpose: 對話摘要 + 最終決策 Badge + SSE 連線狀態 + 匯出 PDF
9. **l1_vector_search_panel**
   - section_type: ranked_table
   - section_purpose: L1 向量搜尋 Top-5 候選案例與相似度、命中欄位
10. **l2_rag_generation_panel**
    - section_type: prompt_response_viewer
    - section_purpose: L2 RAG prompt/response/confidence/tokens 與 SSE 逐 token 重播
11. **l3_escalation_panel**
    - section_type: state_machine_trace
    - section_purpose: L3 狀態機轉移追溯（10 個狀態、verification round、Red_Code 旗標）
12. **dispatch_signals_matrix**
    - section_type: signal_matrix
    - section_purpose: 7 個派工信號觸發狀態（對齊 `diagnostic-state-machine-spec`）
13. **admin_override_console**
    - section_type: action_console
    - section_purpose: 覆寫決策、訓練反饋提交、原因填寫與 audit-events 紀錄預覽

### 子頁面 A33 — SOP 績效儀表板 `/admin/knowledge-base/sop-performance`

14. **sop_performance_header**
    - section_type: page_header
    - section_purpose: 時間區段切換、租戶/品牌篩選、匯出按鈕
15. **sop_kpi_summary**
    - section_type: kpi_cards
    - section_purpose: SOP 總數、平均使用率、平均成功率、需檢視數摘要
16. **sop_performance_table**
    - section_type: data_table_with_trend
    - section_purpose: 各 SOP 績效列表（使用次數、成功率、滿意度、趨勢 sparkline）
17. **sop_drilldown_panel**
    - section_type: slide_over_detail
    - section_purpose: 側滑面板下鑽單一 SOP（每日趨勢、失敗案例、標記需檢視觸發審核）

---

## [SECTION COMPONENT SPEC]

### 子頁面 A23: 客戶主檔 `/admin/customers`

### Section: customers_page_header

- **layout**: 單列 flex，`flex items-center justify-between mb-6 gap-4`
- **elements**:
  - page_title: H1 / required / "客戶主檔" / `text-2xl font-semibold text-[#1E293B]`
  - tenant_scope_badge: Badge / required / `bg-blue-50 text-[#2563EB] border border-blue-200 rounded-md px-2 py-0.5 text-xs` / 顯示當前租戶名稱 + lock icon / Tooltip: "RLS 僅顯示本租戶客戶"
  - global_search: Input / required / `w-80` / icon: Search / placeholder: "搜尋姓名 / 電話 / LINE ID / 地址…" / debounce 300ms / 支援模糊比對與電話去格式化（`09-1234-5678` 自動轉 `0912345678` 比對）
  - add_customer_btn: Button Primary / required / icon: UserPlus / "新增客戶" / 開啟新增 Modal
  - bulk_import_btn: Button Secondary / optional / icon: Upload / "批次匯入 CSV" / 權限 `customers.write`
- **states**:
  - default: 顯示完整 header
  - loading: 搜尋框 disabled + Spinner inline
  - searching: 搜尋框右側 Spinner + 清除按鈕 `X`
  - permission_denied: 新增/匯入按鈕 disabled + Tooltip "需要 customers.write 權限"
- **copy_constraints**: 頁面標題固定「客戶主檔」；租戶 Badge 最多 16 字

### Section: customers_summary_stats

- **layout**: 4 欄 Grid，`grid grid-cols-4 gap-4 mb-4`；Mobile 2 欄
- **elements**:
  - total_customers: Card / required / "總客戶數" + 大數字 / icon: Users / `bg-white`
  - active_customers: Card / required / "活躍客戶（90 天內有工單）" + 數字 + 週變化 trend arrow
  - high_risk_customers: Card / required / "高風險客戶" + 數字 / `bg-red-50 text-red-700` / 數字 > 0 時旁邊 `animate-pulse` 紅點
  - warranty_expiring_soon: Card / required / "30 天內保固到期" + 數字 / `bg-amber-50 text-amber-700` / 點擊 → 自動套用篩選 `warranty_end_within: 30`
- **states**:
  - default: 顯示四卡
  - loading: Skeleton 四張卡片（`h-24 rounded-xl`）
  - error: 單卡替換為 `ErrorState mini` + 重試 icon
- **copy_constraints**: 卡片標題 ≤ 20 字元；數字以千分位 `toLocaleString()` 顯示

### Section: customers_filter_bar

- **layout**: `flex flex-wrap gap-3 mb-4 p-4 bg-white rounded-lg border border-gray-200`
- **elements**:
  - risk_level_filter: Multi-Select / required / "風險等級" / 選項：low / medium / high / blacklisted
  - device_brand_filter: Multi-Select / optional / "設備品牌" / 動態載入（Dormakaba / Yale / Hafele …）
  - warranty_status_filter: Select / optional / "保固狀態" / 全部 / active / grace_period / expired
  - preferred_technician_filter: Select / optional / "偏好技師" / 選項搜尋式
  - last_service_range_picker: DateRangePicker / optional / "最近服務區間" / 預設最長 365 天
  - active_filters_count: Badge / required / "已套用 {n} 個篩選" / 點擊顯示當前 filter chips
  - clear_filters_btn: Button Ghost / optional / "清除全部" / 有任何篩選時顯示
- **states**:
  - default: 無篩選時所有欄位為預設值
  - applied: 有篩選時 active_filters_count 顯示數量 + `bg-blue-100 text-[#2563EB]`
  - loading: 動態選項載入 Spinner
- **copy_constraints**: 每個 filter 標籤 ≤ 6 字

### Section: customers_data_table

- **layout**: 全寬 DataTable，固定表頭，`bg-white rounded-xl border border-gray-200 overflow-hidden`
- **elements**:
  - col_customer_name: AvatarText / required / 姓名（若有 LINE 顯示 LINE 頭像、否則首字 fallback）+ 電話次行 caption
  - col_line_id: Text Code / optional / `line_user_id` 遮罩顯示（`U1234****cdef`）/ hover 顯示完整
  - col_address: Text / required / 地址（最多 30 字元 + Tooltip 完整）
  - col_device_count: Badge / required / "{n} 台設備" / 點擊展開列內設備縮略表
  - col_total_orders: Text Number / required / 總工單數
  - col_satisfaction_avg: StarRating / required / 平均滿意度（1–5）/ < 3.0 `text-red-600` / 3.0–4.0 `text-amber-600` / > 4.0 `text-green-600`
  - col_risk_level: RiskBadge / required /
    - low：`bg-green-100 text-green-700` "低風險"
    - medium：`bg-amber-100 text-amber-700` "中風險"
    - high：`bg-red-100 text-red-700 font-bold` "高風險" + 近 90 天爭議數 Tooltip
    - blacklisted：`bg-gray-900 text-white` "黑名單"
  - col_preferred_tech: Text / optional / 偏好技師名稱 / `text-gray-500 italic`（若為 `blocked_technicians` 則顯示封鎖 icon）
  - col_warranty_alert: WarrantyIndicator / required /
    - 無設備：—
    - 全部有效：綠色盾牌 icon
    - 任一設備 30 天內到期：琥珀色 + "{days}天" caption
    - 任一設備已過期：紅色叉號 + "已過期 {n}"
  - col_actions: ActionButtons / required /
    - "檢視" Button Ghost Small → 跳轉 `/admin/customers/{id}`
    - "合併" Button Ghost Small / 權限 `customers.write` / 開啟合併流程
    - Dropdown more：封鎖 / 解除封鎖 / 匯出單一客戶 PDF
  - pagination: CursorPagination / required / 每頁 20 / 50 / 100 切換
  - row_density_toggle: IconButton / optional / 表格密度切換（comfortable / compact）
- **states**:
  - default: 顯示列表，預設排序 `-last_service_at`
  - hover: 整列 `bg-blue-50 cursor-pointer`；高風險列 hover 為 `bg-red-50`
  - selected: Checkbox 選中列 `bg-blue-100 border-l-4 border-[#2563EB]`（批次操作用）
  - loading: 10 列 Skeleton rows
  - empty: Illustration + "尚無客戶資料" + "新增第一位客戶" CTA
  - empty_filtered: "此條件下無客戶，請調整篩選" + 清除篩選按鈕
  - error: ErrorState + 重試
  - merging: 合併來源列標記 `ring-2 ring-amber-400`
- **copy_constraints**: 地址欄位超過 30 字截斷；手機欄位遵循 `XXX-XXX-XXXX` 格式顯示

---

### 子頁面 A24: 客戶詳情 `/admin/customers/[id]`

### Section: customer_detail_header

- **layout**: Sticky top header，`sticky top-16 z-20 bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4`
- **elements**:
  - back_btn: IconButton / required / icon: ArrowLeft / "返回列表"
  - customer_avatar: Avatar / required / `w-14 h-14` / LINE 頭像或首字
  - customer_identity_block:
    - name_h1: H1 / required / 姓名 / `text-xl font-semibold`
    - subtitle: Text / required / 電話 · LINE · 地址 · 建檔日 / `text-sm text-gray-500` / 用 `·` 分隔
  - risk_badge: RiskBadge / required / 同列表規格 / 較大尺寸 `px-3 py-1 text-sm`
  - device_count_badge: Badge / required / "{n} 台設備" / `bg-gray-100`
  - quick_actions:
    - create_work_order_btn: Button Primary / required / icon: FilePlus / "為此客戶建立工單"
    - send_line_btn: Button Secondary / optional / icon: MessageCircle / "LINE 關心" / 僅有 line_user_id 時啟用
    - merge_btn: Button Ghost / required / icon: GitMerge / "合併客戶" / 開啟 merge_modal
    - more_dropdown: DropdownMenu / required / 封鎖、加入黑名單、匯出 PDF、刪除（軟刪）
- **states**:
  - default: Sticky 顯示
  - scrolled: scroll 後陰影加深 `shadow-sm`
  - loading: Skeleton（頭像 + 兩行文字 + 右側按鈕骨架）
  - not_found: 404 Empty + 返回按鈕
  - permission_denied: 快捷動作 disabled + Tooltip
- **copy_constraints**: 姓名 ≤ 40 字元；subtitle 各欄位過長 truncate

### Section: customer_detail_tabs

- **layout**: shadcn/ui `<Tabs>` 水平 tab bar + 內容區，`max-w-6xl mx-auto p-6`
- **elements**:
  - tabs_trigger_list:
    - tab_profile: Tab / required / "基本資料" / 預設啟用
    - tab_devices: Tab / required / "名下設備" + Badge `{count}`（缺保固時紅點）
    - tab_service_history: Tab / required / "服務歷史" + Badge `{count}`
    - tab_financial: Tab / required / "財務紀錄" / 僅 finance / admin 可見
    - tab_notes_risk: Tab / required / "備註 / 風險"（高風險客戶 tab 標題旁紅點）
  - tab_content_profile: FormSection / required /
    - name_input: Input / required / 姓名 / 最多 40 字
    - phone_input: PhoneInput / required / 電話 / 自動格式化、E.164 驗證 / 唯一性檢查（tenant 內去重）
    - line_id_display: Text Code / optional / LINE user ID（唯讀，由 LINE 綁定流程寫入）
    - address_input: AddressInput / optional / 支援 Google Place Autocomplete / 分段儲存（city / district / street）
    - preferred_technician_select: TechnicianSelect / optional / 偏好技師搜尋下拉
    - blocked_technicians_multiselect: TechnicianMultiSelect / optional / 封鎖技師清單（派工不派）
    - contact_time_preference: TimeRangePicker / optional / "可聯絡時段" / 07:00–22:00 設定
    - payment_method_select: Select / optional / 現金 / 信用卡 / LINE Pay / 匯款
    - save_btn: Button Primary / required / "儲存變更" / 有改動時啟用（dirty state）
    - cancel_btn: Button Ghost / optional / "復原變更" / dirty 時顯示
  - tab_content_devices: DeviceList / required /
    - device_card[]: Card Grid 2 欄 /
      - header: brand + model + 位置 description（"前門"）
      - serial_display: Text Code / S/N 遮罩
      - install_date: Text / 安裝日期
      - warranty_badge: WarrantyBadge / 綠/琥珀/紅
      - days_remaining: "剩餘 {n} 天" 或 "今日到期" 或 "已過期 {n} 天"
      - warranty_reminder_alert: AlertBanner / `bg-amber-50` / 30 天內到期顯示 "已於 {date} 發送 LINE 關心續保"
      - device_repair_count: Badge / 歷史維修次數
      - actions: "檢視維修紀錄" / "轉移至其他客戶" / "停用設備"
    - add_device_btn: Button Primary / required / icon: Plus / "新增設備"
  - tab_content_service_history: Timeline / required /
    - 每條工單一個 timeline entry：日期 · 狀態 Badge · 技師 · 金額 · 滿意度 · 爭議旗標
    - filter_bar: 日期區間、狀態、爭議與否
    - 點擊 entry → 跳轉 `/admin/work-orders/{id}`
  - tab_content_financial: FinancialSummary + Table /
    - summary_cards: 累計消費、累計退款、未結餘額、平均客單價
    - invoices_table: 發票列表（編號 / 日期 / 金額 / 狀態 / PDF 下載）
    - refunds_table: 退款列表（編號 / 日期 / 金額 / 原因 / 狀態）
  - tab_content_notes_risk: NotesPanel + RiskAssessment /
    - risk_indicator_box: AlertBox / `bg-red-50 border-red-200` / 顯示 risk_level 與自動評估依據（近 90 天爭議次數、no-show 次數）
    - auto_rule_hint: Text Caption / "規則：近 90 天爭議 ≥ 2 次 → high；2 次 no-show → high_risk"
    - notes_textarea: Textarea / required / 管理員備註（最多 2000 字）/ 每次儲存版本化
    - notes_history: Timeline / 備註修改歷史（誰在何時改了什麼）
    - risk_override_btn: Button Secondary / optional / "人工覆寫風險等級" / 需填原因，寫 audit-events
- **states**:
  - default: profile tab active，其他 tab 僅 trigger 顯示
  - tab_switching: 切換 tab 時內容區淡入 `transition-opacity duration-150`
  - profile_dirty: save_btn 啟用 + "未儲存變更" amber Badge 在 header 顯示
  - profile_validating: save 時按鈕 Spinner
  - device_warranty_alert: 設備卡片若 30 天內到期 `ring-1 ring-amber-400`
  - empty_devices: "此客戶尚無設備紀錄" + 新增按鈕
  - empty_history: "尚無服務紀錄"
  - loading: 對應 tab 內容 Skeleton
  - error: ErrorState per-tab
  - permission_denied_financial: 非 finance/admin 時 tab trigger disabled + Tooltip
- **copy_constraints**: 備註最多 2000 字；各 tab 標題固定；設備位置描述最多 30 字

### Section: customer_merge_modal

- **layout**: shadcn/ui `<Dialog>` 大尺寸（`max-w-3xl`），3 步驟 Stepper
- **elements**:
  - stepper: Stepper / required / 三步驟：選擇合併對象 → 預覽衝突 → 確認遷移
  - step1_select_target:
    - description: Text / "搜尋要合併到當前客戶的重複資料。合併後，被合併方的所有歷史工單、設備、備註、財務紀錄將遷移至當前客戶。"
    - target_search: CustomerSearch / required / 搜尋方式：電話 / LINE ID / 姓名 / 過濾掉自身
    - target_preview_card: Card / 選中後顯示對方基本資訊
  - step2_conflict_preview:
    - comparison_table: Table / required / 欄位對比（主客戶 vs 被合併方），衝突欄位高亮
    - conflict_resolution: 每個衝突欄位 Radio group：保留主方 / 採用對方 / 合併兩者
    - migration_counts: StatBar / 顯示將遷移的資料量
      - `{n}` 筆工單將遷移
      - `{n}` 台設備將遷移
      - `{n}` 筆發票/退款將遷移
      - `{n}` 筆備註將合併
  - step3_confirm:
    - warning_banner: AlertBanner / `bg-red-50 border-red-200` / icon: AlertTriangle / "此操作無法復原，合併後被合併方客戶資料將標記為 merged 並隱藏"
    - typed_confirmation: Input / required / "輸入主客戶姓名以確認合併" / 比對一致才啟用確認按鈕
    - confirm_btn: Button Destructive / required / "確認合併" / disabled 至輸入一致
    - back_btn: Button Ghost / required / "上一步"
- **states**:
  - step_transition: 動畫 `slide-left 200ms`
  - conflict_found: 衝突欄位 `bg-amber-50`
  - confirming: Spinner + "遷移中…請勿關閉視窗"
  - success: 成功 toast + 自動關閉 Modal + 列表 refetch
  - partial_failure: 顯示哪些資料遷移失敗 + 重試部分操作
  - permission_denied: 無 `customers.merge` 權限時 merge_btn 不顯示
- **copy_constraints**: 警告訊息固定文案；Stepper 步驟名 ≤ 6 字

---

### 子頁面 A32: AI 診斷推理檢視 `/admin/diagnostics/[conversation_id]`

### Section: diagnostic_header

- **layout**: Sticky top header，`sticky top-16 z-20 bg-white border-b border-gray-200 px-6 py-4`
- **elements**:
  - back_btn: IconButton / required / icon: ArrowLeft / 返回對話詳情
  - conversation_id_code: Text Code / required / `font-mono text-gray-500` / 可點擊複製
  - customer_inline: AvatarText / required / 客戶名稱 + 電話 / 點擊跳轉客戶詳情
  - conversation_started_at: Text / required / 對話開始時間
  - final_decision_badge: DecisionBadge / required /
    - sop_auto_dispatch：`bg-green-100 text-green-700` "SOP 自動派工"
    - escalate_to_human：`bg-red-100 text-red-700` "升級人工"
    - continue_ai：`bg-blue-100 text-blue-700` "持續 AI 對話"
    - overridden：右上角加金色星號 icon + Tooltip "已由管理員覆寫"
  - stream_status_indicator: StreamIndicator / required / 三態：
    - live：綠色脈動點 + "即時推理中"（SSE 連線中）
    - completed：灰色圓點 + "推理已完成"
    - error：紅色叉號 + "SSE 斷線 — 重連"
  - export_pdf_btn: Button Secondary / required / icon: FileDown / "匯出追溯 PDF"
  - open_conversation_btn: Button Ghost / required / "開啟原始對話" / 跳轉 `/admin/conversations/{id}`
- **states**:
  - live: `stream_status_indicator` 動畫脈動
  - completed: 靜態顯示
  - error: stream 斷線時顯示 toast + 重連 CTA
  - overridden: header 頂加金色 banner "此診斷已於 {at} 被 {user} 覆寫"
- **copy_constraints**: 對話 ID 固定顯示前 8 碼 + `…` + 後 4 碼；決策 Badge 文案 ≤ 8 字

### Section: l1_vector_search_panel

- **layout**: Card / `bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_header: H2 + L1 badge / required / "L1 向量搜尋" + `bg-blue-100 text-[#2563EB] text-xs rounded-full px-2 py-0.5` "L1"
  - section_subtitle: Text Caption / required / "從 `case_entries` 向量庫以 cosine similarity 比對 Top-5 候選"
  - matched_decision_badge: Badge / required /
    - matched (similarity ≥ threshold)：`bg-green-100 text-green-700` "命中（相似度 {top_sim}）"
    - not_matched：`bg-gray-100 text-gray-600` "未命中 — 進入 L2"
  - confidence_gauge: RadialGauge / required / 0–100 / 顯示 `l1.confidence × 100`
  - candidates_table: RankedTable / required /
    - col_rank: Text / 1–5 / 第 1 名加金色冠冕 icon
    - col_case_id: Text Code / `font-mono` / 點擊跳轉 `/admin/knowledge-base/cases/{id}`
    - col_title: Text / 案例標題 / truncate 40 字
    - col_similarity: SimilarityBar / 水平 bar + 百分比 / 色階（≥0.85 綠 / 0.70–0.85 琥珀 / <0.70 灰）
    - col_matched_fields: ChipList / 命中欄位（symptom / failure_mode / brand / model …）
    - col_preview_btn: Button Ghost Small / "預覽" / 開啟案例 side drawer
  - threshold_hint: Text Caption / required / "命中閾值：0.78（租戶設定）"
- **states**:
  - default: 顯示 Top-5
  - loading: Skeleton rows + gauge shimmer
  - not_matched: candidates_table 仍顯示但標題加 "（低於閾值）"
  - empty: "向量庫尚無資料 — 進入 L2 回退" + info banner
  - error: Fetch 失敗時 ErrorState
- **copy_constraints**: 命中欄位 chip 最多顯示 3 個，其餘 `+N`

### Section: l2_rag_generation_panel

- **layout**: Card / `bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_header: H2 + L2 badge / required / "L2 RAG 生成" + `bg-purple-100 text-purple-700` "L2"
  - triggered_indicator: Badge / required / triggered=true 顯示 "已觸發" 綠色 / false "未觸發（L1 已命中）" 灰色
  - metadata_row: `grid grid-cols-3 gap-4` /
    - confidence_stat: StatBlock / "信心分數" + `{confidence.toFixed(2)}` / <0.6 紅色 / 0.6–0.8 琥珀 / >0.8 綠
    - tokens_stat: StatBlock / "Token 用量" + `{tokens}` / 附成本估算 `~NT${cost}`
    - model_stat: StatBlock / "模型" + model name（如 `gpt-4o-mini`）
  - prompt_viewer: CollapsibleCodeBlock / required /
    - header: "LLM Prompt" + 折疊/展開 + 複製按鈕
    - content: `<pre>` / `bg-gray-900 text-gray-100 rounded-lg p-4 text-sm font-mono overflow-x-auto max-h-96` / 語法高亮 markdown
    - visibility: 僅 admin 可見（reviewer 角色無此權限）→ 顯示 `PermissionDenied` placeholder
  - response_viewer: StreamingResponseViewer / required /
    - header: "LLM Response" + 播放控制（▶ 重播 SSE / ⏸ 暫停 / ⏭ 快轉至結尾）
    - content: markdown 渲染區 / 即時串流時逐 token 顯示 typing cursor `|` / 完成後靜態渲染
    - token_highlight: hover token 顯示 logprob（若後端提供）
  - citations_list: CitationList / optional / LLM 引用的知識來源（case_id / sop_id）/ 點擊跳轉
- **states**:
  - default: 靜態展示（completed）
  - streaming: response_viewer 逐 token 渲染，typing cursor `animate-pulse`
  - streaming_error: "SSE 斷線於第 {n} token" + 重連按鈕
  - empty (triggered=false): panel 塌縮只顯示 header + 說明 "L1 已命中，未觸發 L2"
  - prompt_hidden: reviewer 角色看到 "僅 admin 可查看 prompt" 鎖定 icon
  - loading: 三格 metadata Skeleton + 兩個 CodeBlock Skeleton
- **copy_constraints**: Prompt / Response 無長度限制（可捲動）；信心分數固定兩位小數

### Section: l3_escalation_panel

- **layout**: Card / `bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_header: H2 + L3 badge / required / "L3 升級判定" + `bg-red-100 text-red-700` "L3"
  - triggered_indicator: Badge / required / triggered=true "已升級至人工" 紅色 / false "未升級" 灰色
  - reason_block: AlertBox / optional / triggered 時顯示 / `bg-red-50 border-red-200` / icon: AlertOctagon / 顯示 `l3.reason`（如 "Red_Code / 客戶要求真人 / 3 輪驗證未收斂"）
  - state_machine_trace: Timeline / required / 對齊 `diagnostic-state-machine-spec` 10 狀態
    - 每個 transition 一個 timeline item：
      - timestamp: Text Caption
      - from_state → to_state: StateBadge pair / 箭頭連接
      - trigger_reason: Text / 觸發原因（"symptoms extracted" / "Red_Code" / "3-round limit"）
      - verification_round: Badge / 若 state=VERIFYING 顯示 "第 {n}/3 輪"
    - current_state_highlight: 最後一個 item `ring-2 ring-[#F59E0B]`
  - diagnostic_context_summary: `grid grid-cols-2 gap-4` /
    - extracted_symptoms: ChipList / symptom IDs
    - matched_failures: ChipList / Failure IDs (F-LOCK-001 …)
    - hypothesized_fms: ChipList / FM IDs + confidence
    - verification_qa: Accordion / 展開顯示 `[{round, question, answer}]`
  - flags_row: FlagRow / required / 三旗標：
    - red_code: `Flag` / 觸發時紅色 + 原因 OCAP 代碼
    - escalation_required: `Flag` / 觸發時橘色
    - dispatch_signal_detected: `Flag` / 觸發時藍色
- **states**:
  - default: 顯示完整 trace
  - in_progress: current_state_highlight 脈動
  - red_code_triggered: 整 Card `border-red-500 border-2` + 告警 banner 頂部
  - empty_trace: "尚未產生狀態轉移（INTAKE）"
  - loading: Timeline Skeleton 5 items
- **copy_constraints**: state 名稱使用英文常數（INTAKE / VERIFYING …），中文說明作為 tooltip

### Section: dispatch_signals_matrix

- **layout**: Card / `bg-white rounded-xl border border-gray-200 p-6 mb-6`
- **elements**:
  - section_header: H2 / required / "派工決策信號矩陣" + Text Caption "對齊 diagnostic-state-machine-spec 7 個信號"
  - signals_grid: `grid grid-cols-2 gap-3` / Mobile 1 欄 / 7 個信號卡片：
    - signal_card template:
      - signal_name: Text 英文常數 / `font-mono text-sm`
      - signal_display_name: Text 中文 / `font-medium`
      - triggered_dot: StatusDot / triggered=true 紅色脈動 / false 灰色
      - triggered_badge: Badge / "已觸發" / "未觸發"
      - evidence_link: Button Ghost Small / "檢視證據" / 展開該信號觸發的對話片段
    - 7 個信號具體：
      1. `brand_error_code_present` — "偵測到品牌錯誤碼" / 觸發→直接 DISPATCH
      2. `diagnosis_not_converging` — "診斷未收斂（3 輪上限）" / 強制 DISPATCH
      3. `customer_info_complete` — "客戶資訊完整" / 派工前置條件
      4. `needs_certified_technician` — "需認證技師" / 影響派工匹配
      5. `remote_fix_possible` — "可遠端修復" / 觸發→REMOTE_RESOLVED
      6. `customer_requests_human` — "客戶要求真人" / 觸發→ESCALATED
      7. `agent_confidence_low` — "Agent 信心過低" / 建議升級
  - decision_resolution_explainer: ExplainerBox / required / `bg-blue-50 border-blue-200` / icon: Info /
    - 顯示 resolve_next_state 優先序：P1 Red_Code → P2 派工信號 → P3 輪次上限 → P4 LLM 建議
    - 視覺化當前對話命中哪個優先級 → 導致哪個決策
- **states**:
  - default: 顯示 7 張信號卡
  - triggered: 觸發的信號卡 `border-red-300 bg-red-50` + 脈動 icon
  - loading: Skeleton 7 張卡
  - hover_signal: Tooltip 顯示該信號的完整英文定義
- **copy_constraints**: 信號中文名 ≤ 12 字；英文常數保持小寫底線格式

### Section: admin_override_console

- **layout**: Sticky bottom console / `sticky bottom-0 z-10 bg-white border-t-2 border-[#F59E0B] shadow-lg p-6`
- **elements**:
  - section_header: H3 / required / "管理員介入" / icon: ShieldAlert / `text-[#F59E0B]`
  - warning_hint: Text Caption / required / "覆寫是單案操作（不影響模型訓練）。若要改善模型請同時提交『訓練反饋』。"
  - override_action_group: `grid grid-cols-2 gap-4 mb-4` /
    - override_decision_card: Card / required /
      - title: "覆寫派工決策"
      - current_decision_display: Text / "當前決策：{final_decision}"
      - new_decision_select: Select / required / 選項：
        - 強制派工（force_dispatch）
        - 更改 SOP（reassign_sop） → 觸發 SOP picker
        - 升級真人（escalate_to_human）
        - 關閉工單（close_conversation）
      - sop_picker: SOPSearchSelect / conditional / 當選 reassign_sop 時顯示
      - reason_textarea: Textarea / required / "覆寫原因（將寫入 audit-events）" / 最少 20 字
      - submit_override_btn: Button Primary / required / "提交覆寫"
    - training_feedback_card: Card / required /
      - title: "提交訓練反饋"
      - feedback_type_radio: RadioGroup / required / 選項：
        - L1 命中錯誤（l1_false_positive / l1_false_negative）
        - L2 回應不當（l2_response_incorrect）
        - 狀態機轉移錯誤（state_transition_wrong）
        - 信號誤觸/漏觸（signal_misfire）
        - 其他（other）
      - anonymize_checkbox: Checkbox / required / 預設勾選 / "匿名化個資後進入 Agent Harness feedback loop" / Tooltip 說明遮罩哪些欄位
      - feedback_detail_textarea: Textarea / required / "具體說明（最少 30 字）"
      - submit_feedback_btn: Button Secondary / required / "提交反饋"
  - audit_preview: Collapsible / required / "預覽將寫入的 audit event"（展開顯示 JSON payload：event_type, actor, resource, payload）
  - keyboard_shortcut_hint: Text Caption / "⌘+Enter 快速提交"
- **states**:
  - default: 兩張卡並列顯示
  - reason_too_short: submit 按鈕 disabled + 行內紅字 "至少 20 字"
  - submitting: Spinner + "提交中…"
  - success_override: Toast "已覆寫決策並寫入 audit-events" + header 顯示覆寫 banner + SSE 推送 `/realtime/diagnostics/{id}` 即時刷新
  - success_feedback: Toast "反饋已提交至 Agent Harness（inter-agent-messaging）"
  - error: Toast 錯誤訊息 + 重試
  - already_overridden: 覆寫卡顯示 "此診斷已於 {at} 被 {user} 覆寫" + 禁止重複覆寫 banner
  - permission_denied: 整 console 替換為 "您沒有覆寫權限（需要 diagnostics.override）" 提示
- **copy_constraints**: 覆寫原因 20–500 字；反饋詳情 30–1000 字；所有操作必填原因不可略

---

### 子頁面 A33: SOP 績效儀表板 `/admin/knowledge-base/sop-performance`

### Section: sop_performance_header

- **layout**: `flex items-center justify-between mb-6`
- **elements**:
  - page_title: H1 / required / "SOP 績效儀表板"
  - time_range_tabs: SegmentedControl / required / 今日 / 近 7 天 / 近 30 天 / 近 90 天 / 自訂 / 預設 30 天
  - date_range_picker: DateRangePicker / conditional / 選「自訂」時顯示
  - brand_filter: MultiSelect / optional / 品牌篩選
  - category_filter: MultiSelect / optional / SOP 類別
  - export_btn: Button Secondary / optional / icon: FileDown / "匯出 Excel" / 匯出當前篩選結果
  - refresh_btn: IconButton / optional / icon: RefreshCw / 手動刷新 / 資料延遲 tooltip "資料延遲 ≤ 5 分鐘（Materialized View）"
- **states**:
  - default: 預設近 30 天全部 SOP
  - loading: 全區 Skeleton
  - stale_indicator: 資料超過 10 分鐘未更新時顯示 "資料較舊" amber pill
- **copy_constraints**: Tab 標籤 ≤ 6 字

### Section: sop_kpi_summary

- **layout**: 4 欄 Grid，`grid grid-cols-4 gap-4 mb-6`；Mobile 2 欄
- **elements**:
  - total_sops_card: Card / required / "SOP 總數" + 數字 + "上線中 {active_n} / 已下架 {archived_n}"
  - avg_usage_rate_card: Card / required / "平均使用率" + 百分比 + 週變化
  - avg_success_rate_card: Card / required / "平均成功率（遠端解決或派工達成）" + 百分比 + Sparkline / 成功率 <60% 整卡 `bg-red-50`
  - needs_review_card: Card / required / "需檢視 SOP 數" + 數字 / `bg-amber-50` / 點擊自動套用篩選 `flag=needs_review`
- **states**:
  - default: 顯示四卡
  - loading: 四張卡片 Skeleton
  - drill_hover: hover 卡片時顯示 "點擊以篩選" Tooltip
- **copy_constraints**: 百分比固定 1 位小數

### Section: sop_performance_table

- **layout**: 全寬 DataTable，`bg-white rounded-xl border border-gray-200`
- **elements**:
  - col_sop_id: Text Code / required / `font-mono`
  - col_sop_title: Text + MiniBadge / required / 標題 + 類別 Badge（電池故障 / 指紋 / 螢幕 …）
  - col_coverage_brands: ChipList / required / 適用品牌 chips（最多 3 個 + `+N`）
  - col_usage_count: Text Number / required / 使用次數（期間內被 L1 命中或 L2 引用）/ 可排序
  - col_usage_rate: ProgressBar / required / 使用率（使用次數 / 對話總數）/ 0–100%
  - col_success_rate: SuccessRateBadge / required /
    - ≥80%：`bg-green-100 text-green-700` "{n}%"
    - 60–80%：`bg-amber-100 text-amber-700` "{n}%"
    - <60%：`bg-red-100 text-red-700` "{n}%" + 旁邊紅點
  - col_satisfaction_avg: StarRating / required / 客戶滿意度（1–5）
  - col_escalation_rate: Text Number / required / 命中此 SOP 後升級人工比率 / >30% 標紅
  - col_trend_sparkline: Sparkline / required / 近 14 天使用次數走勢 / 上升綠、下降紅
  - col_last_updated: Text / required / 最後更新日期
  - col_flags: FlagRow / required / icons：
    - needs_review（低成功率 + 高升級率自動觸發）：琥珀旗
    - pinned_by_admin：金色圖釘
    - brand_new（<7 天）：藍色 "NEW"
  - col_actions: ActionButtons / required /
    - "下鑽" Button Ghost Small / 開啟 drilldown 側滑面板
    - "編輯 SOP" Button Ghost Small / 跳轉 `/admin/knowledge-base/sops/{id}/edit`
    - "標記需檢視" Button Ghost Small / 觸發審核流程 → 建立 review task + 通知知識運營
  - pagination: CursorPagination / required / 預設 20 每頁
  - sort_select: Select / required / 排序：使用次數 / 成功率 / 滿意度 / 最後更新 / 升級率
- **states**:
  - default: 預設依使用次數降序
  - hover: 整列 `bg-blue-50 cursor-pointer`
  - row_needs_review: 整列左側 `border-l-4 border-amber-400`
  - row_low_success: 整列左側 `border-l-4 border-red-400`
  - loading: 10 列 Skeleton
  - empty: "選定條件下無 SOP 使用紀錄"
  - marking_review: 標記按鈕 Spinner + "標記中…"
  - error: ErrorState
- **copy_constraints**: SOP 標題 ≤ 60 字截斷；類別 Badge ≤ 6 字

### Section: sop_drilldown_panel

- **layout**: 右側 Slide-over Panel / `fixed right-0 top-16 bottom-0 w-[480px] bg-white shadow-2xl border-l border-gray-200 overflow-y-auto`；Mobile 改為全螢幕 Sheet
- **elements**:
  - panel_header:
    - sop_title: H2 / required / SOP 標題
    - sop_id_code: Text Code caption
    - close_btn: IconButton / icon: X
  - kpi_strip: 4 個小 StatBlock（使用次數 / 成功率 / 滿意度 / 升級率）
  - daily_trend_chart: LineChart / required / 近 30/90 天每日使用次數 + 成功率雙軸 / recharts
  - brand_breakdown_chart: BarChart / required / 各品牌命中次數
  - failure_cases_section:
    - section_title: H3 / "低成功率案例（客戶滿意度 < 3.0）"
    - case_list: List / 10 筆失敗案例 / 每筆顯示 conversation_id · 客戶名 · 不滿意原因（從回饋擷取）· 跳轉 `/admin/diagnostics/{conv_id}` 按鈕
  - linked_cases_section:
    - section_title: H3 / "來源案例（case_entries）"
    - case_list: List / 此 SOP 由哪些 case 蒸餾 / 跳轉查看
  - action_panel:
    - mark_review_btn: Button Primary / required / icon: Flag / "標記需檢視" / 需填原因 → 建立 review task → 寫 audit-events → 通知知識運營 → 此 SOP `needs_review=true`
    - archive_sop_btn: Button Destructive / optional / "下架此 SOP" / 需雙重確認
    - view_full_btn: Button Secondary / "開啟完整 SOP 頁"
- **states**:
  - default: 關閉；點擊列表列「下鑽」後 slide-in 200ms
  - loading: Panel 內各 chart Skeleton
  - marked_review: 標記後 `mark_review_btn` 變為 "已標記 — 審核中" disabled + 綠色
  - archived: 下架成功後 panel 顯示 archived banner + 列表 refetch
  - permission_denied: 下架按鈕 disabled + Tooltip
- **copy_constraints**: 失敗原因擷取 ≤ 80 字，超出 `…` + 查看全文 link

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### A23 客戶主檔

1. 進入頁面 → `GET /api/v1/customers` → 摘要 + 列表渲染
2. 輸入搜尋關鍵字（電話/LINE ID/姓名）→ debounce 300ms → refetch；電話自動去格式化比對
3. 套用風險/品牌/保固篩選 → URL query sync → refetch
4. 點擊保固即將到期卡片 → 自動套用 `warranty_end_within=30` → 列表更新
5. 點擊客戶列 → 跳轉 `/admin/customers/{id}`；Cmd+Click 開新分頁
6. 新增客戶：填寫 Modal → 電話/LINE ID 唯一性驗證（失敗顯示 409 訊息）→ 成功 Toast + 列表 refetch

#### A24 客戶詳情

1. 進入頁面 → `GET /api/v1/customers/{id}` → header + 各 tab 資料預載
2. 切換 tab（profile → devices → history → financial → notes_risk）→ lazy fetch 對應資料
3. 編輯基本資料 → dirty state → 點「儲存」→ `PATCH /api/v1/customers/{id}` → 成功 Toast
4. 新增/轉移設備 → Modal → 送出 → `POST /api/v1/customers/{id}/devices` → devices tab refetch
5. 保固 30 天內提醒：系統 cron 每日掃描 → 有到期設備時 devices tab Badge 紅點 + 發 LINE 關心（紀錄在設備卡 `已於 {date} 發送 LINE 關心續保`）
6. 合併客戶：
   - 點 merge → Modal Step1 搜尋對方（電話/LINE ID/姓名）→ Step2 衝突預覽（Comparison Table + 衝突欄位選 Radio）→ Step3 輸入主客戶姓名確認
   - 送出 `POST /api/v1/customers/merge` Body: `{ primary_id, secondary_id, conflict_resolution: {...}, confirmation_text }`
   - 後端：搬移 `work_orders.customer_id`、`customer_devices.customer_id`、`invoices`、`refunds`、`notes`；被合併方 `merged_into=primary_id` 並標記隱藏
   - 成功 → Toast + 關閉 Modal + 跳轉主客戶詳情（list refetch）
   - 操作寫入 `audit-events`（event_type=`data_change`, resource=`customer:merge`）
7. 覆寫風險等級：點 "人工覆寫" → Modal 填原因 → `PATCH /api/v1/customers/{id}/risk` → audit-events

#### A32 AI 診斷推理檢視

1. 進入頁面 → `GET /api/v1/diagnostics/{conversation_id}` → 全量 DiagnosticTrace 載入
2. 同時開啟 WebSocket `/realtime/diagnostics/{conversation_id}`（SSE 降級）→
   - 若推理仍進行中（state ≠ CLOSED），逐 token 接收 L2 response、即時更新狀態機 trace
   - 每次新 transition → timeline 附加新 item + 自動滾動至最新
3. 捲動頁面檢視 L1 / L2 / L3 / signals 各 panel
4. Reviewer 角色 → L2 prompt 區塊顯示 permission_denied，不影響其他區塊
5. 管理員覆寫：
   - 填寫 new_decision + reason（≥20 字）→ 點「提交覆寫」→ `POST /api/v1/diagnostics/{conversation_id}/override` Body: `{ new_decision, reason, context }`
   - 後端：更新 DiagnosticTrace.overridden_by + 寫 audit-events + 推送 `/realtime/diagnostics/{id}` override 事件 → header banner 即時出現
6. 訓練反饋：
   - 填寫 feedback_type + detail + 勾選匿名化 → `POST /api/v1/diagnostics/{conversation_id}/feedback` Body: `{ feedback_type, detail, anonymize: true }`
   - 後端：匿名化 PII（客戶姓名/電話/地址）→ 推送至 Agent Harness `inter-agent-messaging` 頻道 → Toast 成功
7. 匯出 PDF：`POST /api/v1/diagnostics/{conversation_id}/export` → 下載含 L1/L2/L3/signals 完整 trace 的 PDF（用於爭議舉證）

#### A33 SOP 績效儀表板

1. 進入頁面 → `GET /api/v1/knowledge-base/sop-performance?range=30d` → KPI + 表格渲染
2. 切換時間區段 → URL query sync → refetch
3. 套用品牌/類別篩選 → refetch
4. 點擊 KPI 卡「需檢視」→ 自動套用篩選 `flag=needs_review` → 表格更新
5. 點列「下鑽」→ Slide-over Panel 打開 → `GET /api/v1/knowledge-base/sops/{id}/performance` 詳細資料
6. 標記需檢視：填原因 → `POST /api/v1/knowledge-base/sops/{id}/mark-review` → `needs_review=true` + 建立 review task + 通知知識運營 + audit-events
7. 下鑽面板「失敗案例」點擊 → 跳轉對應 `/admin/diagnostics/{conv_id}` 做深度分析

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 完整多欄佈局 | A23 4 卡 summary + 全欄位表格；A24 tab 並列；A32 左右區塊；A33 表格完整 11 欄 |
| Tablet (768–1279px) | 內容區縮至主欄 | A23 summary 2×2；A32 signals 矩陣 2 欄；A33 表格隱藏 trend sparkline；合併 Modal 維持 wide |
| Mobile (<768px) | 單欄堆疊 | A23 表格轉卡片列表；A24 tab 改為頂部 select；A32 各 panel 全寬堆疊、override console 變底部 fixed sheet；A33 表格轉卡片列表；Drilldown 變全螢幕 Sheet |

### 資料更新策略

- A23 客戶列表：`staleTime: 60_000`，搜尋/篩選變更立即 invalidate
- A24 客戶詳情：
  - Profile tab `staleTime: 120_000`
  - Devices tab `staleTime: 300_000`（保固每日 cron 變動低頻）
  - Service history `staleTime: 60_000`
  - Financial `staleTime: 60_000`
- A32 診斷推理：
  - 初次 fetch 後不 polling；改由 WebSocket `/realtime/diagnostics/{conv_id}` 推播
  - SSE 逐 token 渲染，斷線 3s 後自動重連（指數回退）
  - 覆寫/反饋提交後 invalidate + 即時推播
- A33 SOP 績效：
  - `staleTime: 300_000`（5 分鐘，Materialized View 延遲）
  - 手動 refresh 按鈕觸發 invalidate
  - 標記需檢視後 invalidate 列表

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - **客戶主檔**：
    - `GET /api/v1/customers`
      - Query: `search`, `risk_level` (csv), `brand` (csv), `warranty_status`, `warranty_end_within` (days), `preferred_technician_id`, `cursor`, `limit`, `sort_by`
      - Response: `{ items: Customer[], next_cursor, total_count, summary: { total, active, high_risk, warranty_expiring_30d } }`
      - 多租戶 RLS：後端自動注入 `tenant_id` 過濾（V3.0）
    - `POST /api/v1/customers`
      - Body: `{ name, phone, line_user_id?, address?, preferred_technician_id?, ... }`
      - 409: `{ error_code: "DUPLICATE_PHONE" }` 或 `DUPLICATE_LINE_USER_ID`
    - `GET /api/v1/customers/{id}`
      - Response: `{ customer, devices: CustomerDevice[], stats: { total_orders, total_spent, avg_satisfaction, dispute_count_90d } }`
    - `PATCH /api/v1/customers/{id}`
      - Body: partial Customer fields
    - `PATCH /api/v1/customers/{id}/risk`
      - Body: `{ risk_level: 'low'|'medium'|'high'|'blacklisted', reason: string }`
      - 寫 audit-events
    - `POST /api/v1/customers/{id}/devices`
      - Body: CustomerDevice 新增
    - `PATCH /api/v1/customers/{id}/devices/{device_id}`
    - `POST /api/v1/customers/merge`（`Idempotency-Key` 強制）
      - Body: `{ primary_id, secondary_id, conflict_resolution: {...}, confirmation_text }`
      - Response: `{ migrated_counts: { work_orders, devices, invoices, refunds, notes }, merged_customer_id, audit_event_id }`
      - 409: 已被合併或 primary/secondary 不存在；422: confirmation_text 不符
    - `GET /api/v1/customers/{id}/service-history` — 分頁
    - `GET /api/v1/customers/{id}/financial-summary` — 含發票、退款
  - **診斷檢視**：
    - `GET /api/v1/diagnostics/{conversation_id}`
      - Response: `DiagnosticTrace`（對齊 §8.6 TypeScript 契約）
        ```
        { conversation_id, l1: { candidates[], matched, confidence },
          l2: { triggered, prompt?, response?, confidence?, tokens? },
          l3: { triggered, reason? },
          dispatch_signals: { ...7 booleans },
          decision, overridden_by? }
        ```
      - Reviewer 角色：`l2.prompt` 欄位被後端 mask 為 `null`
    - `POST /api/v1/diagnostics/{conversation_id}/override`（`Idempotency-Key` 強制）
      - Body: `{ new_decision: 'force_dispatch'|'reassign_sop'|'escalate_to_human'|'close_conversation', sop_id?: string, reason: string }`
      - 422: reason 不足 20 字；409: 已被覆寫
      - 寫 audit-events + 推送 `/realtime/diagnostics/{id}`
    - `POST /api/v1/diagnostics/{conversation_id}/feedback`
      - Body: `{ feedback_type, detail, anonymize: boolean }`
      - 透過 `inter-agent-messaging` 推送至 Agent Harness feedback channel
    - `POST /api/v1/diagnostics/{conversation_id}/export`
      - Response: PDF blob（含完整 trace，用於爭議舉證）
  - **SOP 績效**：
    - `GET /api/v1/knowledge-base/sop-performance`
      - Query: `range` (7d|30d|90d|custom), `date_from`, `date_to`, `brand` (csv), `category` (csv), `flag`, `sort_by`, `cursor`, `limit`
      - Response: `{ items: SOPPerformance[], next_cursor, total_count, summary: { total_sops, active, archived, avg_usage_rate, avg_success_rate, needs_review_count } }`
    - `GET /api/v1/knowledge-base/sops/{id}/performance`
      - Response: `{ sop, daily_trend[], brand_breakdown[], failure_cases[], linked_cases[] }`
    - `POST /api/v1/knowledge-base/sops/{id}/mark-review`
      - Body: `{ reason: string }` → 寫 audit-events + 建立 review task
    - `POST /api/v1/knowledge-base/sops/{id}/archive`（雙重確認）
  - **WebSocket / SSE**：
    - `wss://app.smartlock-saas.com/ws/realtime/diagnostics/{conversation_id}`
      - 訊息類型：
        - `l2_token`：SSE 逐 token 串流（`{ token, index, total? }`）
        - `state_transition`：`{ from_state, to_state, at, trigger }`
        - `signal_change`：`{ signal_name, triggered }`
        - `decision_final`：`{ decision }`
        - `overridden`：`{ overridden_by: { user_id, reason, at } }`
      - 斷線重連：攜帶 `last_event_id` 要求 replay（server 保留 5 分鐘）
      - SSE 降級：若 WebSocket 無法連線，fallback 至 `GET /api/v1/diagnostics/{conversation_id}/stream` (text/event-stream)
- **Zustand Stores**：
  - `useCustomersStore`：管理列表篩選、合併流程 step 狀態
  - `useCustomerDetailStore`：管理 tab dirty state、devices 編輯緩衝
  - `useDiagnosticStore`：管理 SSE 連線狀態、override/feedback 表單 dirty、L2 token buffer
  - `useSOPPerformanceStore`：管理 range、filter、drilldown open state
- **error_cases**：
  - 網路錯誤：Toast + TanStack Query 指數回退重試（1→2→4→8s 上限 16s）
  - 電話/LINE 重複（409）：新增 Modal 行內紅字 "此電話已存在於客戶 {masked_name}，是否合併？" + 快捷進入合併流程
  - 合併衝突（409 `MERGE_CONFLICT_OPEN_WORK_ORDERS`）：兩方有進行中工單時不可合併 → Toast + 列出阻擋的工單 ID
  - 合併 confirmation_text 不符（422）：Input 行內紅字 "姓名不一致"
  - 保固計算：前端不自行計算，一律使用後端回傳的 `warranty_status` / `days_remaining`
  - 診斷不存在（404）：顯示 Empty + "此對話無診斷紀錄（可能發生於 V1.0 舊對話）"
  - 覆寫已存在（409 `ALREADY_OVERRIDDEN`）：整個 override_action_group disabled + 顯示現有覆寫 banner
  - Reviewer 角色讀 prompt（403）：prompt_viewer 替換為 permission_denied placeholder（由後端 mask 為 null，前端對應顯示）
  - SSE 斷線：Toast + 自動重連；連續失敗 3 次 fallback 至 polling `GET /api/v1/diagnostics/{id}` 每 10 秒
  - SOP 標記需檢視衝突（409）：Toast "此 SOP 已被 {user} 於 {at} 標記審核中"
  - SOP 下架衝突（409）：若 SOP 當日仍被對話命中 → 要求先停用「AI 自動派工」能力才能下架

---

## [EXCEPTION TO GLOBAL RULES]

- A32 診斷檢視的 L2 `prompt_viewer` 與 `response_viewer` 使用深色主題 `bg-gray-900`，與 Global 淺色 BG 不同（與稽核日誌 JSON 一致）。
- A32 管理員覆寫 console 採 `sticky bottom-0` 強制固定於視窗底部，高度 `min-h-[180px]`，突破 Global Page Footer 規則（確保管理員長時間閱讀 trace 時操作按鈕始終可見）。
- A32 SSE 串流渲染採逐 token 寫入（`useSyncExternalStore` 訂閱 token buffer），不受 Global TanStack Query staleTime 管控。
- A24 客戶合併 Modal 使用 `max-w-3xl`（寬於 Global Dialog 預設 max-w-lg），因需並列顯示衝突欄位對比表。
- A24 Sticky Header `top-16` 覆蓋 Admin Shell 頂部導覽列高度，與 Global Page Header 規則一致但額外附陰影過渡。
- A33 下鑽 Slide-over Panel 寬度 `w-[480px]`，非 Global 側欄標準 `w-96`，因需容納 LineChart + BarChart 雙圖。
- A23 列表 `col_line_id` 遮罩顯示（`U1234****cdef`）與 Global 表格文字直接顯示規則不同，為 GDPR / PDPA 合規要求。
- A32 的 L2 `prompt` 欄位對 Reviewer 角色回傳 `null`，Reviewer 視圖顯示 permission_denied placeholder，突破 Global "所有資料一視同仁" 表格規則（屬法遵資料敏感性分級）。

---

## [ACCEPTANCE CRITERIA]

### 共用

- [ ] 所有頁面具備 loading / error / empty 三態
- [ ] RWD 三斷點（Desktop / Tablet / Mobile）佈局正確
- [ ] 多租戶 RLS：切換租戶（V3.0）後各頁面資料完全隔離，無殘留
- [ ] URL query 與篩選狀態雙向同步（可分享連結）
- [ ] 鍵盤導航可達所有互動元件，WCAG 2.1 AA 合規
- [ ] 符合 Design System（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）

### A23 客戶主檔

- [ ] 支援電話/LINE ID 去重：新增/合併時驗證唯一性（409 明確訊息）
- [ ] 電話搜尋自動去格式化（`09-1234-5678` 與 `0912345678` 一致命中）
- [ ] 風險等級自動評估：後端邏輯「近 90 天爭議 ≥ 2 次 → high」正確反映於列表 Badge
- [ ] 高風險客戶列紅色 hover、保固即將到期卡片可點擊篩選
- [ ] LINE user ID 以遮罩形式顯示，hover 顯示完整
- [ ] 批次匯入 CSV 功能支援欄位映射與錯誤行回報（權限 `customers.write`）

### A24 客戶詳情

- [ ] 5 個 tabs（基本資料 / 名下設備 / 服務歷史 / 財務紀錄 / 備註風險）完整呈現
- [ ] 基本資料 tab 的 dirty state + 儲存 + 復原流程正常
- [ ] 名下設備 30 天內到期以琥珀色標示，已於 cron 發送 LINE 關心的設備顯示發送紀錄
- [ ] 財務 tab 僅 finance / admin 可見（reviewer 無此 tab）
- [ ] 備註 tab 版本化歷史正確紀錄修改者與時間
- [ ] 客戶合併 3 步驟 Stepper 完整：
  - 衝突欄位支援「保留主方 / 採用對方 / 合併兩者」三選一
  - 遷移數量預覽（工單/設備/發票/退款/備註）正確
  - confirmation_text 驗證正確
  - 合併成功後 `work_orders.customer_id` 全部遷移，被合併方標記 `merged_into` 並隱藏
  - 操作寫入 `audit-events`
- [ ] 兩方有進行中工單時合併被阻擋（409 明確列出阻擋工單）
- [ ] 人工覆寫風險等級需填原因並寫入 audit-events

### A32 AI 診斷推理檢視

- [ ] 完整呈現 L1 Top-5 候選 + 相似度色階 + 命中欄位 chips
- [ ] L1 confidence RadialGauge、閾值 tooltip 正確顯示
- [ ] L2 prompt / response 使用深色 CodeBlock，Reviewer 角色看不到 prompt
- [ ] L2 response SSE 逐 token 渲染，支援重播 / 暫停 / 快轉
- [ ] L2 metadata（confidence / tokens / cost）正確
- [ ] L3 狀態機 Timeline 完整呈現 10 狀態轉移，current state 高亮
- [ ] L3 三旗標（red_code / escalation_required / dispatch_signal_detected）狀態正確
- [ ] 7 個派工信號矩陣（對齊 `diagnostic-state-machine-spec`）：
  - brand_error_code_present、diagnosis_not_converging、customer_info_complete、needs_certified_technician、remote_fix_possible、customer_requests_human、agent_confidence_low
  - 觸發卡片紅色脈動 + 可展開證據對話片段
- [ ] resolve_next_state 優先級解釋器（P1 Red_Code > P2 派工信號 > P3 輪次上限 > P4 LLM）正確視覺化
- [ ] 管理員覆寫 UX：
  - 4 種決策選項（force_dispatch / reassign_sop / escalate_to_human / close_conversation）
  - reason ≥ 20 字驗證
  - 提交後寫 audit-events + WebSocket 即時推送 override 事件 + header 顯示覆寫 banner
- [ ] 訓練反饋：
  - 5 種 feedback_type
  - 匿名化 checkbox 預設勾選，tooltip 說明遮罩哪些 PII
  - 提交後推送至 Agent Harness inter-agent-messaging
- [ ] 已覆寫診斷再次進入時禁止重複覆寫（409）
- [ ] 匯出 PDF 含完整 L1/L2/L3/signals trace
- [ ] WebSocket 斷線 3 次 fallback 至 polling

### A33 SOP 績效儀表板

- [ ] 時間區段切換（今日 / 7d / 30d / 90d / 自訂）正常
- [ ] KPI 四卡（總數 / 使用率 / 成功率 / 需檢視數）正確
- [ ] 成功率 <60% 整卡紅底；需檢視數 > 0 琥珀底
- [ ] 表格 11 欄完整呈現，支援排序與 cursor 分頁
- [ ] 成功率 Badge 三色碼正確（≥80% 綠 / 60–80% 琥珀 / <60% 紅）
- [ ] 升級率 >30% 標紅
- [ ] Trend sparkline 近 14 天走勢正確
- [ ] needs_review / pinned / brand_new 三種 flag icons 正確呈現
- [ ] 「標記需檢視」→ 填原因 → 寫 audit-events + 建立 review task + 通知知識運營
- [ ] 下鑽 Slide-over 包含每日 LineChart、品牌 BarChart、失敗案例列表（可跳轉 A32）、來源案例列表
- [ ] 資料延遲 ≤ 5 分鐘（Materialized View），超過 10 分鐘顯示 "資料較舊" pill
- [ ] 匯出 Excel 功能正常（權限 `knowledge_base.export`）

### 效能與規範

- [ ] A23 首次載入 < 2 秒（不含未渲染 tab）
- [ ] A24 tab 切換 < 300ms（lazy fetch）
- [ ] A32 DiagnosticTrace 初次 fetch < 1.5 秒；SSE 首 token < 500ms
- [ ] A33 KPI + Table 首次渲染 < 2 秒（Materialized View）
- [ ] 所有敏感操作（合併、覆寫、下架、風險覆寫、標記需檢視）寫入 `audit-events`
- [ ] 所有 mutation 附 `Idempotency-Key`（合併、覆寫、標記、下架）
- [ ] `X-Tenant-ID` header 強制附帶（V3.0）
