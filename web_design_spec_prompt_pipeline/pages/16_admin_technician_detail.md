# Page-Level Prompt: 技師詳細管理（排班 / 技能 / 結算 三子頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 技師詳細管理涵蓋 V2.0 新增的三大子頁面：排班管理、技能與認證、結算明細，為派工引擎的可用性計算、硬性匹配條件與月度薪酬發放的核心資料基礎。

---

## [PAGE META]

- **page_name**: 技師詳細管理 Technician Detail Management
- **route_path**: `/admin/technicians/[id]/schedule` | `/admin/technicians/[id]/skills` | `/admin/technicians/[id]/settlements`
- **page_type**: tabbed_multi_page（技師詳情 Header + Tab 子導覽 + 各子頁面內容）
- **primary_goal**: 提供單一技師的深度管理介面，涵蓋可用時段編排、技能認證維護、薪酬結算簽核，是派工引擎之可用性、硬性過濾、分潤計算三大核心資料的唯一真實來源
- **secondary_goal**: 確保認證到期預警、排班衝突偵測、結算雙簽流程之合規性與稽核追溯
- **target_users**:
  - 主要：平台管理員（排班/技能 CRUD、結算第一關簽核）
  - 次要：財務主管（結算第二關放款確認）、技師本人（T4/T10 只讀檢視）
- **entry_point**: 技師管理列表 `/technicians` → 點擊技師名稱 → 詳情頁頂部 Tab 切換 / Dashboard 認證到期警示卡片 / 結算排程任務郵件連結
- **expected_time_on_page**: 排班 2-5 分鐘 / 技能 3-8 分鐘 / 結算 5-15 分鐘（簽核時）

---

## [STRUCTURE: SECTIONS]

### 共用結構

1. **page_shell**
   - section_type: layout_shell
   - section_purpose: 技師資訊 Header + 頂部 Tab 子導覽 + 內容區佈局

2. **technician_header**
   - section_type: context_header
   - section_purpose: 顯示當前編輯對象的身份資訊，提供跨子頁面的操作上下文一致性

3. **sub_tabs**
   - section_type: tab_navigation
   - section_purpose: 三個子頁面切換（排班 / 技能 / 結算），URL 路由同步

### 子頁面 A25 — 技師排班 `/admin/technicians/[id]/schedule`

4. **view_toolbar**
   - section_type: toolbar
   - section_purpose: 月/週視圖切換、週次選擇器、規則管理入口、匯出 PDF 按鈕

5. **schedule_calendar**
   - section_type: interactive_calendar
   - section_purpose: 核心排班編輯器，支援拖放批次選時段、衝突警示、最大連續工時檢查

6. **rule_panel**
   - section_type: side_panel
   - section_purpose: 定期規則（每週六休）+ 一次性規則（國定假日）管理

7. **leave_request_queue**
   - section_type: compact_list
   - section_purpose: 技師透過 T10 申請的休假，待管理員審核

### 子頁面 A26 — 技師技能 `/admin/technicians/[id]/skills`

8. **skill_summary_bar**
   - section_type: stats_strip
   - section_purpose: 總技能數、即將到期、已過期、內訓完成度摘要

9. **skill_matrix_table**
   - section_type: editable_table
   - section_purpose: 品牌授權、型號範圍、熟練等級、證書編號、到期管理

10. **certificate_upload_panel**
    - section_type: upload_zone
    - section_purpose: 證書 PDF/JPG 上傳與縮圖預覽

11. **training_progress_card**
    - section_type: progress_card
    - section_purpose: 平台內訓完成度顯示

### 子頁面 A27 — 技師結算 `/admin/technicians/[id]/settlements`

12. **settlement_period_selector**
    - section_type: period_navigator
    - section_purpose: 結算月份切換、年度下拉、狀態篩選

13. **settlement_summary_card**
    - section_type: info_card
    - section_purpose: 當月結算摘要（分潤、獎勵、扣款、墊付、實發）

14. **settlement_breakdown_tabs**
    - section_type: tabbed_detail
    - section_purpose: 收入明細 / 獎勵明細 / 扣款明細 / 墊付明細 四個 Tab

15. **approval_workflow_card**
    - section_type: stepper_card
    - section_purpose: 雙簽流程視覺化（Admin 確認 → Finance 放款）

16. **settlement_actions_bar**
    - section_type: action_bar
    - section_purpose: 匯出 PDF、傳送技師確認、標記已放款

---

## [SECTION COMPONENT SPEC]

### Section: page_shell

- **layout**: 全寬容器，`flex flex-col min-h-screen bg-[#F8FAFC]`，Header 固定在頂部，內容區 `flex-1 p-6`
- **elements**:
  - breadcrumb: Breadcrumb / required / "技師管理 > {technician_name} > {子頁面名稱}" / 每層可點擊
  - header_container: Section / required / `bg-white border-b border-gray-200 px-6 py-4 sticky top-16 z-10`
  - tabs_container: Section / required / `bg-white border-b border-gray-200 px-6`
  - content_container: Main / required / `flex-1 p-6`
- **states**:
  - default: 三區塊正常顯示
  - loading: header 與 tabs 正常顯示 + 內容區 Skeleton
  - technician_not_found: 整頁顯示 "找不到此技師 #{id}" + 返回列表按鈕

### Section: technician_header

- **layout**: 水平卡片，`flex items-center gap-4 py-2`
- **elements**:
  - back_btn: IconButton / required / icon: ArrowLeft / 返回 `/technicians` 列表
  - avatar: Avatar / required / 48×48px 圓形 / 無頭像顯示姓名首字
  - name: H2 / required / 技師姓名 / `text-xl font-semibold text-[#1E293B]`
  - tech_id: Text Caption / required / "ID: {id}" / `font-mono text-gray-500`
  - availability_badge: StatusBadge / required / 即時可用狀態（available/busy/offline 色碼同 `08_admin_technicians.md`）
  - phone: Link / required / icon: Phone / 電話，可點擊 `tel:`
  - profile_link: Button Ghost / required / icon: User / "基本資料" / 跳轉 `/technicians/[id]`
- **states**:
  - default: 顯示所有資訊
  - loading: avatar + 姓名 Skeleton，其他欄位延遲載入
  - websocket_update: availability_badge 收到 WS 事件時 0.3s 淡入淡出動畫
- **copy_constraints**: 技師姓名最多 20 字元，超出 truncate + Tooltip

### Section: sub_tabs

- **layout**: 水平 Tab 列，`flex items-center gap-0 border-b`，每個 Tab `px-4 py-3`
- **elements**:
  - tab_schedule: TabItem / required / icon: Calendar / "排班管理" / 路由 `/admin/technicians/[id]/schedule`
  - tab_skills: TabItem / required / icon: Award / "技能與認證" / 路由 `/admin/technicians/[id]/skills` / 有即將到期認證時顯示琥珀色 Dot
  - tab_settlements: TabItem / required / icon: DollarSign / "結算明細" / 路由 `/admin/technicians/[id]/settlements` / 有待簽核月結算時顯示紅色 Badge
- **states**:
  - active: 當前子頁面 `text-[#2563EB] border-b-2 border-[#2563EB] font-medium`
  - inactive: `text-gray-600 hover:text-gray-900 hover:bg-gray-50`
  - badge: 紅色待簽核 Badge `absolute -top-1 -right-2 min-w-[18px] h-[18px] bg-red-500 text-white text-xs rounded-full flex items-center justify-center`
  - dot: 琥珀色點 `w-2 h-2 bg-amber-500 rounded-full absolute top-2 right-2`
- **copy_constraints**: Tab 文案固定，不可修改

---

### 子頁面 A25: 技師排班 `/admin/technicians/[id]/schedule`

### Section: view_toolbar

- **layout**: 全寬工具列，`flex items-center justify-between gap-3 mb-4`
- **elements**:
  - view_mode_toggle: SegmentedControl / required / 選項：月視圖 / 週視圖 / 預設週視圖
  - date_navigator: DateRangeNavigator / required / 左右箭頭 + 當前週/月顯示 + "今日" 按鈕
    - 週視圖：顯示 "2026/04/20 - 2026/04/26"
    - 月視圖：顯示 "2026 年 4 月"
  - max_hours_indicator: ChipIndicator / required / "連續工時上限 10 hr" / `bg-blue-50 text-blue-700 text-xs rounded-full px-3 py-1` / 設定可透過 Popover 編輯（6-14 小時範圍）
  - manage_rules_btn: Button Secondary / required / icon: Settings / "規則管理" / 開啟 rule_panel Sheet
  - export_pdf_btn: Button Ghost / required / icon: FileDown / "匯出月班表" / 僅月視圖啟用
  - save_btn: Button Primary / required / "儲存排班" / 有變更時啟用，無變更時 disabled
- **states**:
  - default: 全部 enabled
  - dirty: save_btn 亮起 + 旁邊顯示 "未儲存" amber Badge `bg-amber-100 text-amber-700 text-xs rounded-full px-2 py-0.5`
  - saving: save_btn Spinner + "儲存中..."
  - exporting: export_pdf_btn Spinner + 鎖定按鈕 3 秒
- **copy_constraints**: 無

### Section: schedule_calendar

- **layout**: 全寬互動日曆，`bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - legend: ColorLegend / required / 水平色碼圖例 `flex gap-4 mb-3`
    - regular（一般班）：`bg-blue-100 border-blue-300 text-blue-700` 方塊 + "一般班"
    - on_call（備勤）：`bg-purple-100 border-purple-300 text-purple-700` 方塊 + "備勤"
    - overtime（加班）：`bg-orange-100 border-orange-300 text-orange-700` 方塊 + "加班"
    - leave（請假）：`bg-gray-200 border-gray-400 text-gray-500` 斜線圖案 + "請假"
    - holiday（國定假日）：`bg-red-50 border-red-200 text-red-700` 方塊 + "假日"
    - conflict（衝突）：`bg-red-100 border-red-500 border-2` 方塊 + "衝突"
  - week_grid: Grid / required / 週視圖：7 欄（週一至週日）× 14 小時列（07:00-21:00，每格 1 小時）
    - 欄標題：日期 + 星期，今日欄頂部加上 `bg-blue-50 text-[#2563EB] font-semibold`
    - 時段格：預設 `bg-gray-50 border border-gray-200 hover:bg-blue-50 cursor-pointer`
    - 已填格：依 schedule_type 填色
    - 選取中（拖放）：`ring-2 ring-[#2563EB] bg-blue-100`
    - 既有工單時段：疊加半透明 icon: Briefcase + Tooltip "已派工單 #WO-xxxx"，此時無法排「請假」（衝突警示）
  - month_grid: Grid / conditional / 月視圖：6×7 格子（每日一格），每格顯示：
    - 日期數字 H4
    - 該日時段類型摘要（如 "一般 09-18" / "請假" / "加班 18-22"）
    - 該日總工時色碼：
      - 0 hr：灰色 `text-gray-400`
      - 1-8 hr：黑字
      - 9-10 hr：`text-amber-600`
      - >10 hr：`text-red-600 font-bold` + 警示 icon: AlertTriangle
  - drag_selection_tooltip: Tooltip / required / 拖放時顯示 "已選取 {count} 個時段 ({start} - {end})"
  - time_slot_popover: Popover / required / 點擊時段格彈出小選單：
    - "設為一般班" / icon: Briefcase
    - "設為備勤" / icon: Phone
    - "設為加班" / icon: Clock
    - "設為請假" / icon: Plane
    - "清除" / icon: X / 紅字（僅已填時顯示）
  - conflict_warning_banner: AlertBanner / conditional / 有衝突時顯示於網格上方
    - 內容："偵測到 {count} 個排班衝突" + 衝突清單（工單編號 + 時段）
    - 色碼：`bg-red-50 border-red-200 text-red-700 rounded-lg p-3 mb-4`
    - 動作按鈕："查看衝突" 跳至第一個衝突格 + "強制覆寫"（需二次確認）
  - consecutive_hours_warning: InlineBadge / conditional / 當連續排班 >10 小時時，該連續區塊右上角顯示
    - 內容：icon: AlertTriangle + "{n}h 連續"
    - 色碼：`bg-red-500 text-white text-xs rounded-full px-2 py-0.5`
- **states**:
  - default: 顯示當週/當月排班，既有資料填色
  - empty: 新技師無排班時，整個網格顯示「套用預設排班」CTA + 預覽（Mon-Fri 09-18 / Sat 10-17 / Sun off）
  - drag_selecting: 拖放中游標 `cursor-crosshair`，選取區塊 `ring-2 ring-[#2563EB]`，顯示 drag_selection_tooltip
  - popover_open: 點擊時段後顯示 time_slot_popover
  - conflict_detected: 衝突時段格 `bg-red-100 border-red-500 border-2` + 紅色 AlertTriangle icon
  - loading: 整個網格 Skeleton（7×14 灰色方塊）
  - saving: 網格鎖定 + 中央 Spinner + "儲存中..."
  - websocket_conflict: 其他管理員同時編輯時，顯示 Toast "此排班已被其他管理員更新，已自動同步最新資料" + refetch
- **copy_constraints**: 時段格內文字最多 4 字元

### Section: rule_panel

- **layout**: Sheet 側滑面板，`w-96 bg-white shadow-xl` 從右側滑入
- **elements**:
  - panel_title: H3 / required / "排班規則管理"
  - close_btn: IconButton / required / icon: X / 右上角
  - rules_tabs: Tabs / required / 兩個 Tab：
    - tab_recurring: "定期規則" / 每週固定模式（如每週六休）
    - tab_one_time: "一次性規則" / 國定假日、特殊日期
  - recurring_rule_list: List / required / 每條規則一列：
    - day_of_week: Badge / required / "週六" / `bg-gray-100`
    - time_range: Text / required / "全天" 或 "09:00-12:00"
    - schedule_type: Badge / required / 類型色碼同 legend
    - delete_btn: IconButton / required / icon: Trash / 紅色
  - add_recurring_btn: Button Primary / required / icon: Plus / "新增定期規則"
  - add_recurring_form: Form / conditional / 展開表單：
    - day_selector: MultiSelect / required / "週一 週二 ... 週日"（可多選）
    - time_from: TimePicker / required / "起始時間"
    - time_to: TimePicker / required / "結束時間"
    - type_select: Select / required / regular / on_call / overtime / leave
    - confirm_btn: Button Primary / "加入規則"
  - one_time_rule_list: List / required / 每條一次性規則一列：
    - date: Text / required / "2026/05/01（勞動節）"
    - time_range: Text / required / "全天"
    - type: Badge / required / holiday
    - delete_btn: IconButton / required / icon: Trash
  - add_one_time_btn: Button Primary / required / icon: Plus / "新增一次性規則"
  - add_one_time_form: Form / conditional /
    - date_picker: DatePicker / required / "日期"
    - time_from: TimePicker / optional / "起始時間（留空=全天）"
    - time_to: TimePicker / optional / "結束時間"
    - type_select: Select / required / holiday / leave / extra / blocked
    - reason: Textarea / required / "備註原因" / 最少 5 字
    - confirm_btn: Button Primary / "加入規則"
  - apply_btn: Button Primary / required / "套用規則至排班" / 底部粘黏 / 套用後規則自動填入 schedule_calendar
- **states**:
  - default: 顯示現有規則列表
  - empty: "尚無 {類型} 規則" + CTA
  - adding: 表單展開，其他規則半透明 `opacity-50`
  - applying: apply_btn Spinner + "套用中..."
  - validation_error: 時段重疊時行內顯示 "與既有規則衝突"
- **copy_constraints**: 規則備註最多 100 字元

### Section: leave_request_queue

- **layout**: 緊湊卡片列表，`bg-white rounded-xl shadow-sm border border-gray-200 p-4 mt-4`
- **elements**:
  - section_title: H4 / required / "休假申請" + Badge 待處理數量 `bg-amber-100 text-amber-700`
  - request_cards: Card[] / required / 每筆申請一張卡片：
    - date_range: Text / required / "2026/05/10 - 2026/05/12（3 天）"
    - reason: Text Body SM / required / 申請原因（如 "家庭事務"）
    - submitted_at: Text Caption / required / "提交於 2 天前"
    - approve_btn: Button Primary Small / required / "核准" / 核准後自動寫入 day_override
    - reject_btn: Button Ghost Small / required / "駁回" / 需填寫駁回原因
- **states**:
  - default: 顯示待處理申請
  - empty: "目前無休假申請" + icon: CheckCircle 綠色
  - approving: 按鈕 Spinner
  - collapsed: 無申請時整個 Section 不顯示
- **copy_constraints**: 駁回原因最多 200 字元

---

### 子頁面 A26: 技師技能與認證 `/admin/technicians/[id]/skills`

### Section: skill_summary_bar

- **layout**: 水平統計列，`grid grid-cols-4 gap-4 mb-6`
- **elements**:
  - total_skills_card: StatCard / required / "技能總數" + 數字 / `bg-blue-50 text-blue-700`
  - expiring_soon_card: StatCard / required / "30 天內到期" + 數字 / `bg-amber-50 text-amber-700` / 數量 > 0 時 `animate-pulse`
  - expired_card: StatCard / required / "已過期" + 數字 / `bg-red-50 text-red-700` / 點擊可跳至篩選已過期
  - training_completion_card: StatCard / required / "內訓完成度" + 百分比 + 進度條 / 色碼：<50% 紅 / 50-80% 琥珀 / >80% 綠
- **states**:
  - default: 顯示所有統計
  - loading: 四張卡片 Skeleton
- **copy_constraints**: 標籤固定

### Section: skill_matrix_table

- **layout**: 全寬 DataTable，`bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - toolbar: Toolbar / required / `flex justify-between items-center mb-4`
    - search_input: Input / required / icon: Search / placeholder: "搜尋品牌或型號..." / debounce 300ms
    - status_filter: Select / required / 全部 / 有效 / 30 天內到期 / 已過期
    - brand_filter: Multi-Select / optional / 品牌篩選（Dormakaba / Yale / Hafele / Chatlock / Philips ...）
    - add_skill_btn: Button Primary / required / icon: Plus / "新增技能認證"
  - skill_table: DataTable / required / 欄位如下：
    - col_brand: Text / required / 品牌名稱
    - col_model_scope: Text / required / 型號範圍（"全線" 或 "DP850, DP900" 等）
    - col_proficiency_level: LevelBadge / required / 熟練等級
      - L1 一般維修：`bg-gray-100 text-gray-700` "L1"
      - L2 電子鎖：`bg-blue-100 text-blue-700` "L2"
      - L3 保險箱/門禁整合：`bg-purple-100 text-purple-700` "L3"
      - 點擊可展開下拉變更等級（僅管理員有權限）
    - col_cert_id: Text Code / required / 證書編號 / `font-mono text-gray-600`
    - col_issued_at: Text / required / 取得日期 yyyy/MM/dd
    - col_expires_at: Text / required / 到期日期 yyyy/MM/dd（永久時顯示 "永久"）
    - col_days_remaining: DaysCounter / required /
      - 永久：`text-gray-500` "—"
      - >90 天：`text-green-600` "{n} 天"
      - 31-90 天：`text-amber-600` "{n} 天"
      - 1-30 天：`text-red-600 font-bold` "{n} 天" + icon: AlertTriangle
      - ≤0 天：`text-red-600 font-bold` "已過期 {n} 天"
    - col_status: StatusBadge / required /
      - valid：`bg-green-100 text-green-700` "有效"
      - expiring_soon：`bg-amber-100 text-amber-700` "即將到期"
      - expired：`bg-red-100 text-red-700` "已過期"
    - col_certificate: CertificateThumbnail / required / 證書檔案縮圖（40×40px）+ 點擊開啟 Lightbox / 無檔案顯示 "未上傳" 灰字 + Upload icon
    - col_actions: ActionButtons / required /
      - "編輯" icon: Pencil / 開啟編輯 Modal
      - "續約" icon: RefreshCw / 僅即將到期/已過期時顯示
      - "刪除" icon: Trash / 紅色 / 需二次確認 + 寫入 audit-events
  - add_skill_modal: Dialog / required / shadcn/ui `<Dialog>`
    - title: "新增技師技能認證"
    - brand_select: Select / required / 動態載入品牌清單 / 搜尋功能
    - model_scope_input: TagInput / required / "型號範圍" / 可輸入多個型號 + "全線" 單選開關
    - proficiency_select: Select / required / L1 / L2 / L3 / 說明 Tooltip
    - cert_id_input: Input / required / "證書編號" / 重複驗證
    - issued_at_picker: DatePicker / required / "取得日期"
    - expires_at_picker: DatePicker / required / "到期日期" / "永久" checkbox 可關閉日期
    - certificate_upload: FileUpload / required / "證書檔案 (PDF/JPG)" / 最大 5MB
    - confirm_btn: Button Primary / "儲存" / 驗證通過才啟用
    - cancel_btn: Button Ghost / "取消"
  - certificate_lightbox: Lightbox / required /
    - PDF 用 `<embed>` 或 PDF.js 預覽
    - JPG/PNG 直接顯示，支援縮放
    - 下載原檔按鈕
    - 上傳時間標記
- **states**:
  - default: 顯示技能列表，有效排最前，依 days_remaining 升序
  - hover: 整列 `bg-blue-50`（即將到期列 hover `bg-amber-50`，已過期列 hover `bg-red-50`）
  - expiring_warning: 即將到期（≤30 天）整列左邊界 `border-l-4 border-amber-500`
  - expired_warning: 已過期整列背景 `bg-red-50` + 文字刪除線 `line-through decoration-red-500`
  - loading: 8 列 Skeleton
  - empty: "尚未登錄任何技能認證" + "新增技能認證" CTA
  - uploading: 證書欄位 Progress bar + "上傳中... {percent}%"
  - audit_logged: 每次變更顯示 Toast "技能變更已記錄稽核（event_id: {id}）"
- **copy_constraints**: 品牌最多 30 字元，型號最多 50 字元，證書編號最多 40 字元

### Section: certificate_upload_panel

- **layout**: 獨立上傳區塊（僅在無證書時顯示），`border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-[#2563EB] transition-colors`
- **elements**:
  - upload_icon: Icon / required / icon: Upload / 48×48px 灰色
  - instruction_text: Text Body / required / "拖放證書檔案至此，或點擊選擇檔案"
  - format_caption: Text Caption / required / "支援 PDF / JPG / PNG，單檔最大 5MB"
  - browse_btn: Button Secondary / required / "選擇檔案"
- **states**:
  - default: 虛線邊框
  - drag_over: `border-[#2563EB] bg-blue-50`
  - uploading: 顯示進度條 + 檔名 + 百分比
  - success: 綠色 check icon + "上傳成功" 2 秒後淡出
  - error: 紅色 X icon + 錯誤訊息（檔案過大/格式不支援）
- **copy_constraints**: 指示文案固定

### Section: training_progress_card

- **layout**: 獨立卡片，`bg-white rounded-xl shadow-sm border border-gray-200 p-6 mt-6`
- **elements**:
  - card_title: H4 / required / "平台內訓進度"
  - overall_progress: ProgressBar Large / required / 整體完成度進度條 + 百分比
  - course_list: List / required / 每個內訓課程一列：
    - course_name: Text / required / 課程名稱
    - status: Badge / required /
      - completed：`bg-green-100 text-green-700` "已完成" + 完成日期
      - in_progress：`bg-blue-100 text-blue-700` "進行中 {n}%"
      - not_started：`bg-gray-100 text-gray-500` "未開始"
    - required: Tag / optional / 必修課程 `bg-red-100 text-red-700 text-xs` "必修"
  - send_reminder_btn: Button Secondary / optional / icon: Bell / "寄送提醒" / 僅有未完成必修課程時顯示
- **states**:
  - default: 顯示所有課程
  - loading: Skeleton
  - empty: "此技師尚未指派任何內訓課程" + icon: BookOpen
  - reminding: 按鈕 Spinner + "寄送中..."
- **copy_constraints**: 課程名稱最多 40 字元

---

### 子頁面 A27: 技師結算明細 `/admin/technicians/[id]/settlements`

### Section: settlement_period_selector

- **layout**: 水平工具列，`flex items-center justify-between gap-3 mb-6`
- **elements**:
  - year_select: Select / required / 年度下拉（近 3 年）
  - month_list: PillList / required / 12 個月份 Pill，每個 Pill 顯示：
    - 月份數字："4 月"
    - 狀態點色碼：
      - draft（草稿）：`bg-gray-300` 灰點
      - confirmed（已確認）：`bg-blue-500` 藍點
      - paid（已放款）：`bg-green-500` 綠點
      - 當月選中：`ring-2 ring-[#2563EB] bg-blue-50 text-[#2563EB] font-semibold`
  - status_filter: Select / optional / 全部 / 待確認 / 待放款 / 已放款
  - period_type_badge: Badge / required / 顯示結算週期類型："月結" / "雙週結" / "週結" / `bg-gray-100 text-gray-600 text-xs rounded-full px-2 py-1`
- **states**:
  - default: 預設選中上個月
  - loading: 月份 Pills Skeleton
  - empty_month: 選中月份無結算資料時，顯示 "本月尚無結算單" + "生成結算單" 按鈕（僅當月已結束時顯示）
- **copy_constraints**: 月份固定格式 "M 月"

### Section: settlement_summary_card

- **layout**: 大型卡片，`bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6`
- **elements**:
  - period_title: H3 / required / "{yyyy} 年 {MM} 月結算單"
  - settlement_id: Text Caption / required / "單號：SETT-{yyyy}{MM}-{tech_id}" / `font-mono`
  - status_badge: StatusBadge Large / required /
    - draft：`bg-gray-100 text-gray-700` "草稿"
    - confirmed：`bg-blue-100 text-blue-700` "已確認，待放款"
    - paid：`bg-green-100 text-green-700` "已放款"
  - summary_grid: Grid / required / 5 行摘要，`grid grid-cols-[200px_1fr_100px] gap-2`：
    - row_commission: Row / required / "工單分潤" + 明細連結（"詳見 收入明細"） + "NT$ 37,800" / `font-mono text-right`
    - row_bonus: Row / required / "獎勵加總" + Tooltip（"高評分 ×2, 快速完工 ×1"）+ "+NT$ 200" / `text-green-600`
    - row_penalty: Row / required / "扣款加總" + Tooltip（"返工 ×1"）+ "-NT$ 500" / `text-red-600`
    - row_advance: Row / required / "墊付結算" + Tooltip（"零件墊付 2 筆"）+ "+NT$ 300" / `text-blue-600`
    - divider: HR / required / `border-t border-gray-300 my-2`
    - row_net: Row / required / "實發金額" / H2 bold / "NT$ 37,800" / `text-2xl font-bold text-[#2563EB]`
  - meta_info: Grid / required / `grid grid-cols-3 gap-4 mt-4 text-sm text-gray-600`
    - total_orders: "完成工單：{count} 單"
    - gross_amount: "總收入：NT$ {amount}"
    - pricing_rule_link: Link / "分潤率依據 → {tenant_plan}" / 跳轉 `tenants.pricing_rules` 設定頁
  - next_settlement_date: Text Caption / required / "下次結算日：{yyyy/MM/dd}"
  - paid_info: Text Caption / conditional / 已放款時顯示 "放款日：{date} / 匯款單號：{ref}"
- **states**:
  - default: 顯示完整摘要
  - loading: 所有金額 Skeleton
  - draft_editable: 草稿狀態時，各項金額旁出現 icon: Pencil 可點擊調整
  - confirmed_locked: 已確認後所有金額 disabled，無法編輯
- **copy_constraints**: 金額統一 "NT$ " 前綴 + 千分位逗號

### Section: settlement_breakdown_tabs

- **layout**: Tabs 切換 + DataTable，`bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- **elements**:
  - tabs_header: TabsList / required / 4 個 Tab：
    - tab_income: "收入明細" + Badge 工單數
    - tab_bonus: "獎勵明細" + Badge 筆數 / 色 `bg-green-100 text-green-700`
    - tab_penalty: "扣款明細" + Badge 筆數 / 色 `bg-red-100 text-red-700`
    - tab_advance: "墊付明細" + Badge 筆數 / 色 `bg-blue-100 text-blue-700`
  - income_table: DataTable / required / 工單收入：
    - col_order_id: Link / required / 工單編號 / 可點擊跳轉 `/work-orders/[id]`
    - col_completed_at: Text / required / 完工日期 yyyy/MM/dd HH:mm
    - col_service_type: Badge / required / 服務類型：一般維修 / 安裝 / 代工 / 保固 / 緊急
    - col_gross: Text Number / required / 工單總價 "NT$ {amount}" / `text-right`
    - col_rate: Text / required / 分潤率 "{n}%" / Tooltip 說明來自 `tenants.pricing_rules`
    - col_commission: Text Number / required / 分潤金額 "NT$ {amount}" / `font-medium text-right`
  - bonus_table: DataTable / required / 獎勵明細：
    - col_date: Text / required / 日期
    - col_type: TypeBadge / required / bonus_rating / bonus_speed / bonus_weekend / bonus_night
    - col_related_order: Link / required / 關聯工單編號 / 可追溯到單一工單
    - col_description: Text / required / 獎勵原因（"單次評分 5.0" / "工時 < 70% 預估"）
    - col_amount: Text Number / required / "+NT$ {amount}" / `text-green-600 font-medium`
  - penalty_table: DataTable / required / 扣款明細：
    - col_date: Text / required / 日期
    - col_type: TypeBadge / required / penalty_rework / penalty_complaint / penalty_no_show
    - col_related_order: Link / required / 關聯工單編號
    - col_description: Text / required / 扣款原因（"7 天內返工" / "有效客訴 #COMP-xxx"）
    - col_amount: Text Number / required / "-NT$ {amount}" / `text-red-600 font-medium`
  - advance_table: DataTable / required / 墊付明細：
    - col_date: Text / required / 日期
    - col_description: Text / required / 墊付項目（"零件費 Yale YDM-7116 鎖芯"）
    - col_receipt_thumbnail: ImageThumbnail / required / 單據照片縮圖 / 點擊開啟 Lightbox
    - col_amount: Text Number / required / "+NT$ {amount}" / `text-blue-600 font-medium`
  - subtotal_row: Row / required / 每個 Table 底部固定顯示小計 / `bg-gray-50 font-bold`
- **states**:
  - default: 顯示 tab_income
  - loading: Tab 切換時 Skeleton rows
  - empty: 個別 Tab 無資料時顯示 "本月無 {類型} 紀錄"
  - hover: 整列 `bg-blue-50`
- **copy_constraints**: 描述最多 60 字元，超出 truncate + Tooltip

### Section: approval_workflow_card

- **layout**: 步驟卡片，`bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6`
- **elements**:
  - card_title: H4 / required / "簽核流程"
  - workflow_stepper: Stepper / required / 水平 3 步驟：
    - step_1_draft: Step / required /
      - title: "草稿"
      - timestamp: "由系統於 {date} 生成"
      - state: completed（起始狀態即完成）`bg-gray-500`
    - step_2_admin: Step / required /
      - title: "管理員確認"
      - actor: 顯示確認者 Avatar + 名字（已確認時） / "待確認" （未）
      - timestamp: 確認時間 / "—"
      - state: completed `bg-green-500` / in_progress `bg-amber-400 animate-pulse` / pending `bg-gray-200`
      - action_btn: Button Primary / required / "確認結算" / 僅當前步驟且有權限顯示
    - step_3_finance: Step / required /
      - title: "財務放款"
      - actor: 放款者 Avatar + 名字（已放款時）
      - timestamp: 放款時間 / 預計放款日
      - state: completed `bg-green-500` / pending `bg-gray-200`
      - action_btn: Button Primary / required / "確認放款" / 僅 Finance 角色 + 當前步驟時顯示
  - connector_line: Line / required / 步驟間連接線，完成 `bg-green-300`，未完成 `bg-gray-200`
  - audit_link: Link / required / "查看稽核紀錄" / 跳轉 `/admin/audit-events?resource=settlement_{id}`
  - admin_confirm_modal: Dialog / required / 管理員確認時彈出：
    - title: "確認結算 — {period}"
    - summary_preview: 結算摘要（實發金額、工單數）
    - notes: Textarea / required / "確認備註" / 最少 10 字
    - checkbox: Checkbox / required / "我已核對分潤比例、獎懲明細均正確無誤"
    - confirm_btn: Button Primary / "確認並送交財務" / checkbox 勾選後啟用
    - cancel_btn: Button Ghost / "取消"
  - finance_pay_modal: Dialog / required / 財務放款時彈出：
    - title: "放款確認 — {period}"
    - net_amount: H3 / "實發金額：NT$ {amount}" / 大字
    - payment_ref_input: Input / required / "匯款單號" / 格式驗證
    - paid_at_picker: DatePicker / required / "匯款日期" / 預設今日
    - bank_info: Text Caption / required / 顯示技師銀行資訊（遮罩顯示末 4 碼）
    - confirm_btn: Button Primary / "標記已放款"
    - cancel_btn: Button Ghost / "取消"
- **states**:
  - draft: step 1 完成，step 2 in_progress，step 3 pending
  - confirmed: step 1&2 完成，step 3 in_progress，action_btn 出現在 step 3
  - paid: 全部 completed，顯示 "已完成放款" 綠底橫條
  - permission_denied: 當前使用者無對應角色時，action_btn disabled + Tooltip "僅 {role} 角色可執行此步驟"
  - confirming: 確認按鈕 Spinner + "處理中..."
  - error: Toast "簽核失敗：{reason}"
- **copy_constraints**: 備註最多 500 字元，匯款單號最多 30 字元

### Section: settlement_actions_bar

- **layout**: 全寬固定在頁面底部，`sticky bottom-0 bg-white border-t border-gray-200 px-6 py-3 flex justify-end gap-3`
- **elements**:
  - export_pdf_btn: Button Secondary / required / icon: FileDown / "匯出 PDF 結算單" / 所有狀態可用
  - send_to_technician_btn: Button Secondary / conditional / icon: Send / "傳送技師確認" / 僅 confirmed 狀態顯示
  - regenerate_btn: Button Ghost / conditional / icon: RefreshCw / "重新生成" / 僅 draft 狀態 + 有權限者顯示 / 需二次確認
  - back_to_list_btn: Button Ghost / optional / icon: ArrowLeft / "返回結算列表"
- **states**:
  - default: 依結算狀態顯示對應按鈕
  - exporting: export_pdf_btn Spinner + "產生 PDF 中..." / 完成後自動下載
  - sending: send_to_technician_btn Spinner + "傳送中..."
  - regenerating: 彈出確認 Modal + "重新生成將清空當前資料並重算，確認？"
- **copy_constraints**: 無

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### A25 技師排班
1. 進入頁面 → `GET /api/v1/technicians/{id}/schedule?week_start={iso}` → 渲染 week_grid
2. 拖放選取時段 → mousedown 起點 → mousemove 擴展選取 → mouseup 結束 → 彈出 time_slot_popover 選類型 → Optimistic update grid 色碼 → dirty state
3. 點擊「儲存排班」→ `PUT /api/v1/technicians/{id}/schedule` body: `{ week_start, slots: [...], overrides: [...] }`
4. 後端檢查衝突（既有工單）→ 回傳 409 + 衝突清單 → 前端顯示 conflict_warning_banner + 標紅格子
5. 成功儲存 → 後端推播事件 `dispatch.schedule.updated` → 派工引擎即時生效（避免派工衝突）→ Toast "排班已儲存，派工引擎已同步"
6. 新增定期規則 → 開啟 rule_panel → 填寫表單 → 套用 → 自動批次填入多週相同時段
7. 連續工時 >10 小時 → 即時顯示紅色 consecutive_hours_warning（前端計算，無需 API）
8. 技師休假申請 → 管理員點擊「核准」→ `POST /api/v1/technicians/{id}/schedule/leave` body: `{ request_id, action: "approve" }` → 自動寫入 `technician_day_overrides`
9. 匯出 PDF → `GET /api/v1/technicians/{id}/schedule/export?month={yyyyMM}&format=pdf` → 下載班表（含技師姓名、月份、時段色碼圖例）

#### A26 技師技能
1. 進入頁面 → `GET /api/v1/technicians/{id}/skills` → 渲染 summary_bar + skill_matrix_table
2. 點擊「新增技能認證」→ 開啟 Modal → 填寫表單 → 上傳證書（`POST /api/v1/technicians/{id}/skills/certificate` multipart 回傳 URL）→ 送出 → `PUT /api/v1/technicians/{id}/skills` body: `{ skills: [...] }` → 列表 refetch
3. 修改熟練等級 → 點擊 LevelBadge → 下拉選新等級 → Optimistic update → PUT → 成功靜默 / 失敗 rollback
4. 即將到期（≤30 天）→ 排程任務觸發 → email + 推播通知管理員與技師（發送邏輯於後端 worker）
5. 刪除技能 → 二次確認 Modal → DELETE → 寫入 audit-events（事件類型 `permission_change`）→ Toast "技能已刪除並記錄稽核 #{audit_id}"
6. 點擊證書縮圖 → 開啟 Lightbox → PDF 用 PDF.js 預覽 / 圖片直接縮放 → 可下載原檔
7. 派工引擎呼叫 `GET /api/v1/technicians/available?skill={brand}:{model}` 時，僅回傳符合硬性過濾條件的技師（技能匹配且未過期）

#### A27 技師結算
1. 進入頁面 → `GET /api/v1/technicians/{id}/settlements?year={y}` → 渲染月份 Pills
2. 選擇月份 → `GET /api/v1/technicians/{id}/settlements/{month}` → 渲染 summary + breakdown
3. 切換 Tab → 同一次查詢回傳完整 breakdown，前端切換顯示，無需重新呼叫
4. 管理員確認 → 點擊「確認結算」→ 開啟 admin_confirm_modal → 填寫備註 → 勾選 checkbox → `POST /api/v1/technicians/{id}/settlements/{month}/confirm` body: `{ notes, confirmed: true }` → 狀態變 `confirmed` → 寫入 audit-events → 推播通知 Finance 角色
5. 財務放款 → 切換至 finance 角色 → 點擊「確認放款」→ 填寫匯款單號 → `POST /api/v1/technicians/{id}/settlements/{month}/pay` body: `{ payment_ref, paid_at }` → 狀態變 `paid` → 寫入 audit-events
6. 匯出 PDF → `GET /api/v1/technicians/{id}/settlements/{month}/export` → Content-Type `application/pdf` → 瀏覽器直接下載
7. PDF 內容：結算單號、技師資訊、期間、完整 breakdown、技師簽名欄位（留白）、雙簽確認欄位、公司印章位置
8. 點擊獎懲明細中的關聯工單 → 跳轉 `/work-orders/[id]` → 可追溯單一來源
9. 技師端 T4 `/account/earnings` 讀取同份 API 但僅只讀顯示（不顯示 action_btn 與簽核步驟的操作按鈕）

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 完整 Header + 水平 Tabs + 三子頁面完整體驗 | 排班週視圖 7×14 完整顯示 / 技能表 9 欄 / 結算摘要 + breakdown 左右並列 |
| Tablet (768-1279px) | Header 精簡（隱藏 phone + profile_link）/ Tabs 水平捲動 | 排班週視圖保留 7 欄但隱藏技師頭像欄 / 技能表隱藏 col_cert_id / 結算 breakdown 改為單欄堆疊 |
| Mobile (<768px) | Header 改為兩行（姓名+狀態一行，其他下拉）/ Tabs 改為 Pill 橫向捲動 | 排班強制切換至月視圖且水平捲動 / 技能改為卡片列表（每技能一張卡） / 結算 summary 全寬 + breakdown Tab 改為 Accordion |

### 資料更新策略

- 排班資料：進入頁面時載入，`staleTime: 60_000`，手動儲存後 invalidate，WebSocket 訂閱 `ws://*/technicians/{id}/schedule` 接收其他管理員的編輯事件
- 技能資料：`staleTime: 120_000`（2 分鐘），CUD 操作後 invalidate，到期檢查由後端排程每日觸發
- 結算資料：`staleTime: 300_000`（5 分鐘），簽核操作後 invalidate
- 技師狀態：WebSocket 推送即時更新 Header 的 availability_badge
- 休假申請：`refetchInterval: 60_000`（1 分鐘自動更新，數量 Badge 即時性）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - **排班管理 (A25)**:
    - GET `/api/v1/technicians/{id}/schedule` — 取得排班資料
      - Query params: `week_start` (ISO date) | `month` (yyyy-MM)
      - Response: `{ recurring: TechnicianSchedule[], overrides: DayOverride[], conflicts: Conflict[], max_continuous_hours: number }`
    - PUT `/api/v1/technicians/{id}/schedule` — 覆寫整週/整月排班
      - Body: `{ week_start, slots: { day, hour, type }[], overrides?: [...] }`
      - Response 409：`{ error: "schedule_conflict", conflicts: [{ work_order_id, time_slot }] }`
    - POST `/api/v1/technicians/{id}/schedule/leave` — 新增/核准休假
      - Body: `{ date_from, date_to, reason, override_type: "leave", approved_by? }`
    - DELETE `/api/v1/technicians/{id}/schedule/leave/{date}` — 取消休假
    - GET `/api/v1/technicians/{id}/schedule/export?month={yyyyMM}&format=pdf` — 匯出月班表 PDF
    - WebSocket `ws://*/technicians/{id}/schedule` — 即時排班變動事件
  - **技能管理 (A26)**:
    - GET `/api/v1/technicians/{id}/skills` — 取得技能列表
      - Response: `{ data: TechnicianSkill[], summary: { total, expiring_soon, expired, training_completion } }`
      - 每筆 TechnicianSkill: `{ id, brand, model_scope, proficiency_level (L1|L2|L3), certification_id, issued_at, expires_at, certificate_url, status }`
    - PUT `/api/v1/technicians/{id}/skills` — 批次更新技能（含新增/修改/刪除）
      - Body: `{ skills: [{ id?, brand, model_scope, proficiency_level, certification_id, issued_at, expires_at }] }`
      - 所有變更自動寫入 `audit-events`，事件類型 `permission_change`
    - POST `/api/v1/technicians/{id}/skills/certificate` — 上傳證書檔案
      - Body: `multipart/form-data` with `file` (PDF/JPG/PNG, max 5MB)
      - Response: `{ certificate_url: string, thumbnail_url: string }`
    - DELETE `/api/v1/technicians/{id}/skills/{skill_id}` — 刪除技能（軟刪除，寫 audit）
    - GET `/api/v1/technicians/available?skill={brand}:{model}&datetime=...` — 派工引擎查詢可用技師（硬性過濾）
  - **結算管理 (A27)**:
    - GET `/api/v1/technicians/{id}/settlements` — 取得結算列表
      - Query params: `year`, `status` (draft|confirmed|paid)
      - Response: `{ data: Settlement[] }` 其中 Settlement: `{ id, period_start, period_end, status, net_amount, pricing_rule_ref }`
    - GET `/api/v1/technicians/{id}/settlements/{month}` — 取得指定月結算詳情
      - Response: `{ summary: {...}, income: Order[], bonuses: Adjustment[], penalties: Adjustment[], advances: Advance[], approval_chain: [{ step, actor, timestamp }] }`
    - POST `/api/v1/technicians/{id}/settlements/{month}/confirm` — Admin 確認結算
      - Body: `{ notes: string, confirmed: true }`
      - 驗證：當前使用者角色必須為 admin，注入 `confirmed_by` + `confirmed_at`，寫入 audit-events
    - POST `/api/v1/technicians/{id}/settlements/{month}/pay` — Finance 放款確認
      - Body: `{ payment_ref: string, paid_at: date }`
      - 驗證：當前使用者角色必須為 finance，前置條件：status = confirmed
    - GET `/api/v1/technicians/{id}/settlements/{month}/export` — 匯出 PDF 結算單
      - Response: `application/pdf`
      - PDF 內含：結算單號、技師資訊、期間摘要、完整 breakdown、技師簽名欄位（留白）、Admin + Finance 雙簽欄位
    - POST `/api/v1/settlements/generate` — 生成月結算單（Admin 排程任務）
      - Body: `{ tenant_id, period_start, period_end, technician_ids?: [] }`
- **Zustand Store**:
  - `useScheduleEditorStore`: 管理排班編輯 dirty state、當前視圖模式（月/週）、拖放選取狀態
  - `useSkillsStore`: 管理技能表篩選、排序、新增/編輯表單狀態
  - `useSettlementStore`: 管理選中月份、Tab 狀態、簽核 Modal 狀態
- **error_cases**:
  - 網路錯誤：Toast "網路連線異常" + TanStack Query 自動重試 3 次
  - 排班衝突（409）：conflict_warning_banner 顯示衝突清單 + 「查看衝突」跳至格子 + 「強制覆寫」二次確認
  - 證書檔案過大（413）：Toast "檔案超過 5MB 限制，請壓縮後重試"
  - 證書格式不支援（415）：Toast "僅支援 PDF / JPG / PNG"
  - 認證編號重複（409）：表單欄位行內顯示 "此證書編號已存在"
  - 權限不足（403）：
    - 排班：Toast "您沒有編輯排班的權限" + 所有編輯按鈕 disabled
    - 技能：同上
    - 結算確認：僅 admin 角色可見 step_2 action_btn
    - 結算放款：僅 finance 角色可見 step_3 action_btn
  - 結算狀態衝突（409）：如嘗試放款未確認的結算 → Toast "此結算尚未由管理員確認，無法放款"
  - 結算已放款不可修改（422）：Toast "已放款結算不可重新生成，請聯繫超管"

---

## [EXCEPTION TO GLOBAL RULES]

- 排班日曆網格在 Desktop 強制使用 7×14 固定尺寸，不受 Global 容器最大寬度限制（必要時水平捲動）
- 拖放選取時段使用全頁 `mousemove` 事件監聽 + `cursor-crosshair`，與 Global 預設指標行為不同
- 證書 Lightbox 使用 PDF.js 渲染 PDF，引入額外 3rd party library，屬於此頁面特例
- 結算 PDF 匯出使用後端伺服器端渲染（`@react-pdf/renderer` 或 Puppeteer），不在前端生成，與 Global 資料匯出策略不同
- 結算 settlement_actions_bar 使用 `sticky bottom-0`，覆蓋 Global footer 位置
- 技能證書縮圖 40×40px 超出 Global DataTable 既定 col 寬度規範，需自訂 col 寬 `w-16`

---

## [ACCEPTANCE CRITERIA]

### 共用
- [ ] 三個子頁面 Tab 切換正確，URL 同步
- [ ] technician_header 在三個子頁面保持一致顯示
- [ ] 每個子頁面具備 loading / error / empty 三態
- [ ] 技師不存在時整頁顯示「找不到此技師」+ 返回按鈕
- [ ] RWD 三斷點佈局正確（Desktop 完整 / Tablet 精簡 / Mobile 堆疊）

### A25 排班管理
- [ ] 月/週視圖切換正常，URL query param 記錄
- [ ] 拖放批次選取時段功能正常，selection tooltip 顯示 count
- [ ] 6 種時段類型色碼正確（regular/on_call/overtime/leave/holiday/conflict）
- [ ] 連續工時 >10 小時即時顯示紅色警示
- [ ] 既有工單時段衝突時顯示 conflict_warning_banner + 紅色邊框格子
- [ ] 定期規則（每週六休）+ 一次性規則（國定假日）管理正常
- [ ] 儲存成功後派工引擎即時同步（WebSocket 事件）
- [ ] 休假申請可核准/駁回，核准後自動寫入 day_overrides
- [ ] 新技師無排班時顯示「套用預設排班」CTA（Mon-Fri 09-18 / Sat 10-17 / Sun off）
- [ ] 月班表 PDF 匯出含技師姓名、月份、時段色碼圖例

### A26 技能與認證
- [ ] 熟練等級三態 Badge 色碼正確（L1 灰 / L2 藍 / L3 紫）
- [ ] 認證狀態三態色碼正確（valid 綠 / expiring_soon ≤30 天琥珀 / expired 紅）
- [ ] 即將到期 30 天內觸發 email + 推播提醒（後端 worker）
- [ ] 證書上傳支援 PDF/JPG/PNG，最大 5MB
- [ ] 證書縮圖點擊開啟 Lightbox，PDF 用 PDF.js 預覽
- [ ] 所有技能變更寫入 audit-events，Toast 顯示 event_id
- [ ] 派工演算法查詢 `/api/v1/technicians/available` 以技能為硬性過濾（不符合條件者不回傳）
- [ ] 內訓完成度進度條色碼正確（<50% 紅 / 50-80% 琥珀 / >80% 綠）
- [ ] 新增技能認證編號重複時行內驗證錯誤

### A27 結算明細
- [ ] 結算週期類型 Badge 顯示正確（月結/雙週結/週結，依 tenant plan）
- [ ] 分潤率依 `tenants.pricing_rules` 取得（一般維修 70% / 安裝 60% / 代工 80% / 保固 100% 工資）
- [ ] 結算摘要 5 行（分潤/獎勵/扣款/墊付/實發）金額正負號色碼正確
- [ ] 獎懲明細每條可追溯關聯工單（Link 可點擊跳轉）
- [ ] 簽核流程 Stepper 三步驟（draft → confirmed → paid）狀態正確
- [ ] 管理員確認 Modal 含備註 + checkbox 核對確認，缺一不可
- [ ] 財務放款 Modal 含匯款單號 + 匯款日期
- [ ] 角色分流：admin 僅可執行 step_2，finance 僅可執行 step_3
- [ ] 嘗試放款未確認結算時顯示「尚未由管理員確認」錯誤
- [ ] PDF 匯出含技師簽名欄位、Admin + Finance 雙簽欄位
- [ ] 每次簽核動作寫入 audit-events
- [ ] 技師端 T4 讀取同 API 但為只讀模式（無 action_btn）

### 效能與規範
- [ ] 各子頁面首次載入 < 2 秒
- [ ] 排班拖放選取延遲 < 50ms（60 FPS 流暢）
- [ ] 證書縮圖採用 lazy loading
- [ ] PDF 匯出 < 5 秒完成（後端渲染）
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）
