# Page-Level Prompt: 進階管理功能（6 個子頁面）

> 對應 `guides/vibe_coding_build_strategy.md` → Step 5。
> 進階管理涵蓋退款審核、庫存管理、保固申請、爭議處理、稽核日誌與權限管理六大子系統，為平台治理與合規的核心功能群。

---

## [PAGE META]

- **page_name**: 進階管理 Advanced Admin
- **route_path**: `/admin/refunds` | `/admin/inventory` | `/admin/warranty-claims` | `/admin/disputes` | `/admin/audit-events` | `/admin/roles`
- **page_type**: tabbed_multi_page（側邊子導覽 + 各子頁面內容）
- **ia_pages**: A17, A18, A19, A20, A21, A22
- **openapi_ops**: submitRefundDecision
- **asyncapi_ops**: subscribeRefundEvents, subscribeDisputeEvents, subscribeLowStockAlerts, subscribeRbacUpdates
- **primary_goal**: 提供平台進階治理功能，涵蓋退款審核、庫存控管、保固追蹤、爭議仲裁、稽核紀錄與角色權限管理
- **secondary_goal**: 確保平台合規、資金安全與營運透明度
- **target_users**:
  - 主要：平台管理員、財務主管、客服主管（依功能分權）
  - 次要：審計人員（稽核日誌）、技術主管（庫存管理）
- **entry_point**: 依 E5x 7.3 節 `adminNavigation` 分屬三個導覽項目入口：「帳務與結算」（退款審核、保固索賠、爭議仲裁）、「庫存」（庫存管理）、「稽核與權限」（稽核日誌、角色權限）/ Dashboard 告警卡片 / 工單詳情頁關聯連結
- **expected_time_on_page**: 依子頁面 3-15 分鐘不等

---

## [STRUCTURE: SECTIONS]

### 共用結構

1. **page_shell**
   - section_type: layout_shell
   - section_purpose: 側邊子導覽 + 右側內容區佈局

2. **sub_navigation**
   - section_type: sidebar_nav
   - section_purpose: 六個子頁面切換導覽
   - **⚠️ E5x 導覽映射**: 本頁 6 個子頁面在 `E5x--frontend-information-arch.md` 7.3 節中分屬 3 個頂級導覽：
     - 「帳務與結算」→ 退款審核 (`/admin/refunds`)、保固索賠 (`/admin/warranty-claims`)、爭議仲裁 (`/admin/disputes`)
     - 「庫存」→ 庫存管理 (`/admin/inventory`)
     - 「稽核與權限」→ 稽核日誌 (`/admin/audit-events`)、角色權限 (`/admin/roles`)

### 子頁面 1 — 退款審核 `/admin/refunds`

3. **refund_queue**
   - section_type: data_table
   - section_purpose: 依 SLA 剩餘時間排序的退款申請佇列

### 子頁面 2 — 庫存管理 `/admin/inventory`

4. **inventory_list**
   - section_type: data_table
   - section_purpose: 物料庫存清單與低庫存警示

### 子頁面 3 — 保固申請 `/admin/warranty-claims`

5. **warranty_claims_list**
   - section_type: data_table
   - section_purpose: 保固申請清單與證據檢視

### 子頁面 4 — 爭議處理 `/admin/disputes`

6. **dispute_cases**
   - section_type: detail_panel
   - section_purpose: 爭議案件列表與雙方證據並列檢視

### 子頁面 5 — 稽核日誌 `/admin/audit-events`

7. **audit_log**
   - section_type: searchable_table
   - section_purpose: 可搜尋的系統操作稽核紀錄

7a. **audit_export_modal**
   - section_type: modal
   - section_purpose: 稽核日誌匯出對話框（CSV / JSON），支援同步下載與大檔異步匯出兩條路徑

### 子頁面 6 — 角色權限 `/admin/roles`

8. **rbac_management**
   - section_type: matrix_editor
   - section_purpose: 角色與權限矩陣管理

---

## [SECTION COMPONENT SPEC]

### Section: page_shell

- **layout**: 左側固定寬度子導覽（`w-56`）+ 右側主內容區（`flex-1`），`flex min-h-screen`
- **elements**:
  - sidebar_container: Aside / required / `w-56 bg-white border-r border-gray-200 py-6 px-3 sticky top-16`（固定於頂部導覽列下方）
  - content_container: Main / required / `flex-1 p-6 bg-[#F8FAFC]`
- **states**:
  - default: 側邊欄展開 + 內容區正常
  - mobile: 側邊欄隱藏，改為頂部 Tab bar

### Section: sub_navigation

- **layout**: 垂直列表，`flex flex-col gap-1`
- **elements**:
  - nav_refunds: NavItem / required / icon: RotateCcw / "退款審核" / 有待審核數量時顯示紅色 Badge
  - nav_inventory: NavItem / required / icon: Package / "庫存管理" / 有低庫存警示時顯示琥珀色 Badge
  - nav_warranty: NavItem / required / icon: Shield / "保固申請"
  - nav_disputes: NavItem / required / icon: Scale / "爭議處理" / 有待處理爭議時顯示紅色 Badge
  - nav_audit: NavItem / required / icon: FileSearch / "稽核日誌"
  - nav_roles: NavItem / required / icon: Users / "角色權限"
- **states**:
  - active: 選中項目 `bg-blue-50 text-[#2563EB] font-medium border-l-2 border-[#2563EB]`
  - inactive: `text-gray-600 hover:bg-gray-50 hover:text-gray-900`
  - badge: 數量 Badge `absolute -right-1 top-0 min-w-[20px] h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center`
- **copy_constraints**: 導覽項目名稱最多 6 字

---

### 子頁面 1: 退款審核 `/admin/refunds`

### Section: refund_queue

- **layout**: 全寬，頂部摘要列 + DataTable
- **elements**:
  - section_title: H2 / required / "退款審核佇列"
  - sla_summary_bar: AlertBar / required / 水平排列三張小卡，`flex gap-4 mb-4`
    - urgent_count: Card / required / "SLA ≤ 2小時" + 數量 / `bg-red-50 border-red-200 text-red-700`
    - warning_count: Card / required / "SLA ≤ 8小時" + 數量 / `bg-amber-50 border-amber-200 text-amber-700`
    - normal_count: Card / required / "SLA > 8小時" + 數量 / `bg-green-50 border-green-200 text-green-700`
  - refund_table: DataTable / required / 預設依 SLA 剩餘時間升序排列：
    - col_refund_id: Text Code / required / 退款編號 / `font-mono`
    - col_work_order: Link / required / 關聯工單編號 / 可點擊跳轉
    - col_amount: Text Number / required / "NT$ {amount}" / 依金額色碼：
      - ≤NT$10,000：正常黑字
      - ≤NT$100,000：`text-amber-600 font-medium`
      - >NT$100,000：`text-red-600 font-bold`
    - col_reason: Text / required / 退款原因 / 最多 50 字元，超出 truncate + Tooltip
    - col_requester: AvatarText / required / 申請人名稱 + 角色 Badge
    - col_approval_chain: ApprovalSteps / required / 視覺化審核步驟
      - 分層審核規則：
        - ≤NT$10,000：經理審核（單層）→ 1 個步驟節點
        - ≤NT$100,000：總監審核（單層）→ 1 個步驟節點
        - >NT$100,000：雙簽審核 → 2 個步驟節點（經理 + 總監）
      - 步驟狀態：待審核 `bg-gray-200` 圓點 / 審核中 `bg-amber-400 animate-pulse` 圓點 / 已通過 `bg-green-500` 勾選 / 已拒絕 `bg-red-500` 叉號
      - 步驟間連接線：完成 `bg-green-300` / 未完成 `bg-gray-200`
    - col_sla_remaining: SLATimer / required / 剩餘時間倒數
      - ≤2 小時：`text-red-600 font-bold animate-pulse`
      - ≤8 小時：`text-amber-600 font-medium`
      - >8 小時：`text-green-600`
    - col_status: StatusBadge / required /
      - 待審核（pending）：`bg-yellow-100 text-yellow-700` "待審核"
      - 審核中（in_review）：`bg-blue-100 text-blue-700` "審核中"
      - 已核准（approved）：`bg-green-100 text-green-700` "已核准"
      - 已拒絕（rejected）：`bg-red-100 text-red-700` "已拒絕"
    - col_actions: ActionButtons / required /
      - "核准" Button Primary Small / 僅有權限者顯示 / 需輸入備註
      - "拒絕" Button Destructive Small / 僅有權限者顯示 / 必須輸入拒絕原因
  - approve_modal: Dialog / required / shadcn/ui `<Dialog>`
    - title: "核准退款 #{refund_id}"
    - amount_display: H3 / "退款金額：NT$ {amount}"
    - approval_level: Text / "審核層級：{經理/總監/雙簽}"
    - notes_input: Textarea / required / "審核備註" / placeholder: "請輸入核准備註..."
    - confirm_btn: Button Primary / "確認核准"
    - cancel_btn: Button Ghost / "取消"
  - reject_modal: Dialog / required /
    - title: "拒絕退款 #{refund_id}"
    - reason_input: Textarea / required / "拒絕原因" / placeholder: "請輸入拒絕原因（必填）..." / 驗證：至少 10 字
    - confirm_btn: Button Destructive / "確認拒絕"
    - cancel_btn: Button Ghost / "取消"
- **states**:
  - default: 依 SLA 升序顯示，SLA ≤ 2小時的列 `bg-red-50`
  - hover: 整列 `bg-blue-50`（紅色警示列 hover 為 `bg-red-100`）
  - loading: SLA 摘要 Skeleton + 8 列 Skeleton rows
  - empty: "目前無待審核退款申請" + icon: CheckCircle
  - error: ErrorState + 重試按鈕
  - approving: 核准按鈕 Spinner + "審核中..."
  - permission_denied: 無權限時操作按鈕 disabled + Tooltip "您的權限不足以審核此金額層級"
- **copy_constraints**: 退款原因最多 200 字元，審核備註最多 500 字元

---

### 子頁面 2: 庫存管理 `/admin/inventory`

### Section: inventory_list

- **layout**: 全寬，頂部搜尋列 + DataTable + 新增庫存 Modal
- **elements**:
  - section_title: H2 / required / "物料庫存管理"
  - inventory_summary: StatCards / required / `flex gap-4 mb-4`
    - total_items: Card / "物料品項" + 數量
    - low_stock_items: Card / "低庫存警示" + 數量 / `bg-amber-50 text-amber-700` / 數量 > 0 時脈動
    - out_of_stock_items: Card / "缺貨品項" + 數量 / `bg-red-50 text-red-700`
  - search_bar: Input / required / icon: Search / placeholder: "搜尋物料名稱或 SKU..." / debounce 300ms
  - category_filter: Select / optional / 物料類別篩選
  - stock_status_filter: Select / optional / 全部 / 正常 / 低庫存 / 缺貨
  - inventory_table: DataTable / required / 欄位如下：
    - col_item_name: Text / required / 物料名稱
    - col_sku: Text Code / required / SKU 編號 / `font-mono text-gray-500`
    - col_current_stock: Text Number / required / 當前庫存數量
      - 正常（> threshold）：黑字
      - 低庫存（> 0 且 ≤ threshold）：`text-amber-600 font-medium` + 琥珀色 Badge "低庫存" `bg-amber-100 text-amber-700 text-xs rounded-full px-2`
      - 缺貨（= 0）：`text-red-600 font-bold` + 紅色 Badge "缺貨" `bg-red-100 text-red-700 text-xs rounded-full px-2`
    - col_threshold: Text Number / required / 安全庫存閾值 / 可行內編輯（點擊變為 Input）
    - col_last_restocked: Text / required / 最後補貨日期 yyyy/MM/dd / 超過 30 天未補貨顯示 `text-gray-400`
    - col_actions: ActionButtons / required /
      - "補貨" Button Primary Small / 開啟 Add Stock Modal
      - "編輯" Button Ghost Small / 編輯物料基本資料
      - "紀錄" Button Ghost Small / 查看庫存異動紀錄
  - add_stock_modal: Dialog / required / shadcn/ui `<Dialog>`
    - title: "補貨 — {item_name}"
    - current_stock_display: Text / "目前庫存：{amount}"
    - add_quantity_input: NumberInput / required / "補貨數量" / min: 1 / 附增減按鈕
    - new_stock_preview: Text / required / "補貨後庫存：{current + add}" / 即時計算
    - supplier_input: Input / optional / "供應商"
    - notes_input: Textarea / optional / "備註"
    - confirm_btn: Button Primary / "確認補貨"
    - cancel_btn: Button Ghost / "取消"
  - add_item_btn: Button Primary / required / icon: Plus / "新增物料" / 置於表格右上方
- **states**:
  - default: 顯示庫存列表，低庫存項目琥珀色 Badge
  - hover: 整列 `bg-blue-50`（低庫存列 hover `bg-amber-50`，缺貨列 hover `bg-red-50`）
  - loading: 摘要卡片 Skeleton + 8 列 Skeleton rows
  - empty: "尚無物料紀錄，請新增物料" + CTA
  - error: ErrorState + 重試按鈕
  - inline_editing: 閾值欄位變為 Input + 確認/取消小按鈕
  - restocking: 補貨 Modal 確認按鈕 Spinner + "處理中..."
- **copy_constraints**: 物料名稱最多 40 字元，SKU 最多 20 字元

---

### 子頁面 3: 保固申請 `/admin/warranty-claims`

### Section: warranty_claims_list

- **layout**: 全寬，頂部篩選列 + DataTable + 證據照片燈箱
- **elements**:
  - section_title: H2 / required / "保固申請管理"
  - warranty_rule_banner: AlertBanner / required / icon: Info / `bg-blue-50 border-blue-200 text-blue-700 rounded-lg p-3 mb-4`
    - 文案："保固起算日以「交屋日期」為準，非「入住日期」。此為系統核心規則，所有保固計算均依據此原則。"
  - status_filter: Select / required / 全部 / 有效（active）/ 寬限期（grace_period）/ 已過期（expired）
  - search_input: Input / required / icon: Search / placeholder: "搜尋案件編號、設備或客戶..." / debounce 300ms
  - claims_table: DataTable / required / 欄位如下：
    - col_claim_id: Text Code / required / 案件編號 / `font-mono`
    - col_device: Text / required / 設備名稱（品牌 + 型號）
    - col_customer: AvatarText / required / 客戶名稱
    - col_warranty_start: Text / required / 保固起始日（= 交屋日期）/ yyyy/MM/dd / Tooltip: "交屋日期"
    - col_warranty_end: Text / required / 保固到期日 / yyyy/MM/dd
    - col_days_remaining: DaysCounter / required /
      - >90 天：`text-green-600` "{n} 天"
      - 30-90 天：`text-amber-600` "{n} 天"
      - 1-29 天：`text-red-600 font-bold` "{n} 天"
      - 0 天：`text-red-600 font-bold` "今日到期"
      - <0 天（寬限期內或已過期）：依 status 顯示
    - col_status: StatusBadge / required /
      - 有效（active）：`bg-green-100 text-green-700` "有效"
      - 寬限期（grace_period）：`bg-amber-100 text-amber-700` "寬限期" + 剩餘天數
      - 已過期（expired）：`bg-red-100 text-red-700` "已過期"
    - col_evidence: EvidenceGalleryTrigger / required /
      - 縮圖預覽（最多 3 張小圖 32×32px）+ "+{n}" 更多
      - 點擊開啟證據照片燈箱
    - col_actions: ActionButtons / required /
      - "檢視詳情" — 展開列內詳情 / 開啟側面板
      - "核准保固" — 僅 active 狀態顯示
      - "拒絕" — 附拒絕原因
  - evidence_lightbox: Lightbox / required / shadcn/ui `<Dialog>` 全螢幕
    - 左右箭頭切換照片
    - 照片說明文字
    - 上傳時間標記
    - 縮放功能（pinch-to-zoom Mobile）
    - 下載原圖按鈕
- **states**:
  - default: 顯示保固申請列表
  - hover: 整列 `bg-blue-50`
  - loading: Banner 正常顯示 + 8 列 Skeleton rows
  - empty: "目前無保固申請"
  - error: ErrorState + 重試按鈕
  - lightbox_open: 背景模糊 `backdrop-blur-sm`，燈箱全螢幕
  - lightbox_loading: 照片位置顯示 Spinner
- **copy_constraints**: 設備名稱最多 30 字元，保固規則 Banner 固定文案不可修改

---

### 子頁面 4: 爭議處理 `/admin/disputes`

### Section: dispute_cases

- **layout**: 上方列表 + 下方（或右側面板）詳情區，點擊列表項目展開詳情
- **elements**:
  - section_title: H2 / required / "爭議案件處理"
  - type_filter: Multi-Select / required / 爭議類型：
    - 價格爭議（pricing）
    - 品質爭議（quality）
    - 保固爭議（warranty）
    - 取消費爭議（cancellation_fee）
    - 結算爭議（settlement）
  - status_filter: Select / required / 全部 / 待處理 / 調解中 / 已結案
  - dispute_list: DataTable / required /
    - col_dispute_id: Text Code / required / 爭議案件編號 / `font-mono`
    - col_type: TypeBadge / required / 爭議類型 Badge
      - pricing：`bg-blue-100 text-blue-700` "價格"
      - quality：`bg-purple-100 text-purple-700` "品質"
      - warranty：`bg-green-100 text-green-700` "保固"
      - cancellation_fee：`bg-orange-100 text-orange-700` "取消費"
      - settlement：`bg-pink-100 text-pink-700` "結算"
    - col_parties: Text / required / "{customer_name} vs {technician_name}"
    - col_amount: Text Number / required / 爭議金額 "NT$ {amount}"
    - col_created_at: Text / required / 建立日期
    - col_status: StatusBadge / required /
      - 待處理（pending）：`bg-yellow-100 text-yellow-700` "待處理"
      - 調解中（mediating）：`bg-blue-100 text-blue-700` "調解中"
      - 已結案（resolved）：`bg-green-100 text-green-700` "已結案"
      - 已駁回（dismissed）：`bg-gray-100 text-gray-500` "已駁回"
  - evidence_comparison_panel: SplitPanel / required / 點擊爭議案件後展開
    - **layout**: 左右並列，`grid grid-cols-2 gap-4 p-6 bg-white rounded-xl border border-gray-200`
    - left_panel: EvidenceSection / required /
      - panel_title: H4 / "客戶方證據" / `text-[#2563EB]`
      - evidence_list: MediaCard[] / required / 照片 + 影片 + 文字說明
      - submitted_at: Text Caption / 提交時間
    - right_panel: EvidenceSection / required /
      - panel_title: H4 / "技師方證據" / `text-[#F59E0B]`
      - evidence_list: MediaCard[] / required / 照片 + 影片 + 文字說明
      - submitted_at: Text Caption / 提交時間
    - divider: VerticalDivider / required / `border-l border-gray-300` 中間分隔線
  - resolution_form: Form / required / 展開於證據區下方
    - mediator_notes: Textarea / required / "調解備註" / placeholder: "請輸入調解說明與依據..." / 最少 20 字
    - resolution_amount: NumberInput / required / "調解金額" / "NT$" 前綴 / min: 0
    - resolution_type: Select / required / "調解方式" / 全額退款 / 部分退款 / 補償方案 / 駁回
    - approve_btn: Button Primary / required / "確認調解結果"
    - save_draft_btn: Button Secondary / optional / "儲存草稿"
- **states**:
  - default: 列表顯示，無選中項目
  - selected: 選中列 `bg-blue-50 border-l-4 border-[#2563EB]`，下方展開證據對比面板
  - loading: 列表 8 列 Skeleton / 證據面板 Skeleton（左右各 3 張 Skeleton 圖片）
  - empty: "目前無爭議案件"
  - error: ErrorState + 重試按鈕
  - evidence_loading: 個別照片/影片載入中 Spinner
  - submitting: 確認按鈕 Spinner + "提交中..."
  - form_validation: 字數不足時行內紅色錯誤訊息
- **copy_constraints**: 調解備註最多 2000 字元，爭議類型 Badge 最多 4 字

---

### 子頁面 5: 稽核日誌 `/admin/audit-events`

### Section: audit_log

- **layout**: 全寬，頂部搜尋篩選列 + DataTable（可展開列）
- **elements**:
  - section_title: H2 / required / "稽核日誌"
  - filter_bar: FilterBar / required / `flex flex-wrap gap-3 mb-4`
    - date_range_picker: DateRangePicker / required / 預設過去 7 天 / 最長 90 天
    - keyword_search: Input / required / icon: Search / placeholder: "搜尋操作者、資源或動作..." / debounce 300ms
    - event_type_filter: Multi-Select / required / 7 種事件類型可多選：
      - 使用者操作（user_action）
      - 系統事件（system_event）
      - 資料變更（data_change）
      - 權限變更（permission_change）
      - 登入登出（auth_event）
      - API 呼叫（api_call）
      - 錯誤事件（error_event）
    - actor_filter: Select / optional / 操作者篩選（動態載入使用者列表）
    - clear_btn: Button Ghost / optional / "清除篩選"
  - event_count: Text Caption / required / "共 {total} 筆紀錄"
  - audit_table: DataTable / required / 固定表頭，可展開列
    - col_timestamp: Text / required / 時間戳 yyyy/MM/dd HH:mm:ss / `font-mono text-sm` / 可排序（預設降序）
    - col_event_type: TypeBadge / required / 事件類型 Badge
      - user_action：`bg-blue-100 text-blue-700` "使用者操作"
      - system_event：`bg-gray-100 text-gray-600` "系統事件"
      - data_change：`bg-green-100 text-green-700` "資料變更"
      - permission_change：`bg-purple-100 text-purple-700` "權限變更"
      - auth_event：`bg-cyan-100 text-cyan-700` "登入登出"
      - api_call：`bg-indigo-100 text-indigo-700` "API 呼叫"
      - error_event：`bg-red-100 text-red-700` "錯誤事件"
    - col_actor: AvatarText / required / 操作者名稱 + 角色
    - col_resource: Text / required / 被操作資源（如 "工單 #WO-2026-0412"、"技師 ID-1023"）
    - col_action: Text Code / required / 操作動作（create / read / update / delete / login / logout / export）/ `font-mono text-sm`
    - col_expand: ExpandButton / required / 箭頭按鈕展開詳情
    - expanded_row: ExpandedContent / required / 展開後顯示：
      - details_json: CodeBlock / required / `<pre>` 區塊顯示完整 JSON 資料 / `bg-gray-900 text-green-400 rounded-lg p-4 text-sm font-mono overflow-x-auto`
      - ip_address: Text Caption / optional / "IP: {address}"
      - user_agent: Text Caption / optional / "瀏覽器: {parsed_ua}"
      - copy_json_btn: Button Ghost Small / required / icon: Copy / "複製 JSON"
  - export_btn: Button Secondary / optional / icon: FileDown / "匯出日誌" / 匯出當前篩選結果
- **states**:
  - default: 顯示日誌列表，最新在上
  - hover: 整列 `bg-blue-50`（error_event 列 hover `bg-red-50`）
  - loading: 10 列 Skeleton rows
  - empty: "選定條件下無稽核紀錄" + 調整篩選建議
  - error: ErrorState + 重試按鈕
  - expanded: 展開列平滑動畫 `transition-all duration-200`，箭頭旋轉 180°
  - error_row: error_event 類型的列左側加紅色邊框 `border-l-4 border-red-500`
  - copying: 複製按鈕點擊後短暫變為 "已複製" + icon: Check / 2 秒後恢復
- **copy_constraints**: 資源名稱最多 50 字元，JSON 詳情無長度限制（可捲動）

### Section: audit_export_modal

- **trigger**: 頁面標題列「匯出」按鈕（lucide `Download` icon）
- **layout**: Modal size=md（基於 components/ui/Modal）
- **elements**:
  - filter_summary: ReadOnlyText / required / 顯示當前篩選條件摘要（日期範圍、事件類型、operator）
  - format_radio: RadioGroup / required / 兩選項 CSV / JSON，預設 CSV
  - estimated_count: Text / optional / 「預估匯出 N 筆」（呼叫 listAuditLogs count 取得）
  - export_btn: Button Primary / required / 「開始匯出」
  - cancel_btn: Button Secondary / required / 「取消」
- **states**:
  - idle: 預設
  - exporting: export_btn disabled + spinner
  - sync_done (≤100k): 觸發 blob download，檔名 `audit-events-YYYY-MM-DD-HHmm.csv`，useToast variant=success「匯出完成」，關閉 modal
  - async_started (>100k): 收到 202 + job_id，useToast variant=info「匯出中，完成後寄送 email」，關閉 modal
  - error: useToast variant=error 顯示錯誤
- **api**:
  - POST /api/v1/audit-logs/export（operationId: exportAuditEvents）
  - body: { from?, to?, event_types[], actor_id?, resource_type?, format: 'csv'|'json' }
  - 200: text/csv stream → blob 下載
  - 202: { job_id, estimated_completion } → email 通知

---

### 子頁面 6: 角色權限 (RBAC) `/admin/roles`

### Section: rbac_management

- **layout**: 上方角色列表 + 下方權限矩陣，`flex flex-col gap-6`
- **elements**:
  - section_title: H2 / required / "角色與權限管理"
  - role_list: HorizontalCards / required / `flex gap-4 mb-6`
    - role_card: Card / required / 每個角色一張卡片
      - role_name: H4 / required / 角色名稱（admin / reviewer / technician / 自訂角色）
      - role_description: Text Caption / required / 角色說明
      - user_count: Badge / required / "使用者 {count}" / `bg-gray-100`
      - is_system: Badge / optional / 系統內建角色顯示 "系統角色" `bg-blue-100 text-blue-700`
      - edit_btn: IconButton / required / icon: Pencil / 僅自訂角色可編輯
      - delete_btn: IconButton / optional / icon: Trash / 紅色 / 僅自訂角色且無使用者時可刪除
    - 選中角色卡片 `ring-2 ring-[#2563EB]` 邊框高亮
  - create_role_btn: Button Primary / required / icon: Plus / "建立自訂角色"
  - create_role_modal: Dialog / required /
    - title: "建立自訂角色"
    - role_name_input: Input / required / "角色名稱" / 唯一性驗證
    - role_description_input: Textarea / optional / "角色說明"
    - confirm_btn: Button Primary / "建立"
    - cancel_btn: Button Ghost / "取消"
  - permission_matrix: Table / required / Checkbox 網格
    - **layout**: 固定首欄（資源名稱） + 可水平捲動的權限欄
    - row_headers（資源）: Text / required / 列標題 — 系統資源：
      - 工單（work_orders）
      - 技師（technicians）
      - 客戶（customers）
      - 結算（settlements）
      - 發票（invoices）
      - 退款（refunds）
      - 庫存（inventory）
      - 保固（warranty_claims）
      - 爭議（disputes）
      - 稽核日誌（audit_events）
      - 角色權限（roles）
      - 系統設定（settings）
    - col_headers（動作）: Text / required / 欄標題 — 三種權限動作：
      - 讀取（read）
      - 寫入（write）
      - 刪除（delete）
    - permission_checkbox: Checkbox / required / 每個交叉格一個 Checkbox
      - checked：`bg-[#2563EB]` 勾選
      - unchecked：空白
      - disabled：系統角色的核心權限不可取消 / 灰底 `bg-gray-100` + 鎖定 icon
    - row_select_all: Checkbox / optional / 整列全選（給予某資源所有權限）
    - col_select_all: Checkbox / optional / 整欄全選（給予所有資源某權限）
  - save_permissions_btn: Button Primary / required / "儲存權限設定" / 有變更時啟用
  - reset_btn: Button Ghost / optional / "重置為預設" / 僅自訂角色顯示
- **states**:
  - default: 預設選中 admin 角色，顯示其權限矩陣
  - role_selected: 點擊角色卡片 → 權限矩陣更新為該角色的權限
  - loading: 角色卡片 Skeleton + 權限矩陣 Skeleton
  - empty_roles: "尚無自訂角色" + 建立按鈕（系統角色始終存在）
  - dirty: 有未儲存變更時，儲存按鈕亮起 + 標題旁 "未儲存" amber Badge
  - saving: 儲存按鈕 Spinner + "儲存中..."
  - system_role_locked: 系統角色（admin/reviewer/technician）的部分核心權限 Checkbox disabled + Tooltip "系統角色核心權限不可變更"
  - hover_checkbox: Checkbox hover 時顯示 Tooltip "{role} 對 {resource} 的 {action} 權限"
  - error: Toast "權限儲存失敗，請重試"
  - conflict: Toast "權限設定衝突：{detail}" — 如嘗試刪除自身 admin 角色的 roles.write 權限
- **copy_constraints**: 角色名稱最多 20 字元，角色說明最多 100 字元

---

## [T1.5 §6 補漏] 既有子頁補強（from Info-Arch §6.13–§6.18）

### §6.13 退款審批 補強（子頁 1）

**雙簽 PIN 驗證流程**：金額超門檻（NT$ 5,000 二簽 / NT$ 100,000 三簽）時：
1. 簽核者於 Modal 內輸入 6 位 PIN（非密碼，專屬簽章用，於 /settings 設定）
2. PIN 驗證通過 → Signature Canvas 啟用（觸控/滑鼠手寫）
3. 簽署後後端記錄：`signer_id`, `signer_role`, `signed_at`, `client_ip`, `signature_hash`（SHA-256）
4. PIN 連續錯誤 5 次鎖 30 分鐘

**Accounting Voucher 自動建立**：核准成功後：
- 同 transaction 產出 `accounting_voucher`（voucher_no、金額、分錄對應）
- 前端 Toast「已核准，傳票號 #V-XXXX」+ 連結至 A15 帳務
- 失敗時回滾退款狀態，標 `pending_voucher_retry` + 通知會計

### §6.14 RBAC 管理 補強（子頁 6）

**臨時授權面板**（新 Modal：「授予臨時權限」）：
- 選擇使用者（autocomplete）
- 選擇額外權限碼（checklist，僅能選目前登入者可授權範圍內）
- 有效期限：選擇器（小時 / 天數，上限 7 天）
- 雙簽：需 `admin` + `operations_manager` 皆簽（Signature Canvas × 2）
- 清單區顯示：已授予 / 待簽核 / 已過期（三 Tab）
- API：`POST /api/v1/roles/temporary-grants`

**權限差異檢視**：從既有角色複製時：
- 對比視圖：左欄「來源角色權限」右欄「新角色（可編輯）」
- 權限變動高亮：新增（綠底）、移除（紅刪除線）、未變（灰）
- 儲存前強制使用者 review 變動摘要

### §6.16 庫存管理 補強（子頁 2）

**調撥 Modal**（「倉對倉調撥」按鈕）：
- 來源倉 / 目的地倉（下拉）+ 品項 + 數量 + 調撥原因
- 簽核：`warehouse_manager` 角色單簽（Canvas + PIN）
- API：`POST /api/v1/inventory/transfers`
- 同步寫 `audit_events`（action=`inventory.transfer`, before/after stock）

**報廢 Modal**（每列「報廢」按鈕）：
- 品項 + 報廢數量 + 報廢原因（下拉：過期/損壞/召回/其他）
- 報廢金額 > NT$ 5,000 需 `warehouse_manager` + `accountant` 雙簽
- API：`POST /api/v1/inventory/write-offs`

### §6.17 保固索賠 補強（子頁 3）

**技師責任扣罰雙簽**（在保固審核 Modal 內）：
- 顯示原施工技師名 + 技師分級 + 歷史客訴數
- 扣罰金額輸入（含快速選擇：NT$ 500 / 1,000 / 2,000）
- 雙簽：`operations_manager` + `technician_supervisor`（Signature Canvas × 2）
- 扣罰後：技師端 App Toast 通知 + 月結算自動扣除

**返工工單自動建立**：
- 保固核准後，系統自動 `POST /api/v1/work-orders`，body 含 `parent_work_order_id` + `type=rework` + `is_free=true`
- 原工單 `status=warranty_accepted`，返工單透過 `dispatch_candidates` 強制篩選 S 級技師
- Toast「返工工單已建立 #WO-XXX」+ 連結

### §6.18 爭議仲裁 補強（子頁 4）

**技師申訴通道**（新 entry point）：
- 從 A27 技師結算扣罰項或 T4 帳戶中心「申訴」按鈕進入
- 開啟新爭議 Modal：類型 `technician_dispute`、對應扣罰記錄 ID、申訴理由 + 證據上傳
- API：`POST /api/v1/disputes`，backlog 進入 `support_agent` 佇列

**後續自動動作觸發邏輯**：裁決提交後依 resolution 自動執行：
| resolution | 自動動作 |
|:---|:---|
| `refund_partial` | 觸發 Flow 6 退款（`POST /refunds`）|
| `rework_required` | 建返工工單（同 §6.17 邏輯）|
| `technician_penalty` | 寫技師扣罰 + 月結算 |
| `customer_rejected` | LINE Flex 最終答覆客戶 |
| `escalate_external` | 標 `DISPUTE_EXTERNAL_PENDING` 外部調解 |

全部動作包裝在單一 DB transaction，失敗回滾 + 告警 `operations_manager`。

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### 退款審核
1. 進入頁面 → 載入退款佇列（依 SLA 升序）→ SLA 摘要列更新
2. 點擊「核准」→ 開啟 Modal → 輸入備註 → 確認 → `PATCH /api/v1/refunds/{id}` body: `{ action: "approve", notes }` → 成功 Toast + 列表 refetch
3. 點擊「拒絕」→ 開啟 Modal → 輸入拒絕原因（必填，至少 10 字）→ 確認 → PATCH → 成功 Toast
4. 雙簽場景（>NT$100K）→ 第一位審核者核准後，狀態變為「審核中」→ 通知第二位審核者 → 第二位核准後狀態變為「已核准」

#### 庫存管理
1. 進入頁面 → 載入庫存列表 → 低庫存/缺貨摘要卡片更新
2. 點擊「補貨」→ 開啟 Modal → 輸入補貨數量 → 即時預覽新庫存 → 確認 → `POST /api/v1/inventory/{id}/restock` → 成功 Toast + 列表 refetch
3. 行內編輯閾值 → 點擊閾值數字 → 變為 Input → 修改 → 確認 → `PATCH /api/v1/inventory/{id}` → Optimistic update

#### 保固申請
1. 進入頁面 → 載入申請列表 → 保固規則 Banner 始終顯示
2. 點擊縮圖 → 開啟證據燈箱 → 左右箭頭瀏覽 → 縮放檢視
3. 核准/拒絕保固 → 對應 API 操作 → 列表 refetch

#### 爭議處理
1. 進入頁面 → 載入爭議列表
2. 點擊爭議案件 → 展開證據對比面板（客戶 vs 技師）
3. 檢視雙方證據 → 填寫調解備註 + 調解金額 + 調解方式 → 點擊「確認調解結果」→ `PATCH /api/v1/disputes/{id}/resolve` → 成功 Toast

#### 稽核日誌
1. 進入頁面 → 預設載入近 7 天日誌
2. 調整日期範圍/事件類型篩選 → 重新查詢 → 表格更新
3. 點擊展開按鈕 → 平滑展開 JSON 詳情 → 可複製 JSON

#### 角色權限
1. 進入頁面 → 載入角色列表 + 預設顯示 admin 權限矩陣
2. 點擊角色卡片 → 權限矩陣切換至該角色
3. 勾選/取消 Checkbox → dirty state → 點擊「儲存」→ `PATCH /api/v1/roles/{id}/permissions` → 成功 Toast
4. 建立自訂角色 → Modal → 輸入名稱 → `POST /api/v1/roles` → 角色列表 refetch → 自動選中新角色

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 左側子導覽 `w-56` + 右側內容區 | 完整體驗，爭議面板左右並列 |
| Tablet (768-1279px) | 子導覽收合為頂部 Tab bar | 爭議證據改為上下堆疊，權限矩陣水平捲動 |
| Mobile (<768px) | 子導覽改為下拉選單 / 所有表格改為卡片列表 | 證據對比改為 Tab 切換（客戶/技師）/ 權限矩陣改為逐資源卡片式 |

### 資料更新策略

- 退款佇列：`refetchInterval: 30_000`（30 秒自動更新，SLA 計時需即時）
- 庫存列表：`staleTime: 60_000`，手動操作後 invalidate
- 保固申請：`staleTime: 60_000`
- 爭議案件：`staleTime: 60_000`
- 稽核日誌：僅手動查詢時載入，無自動更新（避免大量資料消耗）
- 角色權限：`staleTime: 300_000`（5 分鐘）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - **退款審核**:
    - GET `/api/v1/refunds` — 取得退款佇列
      - Query params: `status`, `sort_by` (sla_remaining), `page`, `limit`
      - Response: `{ data: Refund[], total: number, sla_summary: { urgent, warning, normal } }`
    - PATCH `/api/v1/refunds/{id}` — 審核退款
      - Body: `{ action: "approve" | "reject", notes: string }`
      - 分層審核邏輯由後端驗證：≤NT$10K 經理、≤NT$100K 總監、>NT$100K 雙簽
  - **庫存管理**:
    - GET `/api/v1/inventory` — 取得庫存列表
      - Query params: `search`, `category`, `stock_status` (normal|low|out), `page`, `limit`
      - Response: `{ data: InventoryItem[], total: number, summary: { total_items, low_stock, out_of_stock } }`
    - PATCH `/api/v1/inventory/{id}` — 更新物料資訊（閾值等）
      - Body: `{ threshold?, item_name?, category? }`
    - POST `/api/v1/inventory/{id}/restock` — 補貨
      - Body: `{ quantity: number, supplier?: string, notes?: string }`
    - POST `/api/v1/inventory` — 新增物料
      - Body: `{ item_name, sku, initial_stock, threshold, category? }`
  - **保固申請**:
    - GET `/api/v1/warranty-claims` — 取得保固申請列表
      - Query params: `status` (active|grace_period|expired), `search`, `page`, `limit`
      - Response: `{ data: WarrantyClaim[], total: number }`
      - 重要：`warranty_start_date` 欄位值 = 交屋日期（handover_date），非入住日期
    - PATCH `/api/v1/warranty-claims/{id}` — 審核保固申請
      - Body: `{ action: "approve" | "reject", notes?: string }`
  - **爭議處理**:
    - GET `/api/v1/disputes` — 取得爭議列表
      - Query params: `type` (pricing|quality|warranty|cancellation_fee|settlement), `status`, `page`, `limit`
      - Response: `{ data: Dispute[], total: number }`
    - GET `/api/v1/disputes/{id}` — 取得爭議詳情（含雙方證據）
      - Response: `{ id, type, customer_evidence: Evidence[], technician_evidence: Evidence[], mediator_notes?, resolution? }`
    - PATCH `/api/v1/disputes/{id}/resolve` — 調解爭議
      - Body: `{ mediator_notes: string, resolution_amount: number, resolution_type: string }`
  - **稽核日誌**:
    - GET `/api/v1/audit-events` — 取得稽核日誌
      - Query params: `date_from`, `date_to`, `event_type` (user_action|system_event|data_change|permission_change|auth_event|api_call|error_event), `actor`, `keyword`, `page`, `limit`
      - Response: `{ data: AuditEvent[], total: number }`
    - GET `/api/v1/audit-events/export` — 匯出稽核日誌
      - Query params: 同上篩選條件 + `format` (csv|xlsx)
  - **角色權限**:
    - GET `/api/v1/roles` — 取得角色列表
      - Response: `{ data: Role[] }` 其中 Role: `{ id, name, description, is_system, user_count, permissions: { resource: string, actions: string[] }[] }`
    - POST `/api/v1/roles` — 建立自訂角色
      - Body: `{ name: string, description?: string }`
    - PATCH `/api/v1/roles/{id}/permissions` — 更新角色權限
      - Body: `{ permissions: { resource: string, actions: ("read"|"write"|"delete")[] }[] }`
    - DELETE `/api/v1/roles/{id}` — 刪除自訂角色（僅無使用者時可刪除）
- **Zustand Store**:
  - `useAdvancedAdminStore`: 管理當前子頁面、各子頁面篩選狀態
  - `useDisputeStore`: 管理爭議調解表單 dirty state
  - `useRBACStore`: 管理權限矩陣 dirty state + 選中角色
- **error_cases**:
  - 網路錯誤：Toast "網路連線異常" + TanStack Query 自動重試
  - 退款權限不足（403）：操作按鈕 disabled + Tooltip "您的權限不足以審核此金額層級"
  - 庫存 SKU 重複（409）：新增物料 Modal 顯示 "此 SKU 已存在"
  - 保固日期計算錯誤：前端不自行計算保固，一律使用後端回傳的 warranty_start/end
  - 爭議調解衝突（409）：Toast "此爭議已被其他管理員調解" + 自動 refetch
  - 角色刪除衝突（409）：Toast "此角色仍有 {count} 位使用者，無法刪除"
  - 角色權限自鎖（422）：Toast "無法移除自身的角色管理權限" — 防止管理員鎖定自己

---

## [EXCEPTION TO GLOBAL RULES]

- 稽核日誌 JSON 詳情使用深色主題 `bg-gray-900`，與 Global 淺色 BG 不同
- 爭議處理的證據對比面板在 Desktop 使用 `grid-cols-2` 強制並排，不受 Global 內容最大寬度限制
- 退款 SLA 計時器使用 `setInterval` 每秒更新顯示，不受 Global 資料更新策略（polling/staleTime）管控
- 權限矩陣在 Mobile 斷點下使用卡片式呈現，與 Global 表格 Mobile 卡片轉換規則不同（需自訂 layout 而非自動轉換）

---

## [ACCEPTANCE CRITERIA]

### 共用
- [ ] 側邊子導覽正確切換六個子頁面，URL 同步
- [ ] 子導覽 Badge 正確顯示待處理數量（退款、低庫存、爭議）
- [ ] 所有子頁面具備 loading / error / empty 三態
- [ ] RWD 三個斷點佈局正確

### 退款審核
- [ ] 佇列依 SLA 剩餘時間升序排列，SLA ≤ 2小時紅色警示
- [ ] 金額色碼正確：≤NT$10K 黑字 / ≤NT$100K 琥珀 / >NT$100K 紅色
- [ ] 分層審核視覺步驟正確：≤NT$10K 經理單簽 / ≤NT$100K 總監單簽 / >NT$100K 雙簽
- [ ] 核准/拒絕 Modal 正常運作，拒絕原因必填驗證
- [ ] 無權限審核者操作按鈕 disabled

### 庫存管理
- [ ] 低庫存琥珀色 Badge、缺貨紅色 Badge 正確顯示
- [ ] 補貨 Modal 即時預覽新庫存量
- [ ] 閾值行內編輯正常，Optimistic update
- [ ] 新增物料 SKU 唯一性驗證

### 保固申請
- [ ] 保固規則 Banner 始終顯示且不可關閉："交屋日期為準，非入住日期"
- [ ] 保固天數倒數色碼正確：>90天綠 / 30-90天琥珀 / <30天紅
- [ ] 三態 Badge 正確：active/grace_period/expired
- [ ] 證據照片燈箱正常開啟、左右切換、縮放

### 爭議處理
- [ ] 五種爭議類型 Badge 色碼正確
- [ ] 證據對比左右並列：客戶左側、技師右側
- [ ] 調解表單必填驗證（備註 ≥ 20字、金額 ≥ 0）
- [ ] 調解結果提交成功後列表 refetch

### 稽核日誌
- [ ] 日期範圍 + 7 種事件類型篩選正常
- [ ] 展開列顯示 JSON 深色主題 CodeBlock
- [ ] 複製 JSON 按鈕功能正常
- [ ] 匯出日誌功能正常

### 角色權限
- [ ] 三種系統角色（admin/reviewer/technician）始終存在且不可刪除
- [ ] 權限矩陣 Checkbox 網格：12 資源 × 3 動作 正確呈現
- [ ] 系統角色核心權限 Checkbox disabled + 鎖定提示
- [ ] 建立自訂角色 + 權限設定 + 儲存流程正常
- [ ] 防止管理員移除自身 roles.write 權限（自鎖保護）
- [ ] 有使用者的角色不可刪除

### 效能與規範
- [ ] 各子頁面首次載入 < 2 秒
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、Secondary #1E293B、BG #F8FAFC、Font Inter + Noto Sans TC）


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
