# Assembly Prompt: 知識庫管理（Knowledge Base）

> Global Brand System v1.0 + Page Spec → 一體化 AI Prompt
> 建立日期：2026-04-21

---

## === GLOBAL PROJECT GUIDELINE (DO NOT OVERRIDE) ===

你是「電子鎖智能客服與派工平台」的資深產品設計師與前端工程師，負責維護整個專案的設計一致性。

### 核心設計系統

- **品牌**：電子鎖智能客服與派工平台
- **角色**：資深產品設計師與前端工程師
- **配色**：Primary #2563EB (Trust Blue) / Primary Hover #1D4ED8 / Accent #F59E0B (Amber CTA) / Accent Hover #D97706 / Secondary #1E293B (Sidebar) / BG Page #F8FAFC / BG Surface #FFFFFF / Text Primary #0F172A / Text Secondary #64748B / Border #E2E8F0
- **語義色**：Pending #6366F1 / Assigned #8B5CF6 / Active #3B82F6 / Warning #F59E0B / Success #10B981 / Danger #EF4444
- **字體**：Inter + "Noto Sans TC", sans-serif / Code: JetBrains Mono
- **字級**：Display 32px/700 / H1 28px/700 / H2 24px/600 / H3 20px/600 / Body 14px/400 / Caption 11px/400 / KPI 36px/700
- **圓角**：SM 4px / MD 6px / LG 8px / XL 12px
- **陰影**：SM 0 1px 2px rgba(0,0,0,0.05) / MD 0 4px 6px -1px rgba(0,0,0,0.1) / LG 0 10px 15px -3px rgba(0,0,0,0.1)
- **Grid**：Admin 1440px/12col/24px gap, Sidebar 240px/64px
- **斷點**：Mobile <768px / Tablet 768-1024px / Desktop >1024px
- **技術棧**：Next.js 14 (App Router) + React 19 + shadcn/ui + Tailwind CSS 3.4 + TanStack Query + Zustand + Recharts
- **語氣**：精準、可靠、有溫度。稱呼「你」。按鈕用主動語態。錯誤先說問題再說解法。

### 重要規範
- 所有頁面遵守此設計系統
- 除 EXCEPTION RULES 明確說明外，不准違反
- 元件優先使用 shadcn/ui，不自造輪子

---

## === CURRENT TASK: BUILD ONE PAGE ===

本次任務：根據上方 Global Guideline，設計並實作「知識庫管理（Knowledge Base）」。

### [PAGE SPECIFICATION]

## [PAGE META]

- **page_name**: Knowledge Base Management
- **route_path**: `/knowledge-base/cases`（案例庫）、`/knowledge-base/manuals`（手冊管理）、`/knowledge-base/sop-drafts`（SOP 草稿）
- **page_type**: tabbed_list + form + review
- **primary_goal**: 統一管理品牌知識資產，包含歷史案例、產品手冊、AI 自動產生的 SOP 草稿
- **secondary_goal**: 確保知識庫內容經過人工審核後才進入正式索引，維護知識品質
- **target_users**:
  - 主要：品牌管理員（日常維護知識庫）
  - 次要：技術主管（審核 SOP 草稿）
- **entry_point**: 左側導覽列「知識庫」選項 / 問題卡片詳情頁「關聯知識案例」
- **expected_time_on_page**: 案例頁 2-5 分鐘（瀏覽/搜尋）；手冊頁 1-3 分鐘（上傳管理）；SOP 草稿頁 5-10 分鐘（審核作業）

---

## [STRUCTURE: SECTIONS]

1. **page_header**
   - section_type: header
   - section_purpose: 顯示頁面標題與三大子頁籤切換

2. **tab_cases_content**
   - section_type: card_grid + search + modal_form
   - section_purpose: 瀏覽、搜尋、建立與編輯知識案例

3. **tab_manuals_content**
   - section_type: file_list + upload
   - section_purpose: 管理產品手冊 PDF 檔案，追蹤切片處理進度

4. **tab_sop_drafts_content**
   - section_type: queue_list
   - section_purpose: 審核 AI 自動產生的 SOP 草稿，控制知識品質

5. **sop_review_panel**
   - section_type: side_by_side_review
   - section_purpose: 提供 SOP 草稿的並排審核介面（AI 內容 vs 審核者意見）

6. **case_form_modal**
   - section_type: modal_form
   - section_purpose: 建立或編輯知識案例的表單

7. **pdf_viewer_panel**
   - section_type: viewer
   - section_purpose: 檢視手冊 PDF 內容並標示切片區段

---

## [SECTION COMPONENT SPEC]

### Section: page_header

- **layout**: 全寬單欄，標題左對齊，頁籤列於標題下方
- **elements**:
  - page_title: H1 / required / "知識庫管理"
  - breadcrumb: Breadcrumb / required / 首頁 > 知識庫 > {當前頁籤名稱}
  - tab_navigation: Tabs / required / 三個頁籤
    - tab_cases: Tab / required / "案例庫" / 路由 `/knowledge-base/cases`
    - tab_manuals: Tab / required / "產品手冊" / 路由 `/knowledge-base/manuals`
    - tab_sop_drafts: Tab / required / "SOP 草稿" / 路由 `/knowledge-base/sop-drafts`
  - tab_count_badges: Badge[] / required / 各頁籤旁顯示項目數量（如 "案例庫 (128)"）
- **states**:
  - default: 依當前路由高亮對應頁籤，底線指示器使用 Primary（#2563EB）
  - hover (tab): 文字色變為 Primary，背景淺藍 #EFF6FF
  - loading: 頁籤數量徽章顯示 Skeleton
- **copy_constraints**: 頁籤名稱最多 8 字

### Section: tab_cases_content

- **layout**: 頂部搜尋列 + 下方卡片網格（Desktop 3 欄、Tablet 2 欄、Mobile 1 欄）
- **elements**:
  - search_bar: SearchInput / required / placeholder: "搜尋案例（支援語意搜尋）..." / 使用向量相似度搜尋
  - search_mode_toggle: Toggle / optional / "關鍵字搜尋" ↔ "語意搜尋" 切換
  - create_case_button: Button Primary / required / "+ 新增案例" / 開啟 case_form_modal
  - case_card_grid: Grid / required / 每張卡片包含以下元素：
    - card_title: H3 / required / 案例標題
    - card_brand_tags: TagGroup / required / 品牌與型號標籤（Chip 樣式，背景 #EFF6FF，文字 #2563EB）
    - card_success_rate: ProgressBar / required / 解決成功率（0-100%），≥80% Emerald，50-79% Amber，<50% Red
    - card_usage_count: Badge / required / "已使用 {count} 次"，背景 Secondary（#1E293B），文字白色
    - card_last_updated: Caption / required / "更新於 {relative_time}"
    - card_click_area: ClickableCard / required / 點擊開啟 case_form_modal（編輯模式）
  - pagination: Pagination / required / 每頁 12 張卡片
- **states**:
  - default: 顯示卡片網格，依 last_updated 降序排列
  - hover (card): 邊框變為 Primary（#2563EB），輕微上移 shadow-md → shadow-lg
  - loading: Skeleton 卡片佔位（顯示 12 張）
  - error: 網格區域顯示錯誤訊息 + 重試按鈕
  - empty: 置中插圖 + "知識庫尚無案例，立即建立第一筆" + CTA「新增案例」
  - searching: 搜尋中顯示 Spinner + "正在搜尋語意相似案例..."
  - search_empty: "找不到相關案例，試試其他關鍵字" + 清除搜尋建議
- **copy_constraints**: 案例標題最多 50 字；品牌標籤最多 3 個顯示，超過以 +N more 表示

### Section: tab_manuals_content

- **layout**: 頂部上傳區域 + 下方檔案列表
- **elements**:
  - upload_dropzone: DropZone / required / 虛線邊框拖放區域，"拖放 PDF 檔案至此，或 點擊上傳"，圖示：Upload Cloud
  - upload_constraints_text: Caption / required / "支援格式：PDF，單檔上限 50MB"
  - file_table: DataTable / required
    - col_filename: TableColumn / required / 檔案名稱，可點擊開啟 PDF Viewer
    - col_brand: TableColumn / required / 品牌名稱
    - col_page_count: TableColumn / required / 頁數
    - col_chunk_count: TableColumn / required / 切片數量（處理完成後顯示）
    - col_upload_date: TableColumn / required / 上傳日期，相對時間格式
    - col_processing_status: TableColumn / required / 處理狀態徽章：pending=Gray（#94A3B8）、processing=Blue（#2563EB）+ 旋轉 Spinner、completed=Emerald（#10B981）、failed=Red（#EF4444）
    - col_actions: TableColumn / required / 操作按鈕：下載、刪除
  - processing_progress: ProgressBar / conditional / 當 status=processing 時顯示處理進度百分比
  - pagination: Pagination / required / 每頁 10 筆
- **states**:
  - default: 顯示已上傳檔案列表
  - hover (dropzone): 邊框色變為 Primary（#2563EB），背景淺藍 #EFF6FF
  - dragging: 拖放中邊框加粗、脈動動畫、文字變為 "放開以上傳"
  - uploading: DropZone 內顯示上傳進度條 + 檔名 + 百分比
  - upload_success: Toast 成功通知 "上傳成功，正在處理切片..."
  - upload_error: Toast 錯誤通知（檔案過大 / 格式不支援 / 網路錯誤）
  - loading: 表格 Skeleton（5 行佔位）
  - error: 表格區域錯誤訊息 + 重試
  - empty: "尚未上傳任何產品手冊" + 指向 DropZone 的箭頭提示
  - hover (row): 行背景色變為 #F8FAFC，filename 欄位加底線
  - confirm_dialog (delete): "確定要刪除此手冊？相關的切片索引也將一併移除。"
- **copy_constraints**: 檔案名稱最多 80 字，超出 truncate + tooltip

### Section: tab_sop_drafts_content

- **layout**: 佇列列表，單欄垂直排列
- **elements**:
  - sort_controls: Select / optional / 排序方式：建立時間（預設降序）、狀態
  - status_filter: Select / optional / 篩選：全部（預設）、草稿（draft）、待審核（pending_review）、已核准（approved）、已拒絕（rejected）
  - sop_list: List / required / 每筆項目包含：
    - sop_title: H3 / required / SOP 標題
    - sop_source_link: Link / required / "來源對話：{conversation_id}" / 可點擊跳轉至對話管理
    - sop_status_badge: Badge / required / 狀態徽章：draft=Gray（#94A3B8）、pending_review=Amber（#F59E0B）、approved=Emerald（#10B981）、rejected=Red（#EF4444）
    - sop_reviewer: Body SM / optional / "審核者：{reviewer_name}"（待審核/已審核時顯示）
    - sop_created_at: Caption / required / 建立時間
    - sop_click_area: ClickableRow / required / 點擊開啟 sop_review_panel
  - pagination: Pagination / required / 每頁 15 筆
- **states**:
  - default: 顯示 SOP 草稿佇列，依 created_at 降序
  - hover (item): 背景色變為 #F8FAFC，左側顯示 Primary 色條
  - loading: Skeleton 列表（5 筆佔位）
  - error: 列表區域錯誤訊息 + 重試
  - empty: "目前沒有 SOP 草稿需要處理" + 說明文字 "AI 將自動從對話中產生 SOP 草稿"
- **copy_constraints**: SOP 標題最多 60 字

### Section: sop_review_panel

- **layout**: 並排雙欄（左 1/2：AI 生成內容、右 1/2：審核工具），以 Drawer 或全頁形式開啟
- **elements**:
  - panel_header: Header / required / SOP 標題 + 狀態徽章 + 關閉按鈕
  - left_ai_content: ScrollablePanel / required / AI 自動產生的 SOP 內容
    - sop_title_display: H2 / required / SOP 標題
    - sop_body: RichTextDisplay / required / Markdown 渲染的 SOP 步驟內容
    - sop_source_info: Card / required / 來源對話摘要 + 連結
    - sop_applicable_models: TagGroup / optional / 適用型號標籤
  - right_review_tools: ScrollablePanel / required / 審核者工具
    - reviewer_notes: Textarea / required / placeholder: "輸入審核意見..." / 支援 Markdown
    - review_history: Timeline / optional / 歷次審核紀錄（若有退回重審）
    - action_buttons: ButtonGroup / required
      - btn_approve: Button Success / required / "核准並發布" / 背景 Emerald（#10B981）
      - btn_reject: Button Destructive / required / "拒絕" / 背景 Red（#EF4444）
      - btn_request_changes: Button Outline / required / "要求修改"
      - btn_save_draft: Button Ghost / optional / "暫存審核意見"
- **states**:
  - default: 左側顯示 AI 內容，右側審核工具空白待填
  - loading: 兩側分別 Skeleton 載入
  - hover (action_buttons): 各按鈕標準 hover 效果
  - confirm_dialog (btn_approve): "確定核准此 SOP？核准後將自動建立知識案例並產生向量嵌入。"
  - confirm_dialog (btn_reject): "確定拒絕此 SOP？請確認已填寫拒絕原因。"
  - validation_error: 拒絕或要求修改時，若 reviewer_notes 為空，欄位邊框變紅 + 提示 "請填寫審核意見"
  - success (approve): Toast "SOP 已核准，正在建立知識案例..." → 狀態更新為 approved → 返回列表
  - success (reject): Toast "SOP 已拒絕" → 狀態更新為 rejected → 返回列表
  - error: Toast 錯誤訊息 + 審核意見保留不遺失
- **copy_constraints**: 審核意見建議 20-500 字；SOP 內容完整顯示不做 truncate

### Section: case_form_modal

- **layout**: Modal 對話框，寬度 max-w-2xl，垂直表單佈局
- **elements**:
  - modal_title: H2 / required / "新增案例" 或 "編輯案例"
  - field_title: TextInput / required / label: "案例標題" / placeholder: "請輸入案例標題" / 驗證：必填、最多 100 字
  - field_problem_description: Textarea / required / label: "問題描述" / placeholder: "描述遇到的問題情境..." / 最少 20 字
  - field_solution_steps: RichTextEditor / required / label: "解決步驟" / 支援有序列表、程式碼區塊、圖片嵌入
  - field_applicable_models: MultiSelect / required / label: "適用型號" / 動態載入品牌型號清單，支援搜尋，Chip 形式顯示已選
  - field_tags: TagInput / optional / label: "標籤" / 自由輸入標籤，Enter 確認
  - embedding_notice: Caption / required / "儲存時將自動產生向量嵌入索引"
  - btn_save: Button Primary / required / "儲存案例"
  - btn_cancel: Button Ghost / required / "取消"
- **states**:
  - default (create): 所有欄位空白
  - default (edit): 欄位預填現有資料
  - validation_error: 必填欄位未填時邊框紅色 + 錯誤提示文字
  - submitting: btn_save 顯示 Spinner + "儲存中..." + 表單欄位 disabled
  - success: Toast "案例已儲存" → Modal 關閉 → 卡片網格重新載入
  - error: Toast 錯誤訊息 + 表單保持開啟
  - dirty_close: 有未儲存變更時關閉 Modal，彈出確認 "有未儲存的變更，確定離開？"
- **copy_constraints**: 標題最多 100 字；問題描述最少 20 字

### Section: pdf_viewer_panel

- **layout**: Drawer 從右側滑入或全頁開啟，左側 PDF 預覽 + 右側切片資訊
- **elements**:
  - viewer_header: Header / required / 檔案名稱 + 關閉按鈕
  - pdf_display: PDFViewer / required / 嵌入式 PDF 檢視器，支援翻頁、縮放
  - chunk_highlights: Overlay / required / 在 PDF 頁面上以半透明色塊標示切片邊界
  - chunk_sidebar: ScrollableList / required / 右側列出所有切片
    - chunk_item: ListItem / required / 切片編號 + 預覽文字（前 100 字）+ 頁碼範圍
  - chunk_click_sync: Interaction / required / 點擊右側切片項目 → PDF 自動捲動至對應位置並高亮
- **states**:
  - default: PDF 顯示第一頁，切片列表顯示所有切片
  - loading: PDF 載入中顯示 Skeleton + 進度條
  - error: "無法載入 PDF" + 重試 / 下載原檔連結
  - no_chunks: 處理中的手冊顯示 "切片尚在處理中..."
  - hover (chunk_item): 背景高亮 + 對應 PDF 區域輕微閃爍
- **copy_constraints**: 切片預覽文字最多 100 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. 頁面載入 → 依路由決定預設頁籤 → 載入對應資料
2. **案例頁籤**：
   - 搜尋框輸入 → debounce 500ms → 呼叫向量搜尋 API → 重新渲染卡片網格
   - 點擊「新增案例」→ 開啟空白 case_form_modal
   - 點擊卡片 → 開啟預填 case_form_modal（編輯模式）
   - 儲存表單 → POST/PUT API → 關閉 Modal → invalidateQueries 重載列表
3. **手冊頁籤**：
   - 拖放或點擊上傳 PDF → 前端驗證格式與大小 → POST API → 顯示上傳進度
   - 上傳完成 → 後端開始切片處理 → 前端每 10 秒 polling 處理狀態直到完成
   - 點擊檔案名稱 → 開啟 pdf_viewer_panel
   - 點擊刪除 → 確認對話框 → DELETE API → 列表重載
4. **SOP 草稿頁籤**：
   - 載入草稿佇列 → 點擊項目 → 開啟 sop_review_panel
   - 填寫審核意見 → 點擊「核准並發布」→ 確認 → PATCH API（status=approved）→ 自動建立 case_entry + embedding → 返回列表
   - 點擊「拒絕」→ 驗證已填意見 → 確認 → PATCH API（status=rejected）→ 返回列表
   - 點擊「要求修改」→ 驗證已填意見 → PATCH API（status=draft + reviewer_notes）→ 返回列表

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 案例 3 欄網格；手冊全寬表格；SOP 審核並排雙欄 | 完整體驗 |
| Tablet (768-1279px) | 案例 2 欄網格；手冊表格隱藏 chunk_count 欄；SOP 審核改為上下堆疊 | DropZone 尺寸縮小 |
| Mobile (<768px) | 案例 1 欄；手冊改為卡片式列表；SOP 審核全頁堆疊，按鈕固定底部 | 頁籤改為下拉選單或可滑動 Tab |

### 資料更新策略

- 案例列表：TanStack Query staleTime 5 分鐘；搜尋結果不快取（每次即時查詢）
- 手冊列表：TanStack Query staleTime 1 分鐘；processing 狀態手冊每 10 秒 polling（`refetchInterval: 10000`，僅限有 processing 項目時啟用）
- SOP 草稿：TanStack Query staleTime 3 分鐘；審核操作後 invalidateQueries
- 向量嵌入產生：非同步背景任務，完成後不通知前端（下次查詢時自然反映）

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/cases` — 取得案例列表（支援分頁、向量搜尋 `?q=keyword&search_mode=vector|keyword&page=1&per_page=12`）
  - POST `/api/v1/cases` — 建立新案例（body: title, problem_description, solution_steps, applicable_models[], tags[]）
  - PUT `/api/v1/cases/{id}` — 更新案例
  - DELETE `/api/v1/cases/{id}` — 刪除案例
  - GET `/api/v1/manuals` — 取得手冊列表（支援分頁、篩選 `?brand=xx&status=completed&page=1&per_page=10`）
  - POST `/api/v1/manuals` — 上傳手冊 PDF（multipart/form-data: file, brand）
  - DELETE `/api/v1/manuals/{id}` — 刪除手冊及其切片
  - GET `/api/v1/manuals/{id}/viewer` — 取得手冊 PDF 檢視資料（含切片位置標記）
  - GET `/api/v1/sop-drafts` — 取得 SOP 草稿列表（支援分頁、篩選 `?status=pending_review&page=1&per_page=15`）
  - PATCH `/api/v1/sop-drafts/{id}` — 更新 SOP 草稿狀態（body: status, reviewer_notes）
- **error_cases**:
  - 網路錯誤：顯示行內錯誤訊息 + 重試按鈕，表單資料保留不遺失
  - API 413（檔案過大）：Toast "檔案超過 50MB 上限，請壓縮後重試"
  - API 415（格式不支援）：Toast "僅支援 PDF 格式"
  - API 404（資源不存在）：Toast "此項目已被刪除或不存在" + 列表重載
  - API 409（衝突）：Toast "此項目已被其他管理員更新，請重新載入"
  - API 403（權限不足）：Toast "您沒有執行此操作的權限"
  - API 422（驗證錯誤）：Modal 內顯示具體欄位錯誤
  - API 500：通用錯誤訊息 + 錯誤 ID + 「聯絡技術支援」

---

## [ACCEPTANCE CRITERIA]

- [ ] 三個頁籤切換正常，URL 路由同步更新，瀏覽器上下頁功能正確
- [ ] 各頁籤數量徽章正確顯示
- [ ] **案例庫**：卡片網格 3/2/1 欄 RWD 正確
- [ ] **案例庫**：向量語意搜尋與關鍵字搜尋切換正常，結果正確
- [ ] **案例庫**：新增/編輯案例 Modal 表單驗證完整（必填、字數限制）
- [ ] **案例庫**：成功率進度條依閾值正確變色（Emerald/Amber/Red）
- [ ] **案例庫**：適用型號 MultiSelect 可搜尋、可多選、以 Chip 顯示
- [ ] **手冊管理**：DropZone 拖放上傳與點擊上傳均正常
- [ ] **手冊管理**：檔案格式（僅 PDF）與大小（50MB）前端驗證
- [ ] **手冊管理**：上傳進度條正確顯示百分比
- [ ] **手冊管理**：處理狀態四種徽章顯示正確，processing 含 Spinner
- [ ] **手冊管理**：processing 狀態每 10 秒自動更新直到完成
- [ ] **手冊管理**：PDF Viewer 開啟正常，切片高亮與點擊同步
- [ ] **手冊管理**：刪除手冊含確認對話框
- [ ] **SOP 草稿**：佇列依 created_at 降序正確排列
- [ ] **SOP 草稿**：四種狀態徽章顏色正確（Gray/Amber/Emerald/Red）
- [ ] **SOP 草稿**：審核面板並排顯示正常，RWD 改為堆疊
- [ ] **SOP 草稿**：核准時自動建立知識案例 + 向量嵌入
- [ ] **SOP 草稿**：拒絕/要求修改時強制填寫審核意見
- [ ] **SOP 草稿**：審核歷程 Timeline 正確顯示
- [ ] 所有 Section 的 Loading / Error / Empty 三態完備
- [ ] RWD 三個斷點行為正確
- [ ] 表單 dirty close 保護機制（未儲存提醒）
- [ ] 頁面首次載入回應時間 < 2 秒
- [ ] 符合 Design System 視覺規範（Primary #2563EB、Accent #F59E0B、字體 Inter + Noto Sans TC）

---

## === EXCEPTION RULES ===

- PDF Viewer 使用第三方嵌入元件（如 react-pdf），樣式不受 shadcn/ui 約束
- RichTextEditor（案例表單的解決步驟欄位）使用 Tiptap 或類似編輯器，工具列樣式獨立於全域 Design System
- SOP 審核並排面板使用自訂分割線與可拖曳寬度調整，不套用標準 Grid 間距
- 手冊處理狀態 polling 機制使用 TanStack Query 的 `refetchInterval`，與全域的 staleTime 策略不同

---

## === OUTPUT REQUIREMENTS ===

### Step 1: 結構確認
列出本頁面的 sections、關鍵元件、資料流策略

### Step 2: 設計決策說明
2-3 個關鍵設計決策與理由

### Step 3: 實作方案
完整 React/Next.js 程式碼（使用 shadcn/ui + Tailwind CSS）

### 品質檢查
- [ ] 色彩系統一致性
- [ ] 字體層級正確
- [ ] 元件風格統一（shadcn/ui）
- [ ] 響應式設計完整
- [ ] 所有狀態已處理（Loading / Error / Empty / Disabled）
- [ ] 無障礙支援（鍵盤 + ARIA）
- [ ] 效能指標達標

---
執行優先順序：Global 規範 > Page 特定需求 > Exception
Assembly 日期：2026-04-21
Brand System 版本：v1.0
