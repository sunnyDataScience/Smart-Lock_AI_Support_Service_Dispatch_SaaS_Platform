# Page-Level Prompt: 工單詳情頁

> 工單全生命週期的單一真實來源 (Single Source of Truth)。整合診斷鏈、派工紀錄、對話記錄、設備狀態、完工報告、異常記錄於一頁。
> 依據 `02_smartlock_dispatch_brand_system.md` 風格 E（嵌入設備狀態面板）+ 時間軸 + 對話記錄。
>
> **同步狀態（2026-06，code wins）**：本 spec 已對齊現行前端 `web/src/app/work-orders/[id]/page.tsx` + `WorkOrderDetailSidebar.tsx` + `MediaGallery.tsx`（依 CR-0096~0109）。
> - 標 **➕ code 既有**：code 已實作、原 spec 未描述者。
> - 標 **🚧 規格先行・未實作**：原 spec 設計、code 尚未落地者（保留設計意圖，不刪）。
> - 兩者皆有但不符者：內容已改為 code 現況，關鍵差異就地註明。
>
> **資料真實 / 示意分界**（依 page 頂部 info banner 與 code 註解）：問題診斷摘要、客戶上傳媒體、工單歷程、完工報告（completion 真實欄位）、公單資訊、成本明細、指派技師為**真實資料**；SLA 時間軸（部分節點仍缺時間戳）、設備狀態面板（電量/連線/遠端操作）、報價明細（零件費/出勤費/折扣拆項）、異常記錄佔位仍標**示意**。

---

## [PAGE META]

- **page_name**: 工單詳情 (Work Order Detail)
- **route_path**: `/work-orders/[id]`
- **page_type**: detail (左主內容 + 右固定側欄 380px)
- **ia_pages**: A12
- **openapi_ops**: getWorkOrder, assignWorkOrder（:assign / :reassign）, listDispatchCandidates（dispatch:candidates）, acceptWorkOrder（:accept）, completeWorkOrder（:complete）, cancelWorkOrder（/cancel）, escalateWorkOrder（:escalate）, confirmWorkOrder（:confirm）, signWorkOrder（/signature）, proposeReschedule（/reschedule:propose）, requestReschedule（/reschedule-request）, notifyDelay（/notify-delay）, materialRequest（/material-request）, getQuoteItems（/quote-items）, downloadWorkOrderDocument（/document）, listWorkOrderMedia（/media）, setMediaLegalHold（/media/{id}/legal-hold）, listExceptionCases（/exception-cases）
- **asyncapi_ops**: subscribeWorkOrderUpdates — 🚧 規格先行・未實作（現行 code 無 WebSocket，全走 REST fetch + 手動 `setOrder` 更新）
- **primary_goal**: 讓管理員完整掌握單一工單的所有資訊，並執行對應的狀態操作（接受派工、指派/重新指派、取消、升級、電子簽章、改期、通知延遲、缺料回報、確認結案等）
- **secondary_goal**: 整合設備狀態（目前示意），回溯完整服務歷程供稽核使用；下載電子工單 PDF
- **target_users**:
  - 主要：客服主管、營運管理者（處理工單問題、審核完工）
  - 次要：品牌商管理者（查看特定案例）；技師主管（查看團隊工單）
- **entry_point**: 工單列表頁行點擊、Kanban 卡片點擊、Dashboard 工單連結、通知連結、地圖 Popup「查看詳情」
- **expected_time_on_page**: 2-10 分鐘（視工單複雜度，簡單查看 2 分鐘，異常處理可達 10 分鐘）

---

## [STRUCTURE: SECTIONS]

> **code 現況**：左側為主內容（`flex-1`，可捲動），右側為固定寬 380px 側欄（非 2/3 比例）。動態 action 按鈕列**位於 detail_header 內**（不在側欄 action_panel），側欄底部的 action_panel 為 disabled 示意佔位。

### 左側主內容區（主內容欄）

1. **detail_header** ➕ 含動態 action 按鈕列
   - section_type: page_header + SLA_timeline + contextual_actions
   - section_purpose: 工單編號（document_number / 短 id）、狀態群組 Badge、緊急度 Badge、品牌/型號/地址/關聯問題卡、SLA 時間軸、依狀態動態的操作按鈕列（接受派工/重新指派/取消/升級/電子簽章/送出改期/直接改約/通知延遲/缺料回報等）

2. **info_banner** ➕ code 既有
   - section_type: notice_banner
   - section_purpose: 提示哪些區為真實資料、哪些仍示意

3. **quote_cta** ➕ code 既有
   - section_type: link_button
   - section_purpose: 「開啟報價單」連結到 `/admin/quotes?wo={id}`（新分頁）

4. **dispatch_order_view** ➕ code 既有（`DispatchOrderView` 元件）
   - section_type: read_only_form_sections
   - section_purpose: 派工單／施工免責與合規視圖（唯讀欄位 + 模組分區：基礎資訊、設備與計費、施工免責與合規、雙方簽認狀態）；多數欄位由其他流程管理，依工單狀態顯示

5. **problem_card_summary**
   - section_type: info_card（非可摺疊，code 為常駐展開卡）
   - section_purpose: 展示 AI 診斷結果摘要（ProblemCard 核心內容）

6. **line_media_gallery**
   - section_type: media_gallery（縮圖網格 + 外連大圖；**非** issue_bundle 手風琴）
   - section_purpose: 展示客戶透過 LINE 上傳的圖片/影片（由關聯對話 messages 過濾 image/video）
   - 註：原 spec 的 issue_bundle 手風琴結構、filter_tabs、AI 分析區塊、下載/轉傳/分享操作 → code 未實作，詳見該 Section spec 內 🚧 標記

7. **work_timeline**
   - section_type: vertical_timeline
   - section_purpose: 由 WorkOrder 時間戳衍生的歷程（建立/排程/到場/完工/最後更新）

8. **conversation_thread**
   - section_type: embedded_chat（唯讀）
   - section_purpose: 顯示關聯對話 messages（user/assistant/system 三角色氣泡）

9. **completion_report**
   - section_type: detail_card
   - section_purpose: 完工真實資料（完工時間、完工狀態、實收金額、施工摘要、功能測試逐項）

10. **exception_records**
    - section_type: list_cards（非手風琴）
    - section_purpose: 撈 M15 exception-cases（依 work_order_id），顯示異常類型/嚴重度/狀態/描述/時間

### 右側側邊欄（固定 380px，`WorkOrderDetailSidebar`）

11. **device_status_panel**
    - section_type: device_info_card
    - section_purpose: 鎖具品牌/型號（真實）+ 電量/連線/最近操作（示意 —）+ 遠端開鎖/重置密碼（disabled 示意）

12. **quotation_card**
    - section_type: pricing_card
    - section_purpose: 估價（estimated_reward，真實）+ 零件費/出勤費/折扣拆項示意提示

13. **cost_detail_panel** ➕ code 既有（CR-0027）
    - section_type: pricing_card
    - section_purpose: 後台成本拆項（quote-items；unit_price 僅後台可見）+ 「下載電子工單 PDF」按鈕

14. **work_order_fields_panel** ➕ code 既有（CR-0026/0043/0047，快照標題「公單資訊」）
    - section_type: info_card
    - section_purpose: 標準化案件欄位（客戶姓名/聯絡電話/服務類別/問題類型/保固/門型/安裝環境/付款方式/完工狀態/狀態原因等）

15. **customer_info_card**
    - section_type: info_card
    - section_purpose: 客戶名稱/電話（真實）+ LINE ID 獨立列 + 地址 + 查看完整對話連結（CR-0102 修正）

16. **technician_info_card**
    - section_type: info_card
    - section_purpose: 指派技師 Avatar/姓名/星等/電話/技能（真實 fetch）；未指派顯示替代文字

17. **action_panel** — 🚧 規格先行・未實作（側欄此處為 disabled 佔位）
    - section_type: contextual_actions（disabled）
    - section_purpose: 側欄底部「標記異常」按鈕為 disabled +「派工模組接入後可執行操作」。**實際可用的 contextual actions 在 detail_header 按鈕列**（見 §detail_header）

---

## [SECTION COMPONENT SPEC]

### Section: detail_header

- **layout**: 全寬（主內容欄寬度），垂直排列，白色背景 + 底部 border
- **elements**:
  - breadcrumb: 一行小字 / 「首頁 > 工單管理 > 工單列表 > {document_number 或短 id}」（`text.caption`，`color.text.secondary`）
    - 註：code 為純文字 breadcrumb（非可點擊麵包屑連結）；返回功能由下方 back_button 提供
  - header_row: 水平排列，垂直置中，gap `space.3`：
    - back_button: IconButton / ChevronLeft icon / 連結回 `/work-orders`
    - wo_number: H1 (28px, 700) / required / 等寬字體（font-mono）/ 顯示 `order.document_number ?? id.slice(0,8)`，hover title 為完整 id
      - 差異：code 顯示後端產生的 `document_number`（如 `TP-000185`）或短 id，**非** spec 的 `WO-YYYYMMDD-XXXX` 固定格式
    - status_badge: 狀態群組 Badge / required / 用 `STATUS_GROUP_MAP` 把 status 映射為群組（如 assigned → 「已派工」），配色取自 `STATUS_GROUP_TONE`：
      - padding 水平 8px / 垂直 4px，font-size 14px，font-weight 600，`radius.sm`
      - 差異：顯示的是**狀態群組名稱**（非 13 細狀態原文）
    - urgency_badge: 緊急度 Badge ➕ code 既有 / 用 `URGENCY_TONE` 配色 / 「緊急度：{label}」
    - copy_icon: Copy icon ➕ 目前為純圖示，**尚未綁定複製動作**（無 onClick / Toast）— 🚧 複製工單編號互動未實作
  - meta_row: 一行 wrap 資訊列 ➕ code 既有：品牌 / 型號 / 地址（district · address）/ 關聯問題卡連結（`/problem-cards/{pc_id}`，font-mono）
  - sla_timeline_bar: SLA 水平時間軸 / required（`SlaTimeline` 元件，CR-0100 真實化）：
    - 容器：`flex flex-col gap-2`，背景 `--bg-page`，`radius.lg`，padding `space.3` (12px)
    - 節點序列（6 節點，由 `order.status` + 時間戳衍生，**非寫死**）：建立 → 派工 → 接受 → 進行中 → 完工 → 確認
      - status rank 映射：inquiring(0) → assigned(1) → accepted(2) → in_progress(3) → completed(4) → closed(5)
      - 每個節點：上方圓點（已完成=綠實心 3px / 當前=primary 外框環 / 未達=灰邊空心）、下方階段名稱（11px）、再下方真實時間 `MM/DD HH:mm`（10px，僅有時間欄位的節點顯示）
      - 時間欄位來源：建立=`created_at`、派工=`scheduled_time`、進行中=`actual_arrival`、完工=`completion_time`；**接受/確認目前無時間戳**（accepted_at / closed_at 未上 envelope）→ 該兩節點只有圓點與名稱，無時間 🚧 缺時間欄位
    - sla_countdown: 節點列下方右對齊一行 ➕ 用 computed `sla_deadline`：
      - 正常：`剩餘 {N}h{MM}m`，`color.warning`，font-weight 600
      - 逾時：`逾時 {N}h{MM}m`，`color.error`，font-weight 600
      - 終態（completed/billed/paid/closed/cancelled）或無 `sla_deadline` → 不顯示倒數
      - 差異：code **無 pulse 動畫**；正常態用 warning 橙色而非 secondary 灰色
    - progress_bar: 最底部水平進度條（高 8px，`--border` 軌道 + `--primary` 填充），寬度 = lastReached / 5 的百分比；已結案=100%；取消=0%
      - 差異：填充色固定 primary（**不依 SLA 三態變橙/紅**）
  - action_buttons_row: 動態操作按鈕列 ➕ code 既有（依工單狀態 from-set 過濾顯示）：
    - 接受派工（accept）：status ∈ {assigned} / primary 藍 / CheckCircle2 icon
    - 重新指派 / 手動指派（assign）：status ∈ {inquiring, assigned}（assign）或 {accepted, in_progress}（reassign）/ outline 藍 / UserPlus icon / 有技師時顯示「重新指派」否則「手動指派」
    - 取消工單（cancel）：status ∈ 多數進行中狀態 / outline 紅 / X icon
    - 升級工單（escalate）：status ∈ 多數進行中狀態 / outline 橙 / Flag icon
    - 確認結案（confirm）：status ∈ {completed} / 實心藍綠 #0EA5E9 / Star icon
    - 電子簽章（signature）：status ∈ {accepted..completed} / outline 紫 #7C3AED / PenLine icon
    - 送出改期（reschedule，多時段提案）：status ∈ 排程相關 / outline #0EA5E9 / CalendarClock icon
    - 直接改約（requestReschedule）：status ∈ 排程相關 / outline 靛 #4338CA / CalendarClock icon
    - 通知延遲（notifyDelay）：**常駐顯示** / outline 橙 #B45309 / TriangleAlert icon
    - 缺料回報（materialRequest）：**常駐顯示** / outline 綠 #065F46 / Upload icon
    - 各按鈕點擊後開對應 Modal（accept 為直接 POST）；pending 時全列 disabled
    - action_error：按鈕列下方紅色錯誤條（API 失敗時顯示 errorCode + status + message）
- **states**:
  - default: 顯示編號 + 狀態群組 Badge + 緊急度 Badge + meta 列 + SLA 時間軸 + 動態按鈕列
  - loading: 「載入工單中…」文字（code 為簡單文字提示，非 Skeleton）— 🚧 Skeleton 未實作
  - sla_overdue: 倒數文字轉紅色 bold（無 pulse）
  - completed/closed: 進度條全滿，節點全綠，不顯示倒數
  - cancelled: 進度條歸 0，僅「建立」節點綠，其餘 pending
  - error: 主內容區頂部紅色錯誤條「載入工單失敗：{error}」
- **copy_constraints**: 工單編號顯示 document_number 或 8 字短碼；狀態群組名稱簡短

> 🚧 規格先行・未實作（detail_header）：複製工單編號互動、SLA pulse 逾時動畫、SLA 三態進度條變色、節點白色勾號 / ring 動畫、異常分支標記、loading Skeleton。

---

### Section: problem_card_summary

- **layout**: 全寬常駐展開卡片（**非可摺疊**），白色背景，`border` + `radius.xl`，padding `px-8 py-5`
  - 差異：code 為固定展開卡，無 header 點擊摺疊；資料由 `pcId`（order.problem_card_id）fetch `/problem-cards/{pcId}`
- **elements**:
  - card_header: 水平排列（不可點擊摺疊）：
    - icon: FileText icon，`color.primary`
    - title: 「問題診斷摘要」(20px, 600)
    - badge: 「ProblemCard」/ `--primary-light` 背景 + primary 文字
    - pc_link: ➕ 右側 / 「{pcId 前 8 碼} →」font-mono 連結到 `/problem-cards/{pcId}`
  - status_row: ➕ code 既有（card 載入後）：
    - pc_status_badge: 圓角 Badge / 用 `PC_STATUS_TONE`（draft 靛 / confirmed 藍 / resolved 綠）/ 顯示問題卡狀態
    - urgency_badge: 緊急度 Badge / 用 `URGENCY_TONE`
    - confidence_score: 小字 / optional / 「AI 信心度 {score}%」（`confidence_score * 100` 取整）
  - attributes_grid: Grid **4 欄**（code 為 `grid-cols-4`，非 2x2）/ 每格 `--bg #F1F5F9` 圓角：
    - 品牌（brand）、型號（model）、類別（category）、關聯對話（conversation_id 短碼，連結到 `/conversations/{id}`）
    - 差異：欄位為 品牌/型號/類別/關聯對話（**非** 安裝年份/問題類型/保固期）；空值顯示 `—`
  - symptom_summary: 區塊 / `--bg #F8FAFC` 圓角：
    - label: 「症狀描述」（11px，secondary）
    - content: 症狀全文（13px，line-height 1.6）；空值顯示 `—`
- **states**:
  - default: 常駐展開顯示 header + status_row + grid + 症狀
  - no_pc（無 problem_card_id）: 「(無關聯問題卡提示文字)」灰字
  - loading: 「載入中…」文字（非 Skeleton）
  - error: 紅字「載入失敗：{error}」
- **copy_constraints**: 症狀描述全文顯示（code 未截斷）；grid value 隨內容換行

> 🚧 規格先行・未實作（problem_card_summary）：可摺疊互動、resolution_level（解決層級 Badge）、diagnostic_chain（Symptom→Failure→FailureMode→Defect 流程圖）、症狀 500 字截斷「顯示更多」、Skeleton。
> ➕ code 既有：pc_status_badge、urgency_badge、關聯對話連結、關聯問題卡連結。

---

### Section: line_media_gallery

- **layout**: 全寬卡片，白色背景，padding `px-8 py-5`
- **section_purpose**: 展示客戶透過 LINE 上傳的圖片/影片
- **code 現況（重要差異）**：此頁主內容的媒體區由 page.tsx 內部元件 `LineMediaGallery` 渲染，**資料來源是關聯對話的 messages**（`/conversations/{conversation_id}/messages?limit=100`，conversation_id 來自 problem_card），前端過濾出 `type ∈ {image, video} 且有 media_url` 的訊息。**不是** spec 設計的 issue_bundle API（`/work-orders/{id}/media` bundles）。整個 issue_bundle 手風琴 / filter_tabs / AI 分析 / 下載打包 / 轉傳 / 分享 結構 code 皆未實作。
- **visibility_rule**: code 為**常駐顯示 Section**（即使無媒體也顯示卡片 + 空狀態提示），**非** spec 的「全空則整段隱藏」
- **elements（code 現況）**:
  - section_header: 水平排列：
    - icon: Images icon，`color.primary`
    - title: 「客戶上傳媒體」(20px, 600)
    - source_badge: 「LINE」Badge / `--primary-light` 背景 + primary 文字（純文字，**無** LINE 品牌 icon）
    - count_summary: 有媒體時顯示「{count}」筆數小字（非 spec 的 圖片/影片/檔案 細分）
  - media_grid: `flex flex-wrap gap-3` 縮圖列：
    - media_thumbnail: 128x128px，`radius.lg`，border，外層為 `<a target="_blank">` 直接連到 `media_url`（**新分頁開原圖**，非 lightbox）：
      - **圖片項**: `<img>` object-cover；hover 輕微放大（scale 1.03）；無遮罩 / 無 ZoomIn icon
      - **影片項**: 灰底 + 居中「影片」文字標籤（**無**首幀預覽 / PlayCircle / 時長 Badge / 內嵌播放器）
      - 縮圖下方：上傳時間 `YYYY/MM/DD HH:mm`（11px）
      - title（hover tooltip）：「提交時間 {time}」
- **states（code 現況）**:
  - no_conversation（無關聯對話）: 虛線框「(無關聯對話提示)」
  - loading: 虛線框「載入中…」
  - empty（有對話、無 image/video 訊息）: 虛線框「客戶尚未上傳任何媒體」
  - error: 紅框「載入失敗：{error}」
  - default: 顯示縮圖網格
- **copy_constraints**: 時間格式 `YYYY/MM/DD HH:mm`

> 🚧 規格先行・未實作（line_media_gallery）— 以下原 spec 設計 code 全未落地，保留設計意圖：
> - issue_bundle 手風琴（bundle_header / bundle_meta / media_count_badges / ai_insight_badge / 展開摺疊）
> - filter_tabs（全部/圖片/影片/Issue 包）
> - 影片首幀預覽 + PlayCircle + 時長 Badge + 內嵌播放器 Modal（play/pause/seek/音量/倍速/下載）
> - 檔案項 / 語音項（mini 波形 + audio player）
> - 縮圖 index 序號 Badge、source_tag（初次報修/補充說明/AI 追問）
> - Lightbox（與 conversation_thread 共用、左右鍵切換）
> - ai_analysis_block（關鍵字 Chip、→ 關聯 ProblemCard 跳轉高亮、影像識別品牌/型號信心度）
> - bundle_actions（下載此包 .zip / 轉傳給技師 / 複製分享連結）
> - media_expired（LINE 30 天保存期遮罩）、backed_up CloudCheck 標記
> - 「全空整段隱藏」visibility_rule（code 改為常駐 Section + 空狀態提示）

> ➕ code 既有但屬另一元件（CR-0109 legal_hold，**尚未接入本頁**）：
> `web/src/components/work-orders/MediaGallery.tsx` 是另一個獨立媒體元件，讀 `/work-orders/{id}/media`（依 purpose 分組：門面前/門面後/完工前/完工後/客戶證據/技師證據/其他），含：
> - 縮圖左上 purpose 分類標籤、底部檔案大小 + 時間
> - **法務保留 🔒 徽章**（CR-0109）：`legal_hold` 為真時縮圖右上顯示「🔒 保留」amber 徽章
> - **鎖/解 toggle**：admin/tenant_admin/super_admin/operations_manager/reviewer 角色（`LEGAL_HOLD_ROLES`）可見「鎖定/解除」按鈕 → `PATCH /tenants/{tid}/media/{id}/legal-hold { hold }`
> - lightbox（點縮圖開全螢幕預覽）、依 purpose 分組 grid（3-4 欄）、重新整理按鈕
> **但此元件目前未被工單詳情頁 import**（grep 確認 0 引用）；現於 disputes 等場景使用。若未來把 legal_hold / purpose 分組媒體接入本頁，應取代或合併現行 `LineMediaGallery`。

---

### Section: work_timeline

- **layout**: 全寬垂直時間軸，白色背景卡片，padding `px-8 py-6`
- **code 現況（差異）**：歷程**由 `WorkOrder` 上的時間戳欄位衍生**（`buildEvents`），**非** 獨立 timeline 分頁 API。事件種類固定：建立（created_at）、排程（scheduled_time）、到場（actual_arrival）、完工（completion_time）、最後更新（updated_at，且 ≠ created_at 時）。
- **elements（code 現況）**:
  - section_header: 「工單歷程」(20px, 600) / 右側「全部」篩選下拉 — **disabled**（tooltip「即將推出」）🚧 篩選未實作
  - timeline_list: 垂直排列，左側 2px 軸線：
    - 每個 TimelineItem：
      - node_circle: 圓形 12px，背景依事件類型固定色：建立/最後更新=Slate #94A3B8、排程=Rose #F43F5E、到場=Blue #3B82F6、完工=Emerald #10B981
      - actor_badge: 小 Badge（badge tone）：系統（slate）/ 技師（blue）/ 排程（rose）/ 完工（emerald）
      - event_title: 14px, 600：「工單建立」/「已排程」/「技師到場」/「完工」/「最後更新」（i18n key）
      - event_detail: optional 12px secondary：
        - 建立：「由問題卡 {pc 短碼} 衍生」（有 problem_card_id 時）
        - 排程：有技師「(已指派技師 {tech 短碼})」/ 無技師「(未指派)」
        - 最後更新：「目前狀態：{status}」
      - timestamp: 11px disabled，格式 `YYYY/MM/DD HH:mm`
    - 排序：按時間**降序**（最新在上）
- **states（code 現況）**:
  - default: 顯示衍生事件（降序）
  - empty: 虛線框「(尚無歷程提示)」
- **copy_constraints**: 事件標題簡短

> 🚧 規格先行・未實作（work_timeline）：篩選下拉（狀態變更/派工記錄/系統事件）、狀態變更逐筆事件（old→new）、派工匹配 match_score + match_factors（距離/技能/評分/負荷 4 Badge）、異常事件項、event_attachments、「載入更多」分頁、WebSocket 即時插入滑入動畫、點擊展開完整備註、Skeleton。
> 差異說明：現行歷程為「由工單時間戳衍生」的精簡版，非完整事件流；timestamp 格式為 `YYYY/MM/DD HH:mm`（無秒）。

---

### Section: conversation_thread

- **layout**: 全寬卡片，白色背景，padding `px-8 py-5`
- **code 現況**：讀關聯對話 messages（`/conversations/{conversation_id}/messages?limit=100`），API 依 created_at DESC 回傳，前端 reverse 為正序（舊→新）顯示。角色為 `user`（客人）/ `assistant`（客服/AI）/ `system`（系統）。
- **elements（code 現況）**:
  - section_header: 「LINE 對話記錄」(20px, 600) / 右側「在新視窗開啟」連結（ExternalLink icon → `/conversations/{conversation_id}` 新分頁）
  - chat_container: 嵌入式聊天視圖 / max-height 420px，垂直捲動，背景 `--bg-page`：
    - message_bubble:
      - 客戶（user）訊息：左對齊，白底氣泡 + border，`rounded-2xl`，max-width 78%
      - 客服/AI（assistant）訊息：右對齊，`--primary` 藍底白字氣泡
      - 系統（system）訊息：居中灰色 pill（`#E2E8F0` 背景）
    - 每個氣泡上方：「{角色}・{YYYY/MM/DD HH:mm}」（11px secondary）
    - 氣泡內：訊息文字（whitespace-pre-wrap）；若有 media_url → 氣泡內附「(附件)」底線連結（新分頁開啟），**非**內嵌縮圖
  - read_only_indicator: 底部灰色橫條 / Lock icon +「唯讀模式 — 此為 LINE 對話備份」
- **states（code 現況）**:
  - default: 正序顯示對話
  - no_conversation: 虛線框「(無關聯對話提示)」
  - loading: 虛線框「載入中…」
  - empty: 虛線框「尚無對話訊息」
  - error: 紅框「載入失敗：{error}」
- **copy_constraints**: 單則訊息完整顯示（無截斷）

> 🚧 規格先行・未實作（conversation_thread）：圖片/影片訊息內嵌縮圖 + Lightbox + 「在客戶媒體區檢視」跳轉、影片首幀 + PlayCircle + 時長 Badge + 內嵌播放器、檔案訊息（下載按鈕）、語音訊息（波形 + audio player）、Quick Reply Chip 群組、Flex Message 卡片渲染、「↓ 回到最新」浮動按鈕、Skeleton。
> 差異說明：現行附件統一以「(附件)」文字連結呈現（新分頁開原檔）；技師訊息未獨立配色（並入 assistant）。

---

### Section: completion_report

- **layout**: 全寬卡片，白色背景，padding `px-8 py-5`；**code 為常駐 Section**（未完工時顯示空狀態，非整段隱藏）
- **visibility_rule**（code 現況）: 永遠渲染卡片。內部以 `done` 判斷是否完工：`completion_time` 存在 或 status ∈ {completed, billed, paid, closed}
- **code 現況（CR-0100 真實化）**：完工資料直接取自 `WorkOrder` envelope 上的真實欄位，未完工誠實顯示空狀態，不再顯示寫死的假測試結果。
- **elements（code 現況）**:
  - section_header: ClipboardCheck icon（success 綠）+「完工報告」(20px, 600) / 右側完工時提交時間「提交時間：{completion_time}」
  - 未完工（!done）: 虛線框「(尚未完工提示)」
  - 已完工（done）顯示真實欄位：
    - completion_status: 「完工狀態」label + `order.completion_status` 原值（有值才顯示）
    - customer_final_amount: 「實收金額」label + `${order.customer_final_amount}`（有值才顯示，bold）
    - completion_summary: 「施工摘要」label + `order.completion_summary`（技師 notes 抽出，whitespace-pre-wrap）；空則「(無摘要)」
    - function_tests: 「功能測試」label + 逐項列表（有 `order.function_tests` 陣列才顯示）：
      - 每項：結果符號 + 測項中文標籤 + 結果文字
      - 結果符號/色：pass=「✓」綠、fail=「✗」紅、na=「—」灰
      - 測項標籤映射（`FUNCTION_TEST_LABEL`）：fingerprint=指紋解鎖、password=密碼解鎖、card=卡片(RFID)、app=App/藍牙、mechanical_key=機械鑰匙、battery=電池電壓
- **states（code 現況）**:
  - not_completed: 空狀態提示框
  - completed: 顯示真實完工欄位（依各欄位有值才渲染）
- **copy_constraints**: 摘要 whitespace-pre-wrap 完整顯示

> ➕ code 既有：completion_status、customer_final_amount、completion_summary、function_tests 逐項真實結果。
> 🚧 規格先行・未實作（completion_report）：
> - photos_gallery 現場照片 Gallery + Lightbox + 照片分類標籤（維修前/中/後）
>   - 註：完工照片有上傳/驗證機制（CR-0096 後端 ≥3 硬閘 + 「施工中」格、CR-0107 雙簽名板），但**完工報告區尚未把照片以分類縮圖呈現**；相關 purpose 分組媒體展示能力在未接入的 `MediaGallery.tsx`（見 line_media_gallery §legal_hold 註）
> - service_items 服務項目表（名稱/數量/單價/小計/合計）
> - parts_used 使用零件表
> - customer_signature 簽名圖片 + 簽署人/時間（簽名動作走 detail_header「電子簽章」按鈕 → SignatureModal 雙簽名板；但完工報告區尚未回顯簽名圖）
> - satisfaction_rating 滿意度 5 星 + 評分文字 + 客戶備註（評分動作走「確認結案」ConfirmModal；報告區尚未回顯）
> - rework_required 返工 Alert
> - Skeleton

---

### Section: exception_records

- **layout**: 全寬卡片，白色背景，padding `px-8 py-5`；**code 為常駐 Section**（無異常顯示空狀態提示，非整段隱藏）
- **code 現況**：撈 M15 exception-cases API（`/exception-cases?work_order_id={id}`），以**簡單列表卡片**呈現（**非**可展開手風琴 / **非**按 5 種類型分區內容）。
- **elements（code 現況）**:
  - section_header: TriangleAlert icon（error 紅）+「異常記錄」(20px, 600)
  - exception_list: 每個異常一張小卡（border + `--bg-page`）：
    - severity_dot: 左側 8px 圓點，依 severity 配色（`EXCEPTION_SEVERITY_COLOR`）：critical/high=error 紅、medium=warning 橙、low=secondary 灰
    - exception_type: 13px 600 / 中文標籤（`EXCEPTION_TYPE_LABEL`）：no_show=放鴿子、customer_absent=客戶不在、scope_change_rejected=加價拒絕、material_shortage=缺料、delay_severe=嚴重延遲、appearance_refused=拒絕施工、payment_failed=付款失敗、quality_complaint=品質客訴、schedule_conflict=排班衝突、other=其他
    - status: 右側 11px disabled / 原始 `status` 字串
    - description: optional 12px secondary / 異常描述
    - created_at: 11px disabled / `YYYY/MM/DD HH:mm`
- **states（code 現況）**:
  - loading: 虛線框「載入中…」
  - empty: 虛線框「(尚無異常提示)」（**非**整段隱藏）
  - default: 異常列表
- **copy_constraints**: 描述完整顯示

> 🚧 規格先行・未實作（exception_records）：手風琴展開/摺疊、依 5 種類型（scope_change/material_request/complaint/dispute/refund）展開不同內容區塊（原始/變更範圍、價格影響、零件清單、投訴/爭議/退款明細）、異常數量 Badge、未解決左邊框高亮、Skeleton。
> 差異說明：現行異常分類用 M15 exception_type 列舉（與 spec 5 類不同）；呈現為扁平列表卡，未做類型化展開內容。

---

### Section: device_status_panel（風格 E — 側邊欄頂部）

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4` (16px)
- **code 現況**：僅 **brand/model 為真實**（取自 WorkOrder），其餘指標與遠端操作全為**示意 / disabled**。
- **elements（code 現況）**:
  - device_image: 鎖具圖示佔位區（高 160px，`#F8FAFC` 背景，居中圓形 + 🔒 emoji 32px）— 🚧 真實鎖具圖片未實作
  - device_model: 20px 600 / 「{brand} {model}」（真實）
  - device_serial: 12px secondary / `S/N: {serial_number}`（有值才顯示）否則「S/N： —（示意）」
  - metric_cards: 3 張小指標卡（**整組 opacity 70，全示意**）：
    - battery_card: 灰邊圓 + 「—」/ label「電量（示意）」
    - connectivity_card: 灰圓點 + 「—」/ label「連線（示意）」
    - last_operation_card: Clock icon + 「—」/ label「最近操作（示意）」
  - quick_actions: 2 顆按鈕（**皆 disabled**，tooltip「即將推出」）：
    - remote_unlock_button: LockOpen icon +「遠端開鎖」/ accent 底 opacity 60 disabled
    - reset_password_button: Key icon +「重置密碼」/ outline opacity 60 disabled
- **states（code 現況）**:
  - default: brand/model 真實，指標 + 操作全示意/disabled
- **copy_constraints**: 型號名稱顯示完整

> 🚧 規格先行・未實作（device_status_panel）：真實鎖具圖片、電量圓環（綠/黃/紅梯度 + pulse）、連線狀態燈（在線/離線/連線中）、最近操作相對時間、遠端開鎖 / 重置密碼（二次確認 + API + Toast + 新密碼顯示）、設備離線 overlay、low_battery 警示、no_device 狀態、Skeleton。
> 差異說明：現行所有設備即時指標與遠端操作均為示意佔位，等設備整合模組接入後才真實化。

---

### Section: customer_info_card（CR-0102 修正）

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **code 現況（CR-0102 修正）**：display_name 來自關聯對話、phone 為工單 `customer_phone`、line_user_id 獨立標示**不當電話**。
- **elements（code 現況）**:
  - card_title: 16px 600 / 「客戶資訊」（載入失敗時右側紅色「(載入失敗)」Badge）
  - customer_name: 14px 600 / `conversation.display_name`（空則 `—`）
  - phone_number: Phone icon + 13px / `customer_phone`；**為空時顯示「未提供」灰字**（絕不拿 line_user_id 充當電話 — CR-0102 修正重點）
  - line_id_row: ➕ code 既有 / MessageCircle icon + 「LINE ID {line_user_id 前 12 碼…}」font-mono（line_user_id 存在才顯示，獨立列，**非電話**）
  - address: MapPin icon + 13px / 工單 `address`（純文字顯示，**非** Google Maps 連結）
  - view_conversation_link: 「查看完整對話 →」連結到 `/conversations/{conversation_id}`
- **states（code 現況）**:
  - no_conversation: 「(無關聯對話提示)」灰字
  - loading: 「載入中…」
  - error: 「(載入失敗)」Badge + 錯誤文字
  - default: 顯示客戶資訊
- **copy_constraints**: line_user_id 截前 12 碼 + 「…」（hover title 為完整 ID）

> ➕ code 既有：LINE ID 獨立列（CR-0102 修正，避免 line_user_id 被誤讀為電話）、查看完整對話連結。
> 🚧 規格先行・未實作（customer_info_card）：地址點擊開 Google Maps、risk_level_badge（一般/VIP/高風險）、preferred_technician 偏好技師、order_history_link 歷史工單連結、Skeleton。

---

### Section: technician_info_card

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **code 現況**：有 `technician_id` 時真實 fetch `/technicians/{id}`。
- **elements（code 現況）**:
  - card_title: 16px 600 / 「指派技師」
  - technician_avatar: 40px 圓形色塊（依 id hash 取 `AVATAR_PALETTE` 配色，**非**真實頭像圖）
  - technician_name: 14px 600 / `technician.name`
  - rating_stars: 5 星 / 16px / 依 `Math.floor(rating)` 填充 accent 色，其餘灰
  - rating_number: 12px secondary / `rating.toFixed(1)`（**無** 評價則數）
  - phone_row: Phone icon + font-mono 13px / `technician.phone`
  - skill_badges: Badge 群組 / 技能（取前 5 個）/ `#F1F5F9` 背景
  - unassigned_state: 無 technician_id 時 / 「(尚未指派提示)」灰字（**無** UserPlus icon / 「手動指派」按鈕——指派按鈕在 detail_header）
- **states（code 現況）**:
  - default: 顯示技師資訊
  - unassigned: 顯示未指派文字
  - loading: 「載入中…」
  - error: 「(載入失敗)」Badge + `#{id 前 8 碼}` + 錯誤文字
- **copy_constraints**: 技能取前 5 個

> 🚧 規格先行・未實作（technician_info_card）：真實頭像圖、評價則數、mini_map（技師/工單位置 + 路線）、distance_info 距離、contact_button 聯繫技師、技師離線狀態、Skeleton。
> 差異說明：未指派時不在側欄提供指派入口，改由 detail_header「手動指派/重新指派」按鈕統一處理。

---

### Section: quotation_card

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **code 現況**：僅顯示**估價（estimated_reward，真實）**一行 + 零件費/出勤費/折扣拆項示意提示。
- **elements（code 現況）**:
  - card_title: 16px 600 / 「報價明細」
  - estimate_row: 「估價」label + `formatPrice(estimated_reward)`（font-mono，`NT$ X,XXX`；空值 `—`）
  - info_hint: Info icon + 灰底提示「零件費 / 出勤費 / 折扣明細將於派工計費模組接入後顯示。」
- **states（code 現況）**:
  - default: 顯示估價 + 提示
- **copy_constraints**: 金額格式 `NT$ X,XXX`

> 🚧 規格先行・未實作（quotation_card）：完整 price_breakdown（工資/零件費/出勤費/加急費/折扣/合計）、payment_status（待報價/待付款/已付款/已退款/部分退款）、payment_method、invoice_link 發票、payment_overdue、Skeleton。
> 差異說明：細項報價拆項待派工計費模組；現行僅呈現估價單值。完整成本拆項見下方 ➕ cost_detail_panel。

---

### Section: cost_detail_panel ➕ code 既有（CR-0027）

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **section_purpose**: 後台成本拆項（讀 `/work-orders/{id}/quote-items`），快照標題「成本明細」
- **elements（code 現況）**:
  - card_title: 16px 600 / 「成本明細」/ 右側：若任一品項 `is_mock` 為真 → amber「(示意)」Badge
  - line_items: 每行：`{item_name} ×{quantity}`（左）+ 後台單價 `(內部) {unit_price}`（中，僅 unit_price 存在時，**僅後台可見**）+ 客戶價 `formatPrice(customer_price)`（右，font-mono）
  - final_row: border 分隔 / 「最終金額」+ `formatPrice(customer_final_amount)`
  - cost_hidden_note: `cost_visible` 為 false 時顯示成本隱藏小字
  - download_document_button: 「下載電子工單 PDF」按鈕 → `api.download('/work-orders/{id}/document')`（檔名 `work-order-{id}.pdf`）
- **states（code 現況）**:
  - empty: 「(尚無成本拆項提示)」（快照：「尚未建立成本拆項」）
  - loading: 「載入中…」
  - error: 錯誤文字
  - default: 拆項列表 + 最終金額 + 下載按鈕
- **copy_constraints**: 金額 font-mono；unit_price 僅後台角色可見（客戶端不顯示）

---

### Section: work_order_fields_panel ➕ code 既有（CR-0026 / 0043 / 0047，快照標題「公單資訊」）

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **section_purpose**: 標準化案件欄位（有值才顯示該行；`WorkOrderFieldsPanel`）
- **elements（code 現況，依序，有值才 push）**:
  - 客戶姓名（customer_name）、聯絡電話（customer_phone）— CR-0043 Tier①
  - 服務類別（service_category）：install=安裝 / warranty_in=保內 / warranty_out=保外 / repair=維修
  - 問題類型（problem_type）
  - 保固（warranty_status）：in_warranty=保固內 / out_warranty=保固外 / not_applicable=不適用
  - 保固到期日（warranty_expiry_date，CR-0047 自動算）
  - 門型（door_type）、門厚（door_thickness）、購買地點/經銷商（dealer）、安裝日期（install_date）
  - 安裝環境（rain_exposure）：indoor=室內 / outdoor_covered=室外有遮雨 / outdoor_exposed=室外無遮雨
  - 付款方式（payment_method）：cash=現金 / bank_transfer=轉帳 / credit_card=刷卡 / line_pay=LINE Pay
  - 特殊門型加價（special_door_surcharge 為真時顯示「是」）
  - 完工狀態（completion_status）：pending_report=待完工回報 / pending_photos=待照片 / pending_customer_confirm=待客戶確認 / pending_cs_review=待客服審核 / completed=已完工 / closed=已結案
  - 狀態原因（status_reason）
- **states（code 現況）**:
  - empty: 「(無欄位提示)」
  - default: label / value 兩欄列表（label 左 secondary，value 右 600）
- **copy_constraints**: value 右對齊，可換行

---

### Section: action_panel

- **code 現況（重要差異）**：實際可用的 contextual actions **位於 detail_header 的動態按鈕列**（見 §detail_header `action_buttons_row`），由各 from-set 依工單 status 過濾顯示；**側欄底部的 action_panel 卡片為 disabled 佔位**（單顆「標記異常」disabled +「派工模組接入後可執行操作」）。

#### 側欄 action_panel（disabled 佔位）— 🚧 規格先行・未實作

- **layout**: 側邊欄底部卡片，白色背景，`radius.lg`，`shadow.sm`，border-top 2px
- mark_issue_button: TriangleAlert icon +「標記異常」/ accent 底 opacity 60 **disabled**（tooltip「即將推出」）
- hint_text: 「派工模組接入後可執行操作」

#### detail_header 動態 action 按鈕列（code 現況真正可用）

按鈕由各 from-set 依工單 status 過濾（7 值狀態流：inquiring/assigned/accepted/in_progress/completed/closed/cancelled，及完整報價列舉的中間態）：

| 按鈕 | 顯示條件（from-set） | 樣式 / icon | 行為 |
|---|---|---|---|
| 接受派工 | {assigned} | primary 藍 / CheckCircle2 | 直接 `POST :accept` |
| 手動指派 / 重新指派 | {inquiring, assigned}（assign）或 {accepted, in_progress}（reassign） | outline 藍 / UserPlus | 開 AssignModal；有技師→「重新指派」；reassign 走 `:reassign`（不破壞 wo_id），其餘走 `:assign` |
| 取消工單 | 多數進行中狀態（CANCEL_FROM） | outline 紅 / X | 開 CancelModal（6 階段取消 v2，ADR-0102/FR-0052；含 reason_code/initiator_role/X-Approver SoD/goodwill_waiver） |
| 升級工單 | 多數進行中狀態（ESCALATE_FROM） | outline 橙 / Flag | 開 EscalateModal（operations_manager / tenant_admin）走 `:escalate` |
| 確認結案 | {completed} | 實心 #0EA5E9 / Star | 開 ConfirmModal（5 星評分 + 回饋）走 `:confirm` |
| 電子簽章 | {accepted..completed}（SIGNATURE_FROM） | outline 紫 #7C3AED / PenLine | 開 SignatureModal（客戶 + 技師雙簽名板 base64 + 選填 GPS）走 `/signature` |
| 送出改期 | 排程相關（RESCHEDULE_FROM） | outline #0EA5E9 / CalendarClock | 開 RescheduleModal（1-3 時段提案 + 客戶訊息 + 通道）走 `/reschedule:propose`（CR-0007） |
| 直接改約 | 排程相關（RESCHEDULE_FROM） | outline 靛 #4338CA / CalendarClock | 開 RequestRescheduleModal（單一新時間 + 原因）走 `/reschedule-request` |
| 通知延遲 | **常駐** | outline 橙 #B45309 / TriangleAlert | 開 NotifyDelayModal（延遲 5-300 分 + 原因）走 `/notify-delay` |
| 缺料回報 | **常駐** | outline 綠 #065F46 / Upload | 開 MaterialRequestModal（品牌/型號/數量 1-20 項 + 緊急度 now/today/tomorrow + 備註）走 `/material-request` |

- **states（code 現況）**:
  - default: 依 status 顯示對應按鈕（通知延遲 / 缺料回報常駐）
  - action_pending: 點擊後該批按鈕全 disabled（`actionPending !== null`）
  - action_success: 底部置中綠色 Toast（2.4s 自動消失）+ `setOrder` 更新（header / SLA / 按鈕列重算）
  - action_failure: 按鈕列下方紅色錯誤條（errorCode + status + message）
- **copy_constraints**: 按鈕文字簡短

> 🚧 規格先行・未實作（action_panel 設計差異）：
> - 側欄 sticky bottom action panel（現為 disabled 佔位）
> - 「催促技師」（spec assigned CTA）— code 無此按鈕（改以通知延遲 / 重新指派）
> - 「標記異常」（spec in_progress 主操作）— 側欄按鈕 disabled；異常實際透過缺料回報 / 升級 / 取消等專門按鈕
> - 「要求返工」「恢復進行中」「歸檔」「進入仲裁」「查看爭議詳情」— code 未提供
> - 各狀態的 info_text / Alert 區塊（已取消 / 已歸檔 / 爭議中 / 返工中說明）
> - permission_denied tooltip、Skeleton、WebSocket 即時刷新（現為 setOrder 同步更新）
>
> ➕ code 既有（spec 原未涵蓋）：升級工單、電子簽章（雙簽名板 + GPS）、送出改期（多時段提案）、直接改約、通知延遲、缺料回報。

---

## [INTERACTION & STATE FLOW]

> **code 現況總述**：頁面用 React `useState` + `useEffect`（**非 TanStack Query / Zustand**）。主工單一次 GET，各子區塊各自獨立 fetch；無 WebSocket，所有更新靠 action handler 的 `setOrder(res.data)` 同步。全端點為 **tenant-scoped v2**（`tenantPath()` 注入 `/tenants/{tid}` 前綴）。

### 主要互動流程（code 現況）

1. **頁面載入**：
   - 從 URL 取得 `[id]` → GET `tenantPath(/work-orders/{id})` → `setOrder`
   - 子區塊各自 fetch：ProblemCardSummary（`/problem-cards/{pc_id}`）、LineMediaGallery + ConversationThread（`/conversations/{conv_id}/messages`）、ExceptionRecords（`/exception-cases?work_order_id=`）、側欄（technician / conversation / quote-items）
   - **無 WebSocket 連線**

2. **狀態操作（detail_header 按鈕列）**：
   - 點擊按鈕 → accept 直接 POST；其餘開對應 Modal
   - 各 handler 走專屬 tenant-scoped 端點（見下表），**非** 統一 `PATCH /status`
   - 成功 → `setOrder(res.data)`（或部分端點回非 envelope 時重新 GET）+ 底部綠色 Toast + 關閉 Modal
   - 失敗 → 按鈕列下方紅色 actionError 條 + 按鈕恢復

3. **指派 / 重新指派**：
   - 開 AssignModal → GET `tenantPath(/dispatch:candidates?work_order_id=)` 載入候選（含 score / skill_match / distance_km / eta）
   - 選技師 + reason_code（必填）+ reason_text → reassign 走 `:reassign`（reason 必填），其餘走 `:assign`

4. **取消（CancelModal）**：6 階段取消 v2 — reason_code + initiator_role + X-Approver（SoD 覆核，必填且須異於發起人）+ goodwill_waiver → `POST /tenants/{tid}/work-orders/{id}/cancel`，回 CancellationResult（費用拆項 Toast），本地標記 status=cancelled

5. **完工 / 確認 / 簽章**：
   - 完工 CompleteModal（摘要必填 + 實收金額選填）→ `:complete`
   - 確認 ConfirmModal（5 星 + 回饋）→ `:confirm`
   - 簽章 SignatureModal（客戶 + 技師雙簽名板上傳 base64 + 選填 GPS）→ `/signature`

6. **設備遠端操作**：🚧 未實作（device panel 按鈕 disabled）

7. **瀏覽客戶上傳媒體**：
   - 由關聯對話 `conversation_id` → GET `/conversations/{id}/messages?limit=100` → 前端過濾 image/video 顯示縮圖
   - 點縮圖 → **新分頁開啟原圖**（非 Lightbox / 非打包下載 / 非轉傳）

8. **對話記錄瀏覽**：GET messages（reverse 為正序）顯示；附件以「(附件)」連結新分頁開啟；「在新視窗開啟」→ `/conversations/{id}`

9. **異常記錄**：GET `/exception-cases?work_order_id=` → 扁平列表卡（無手風琴展開）

10. **改期 / 延遲 / 缺料**：
    - 送出改期 RescheduleModal（1-3 時段 + 客戶訊息 + 通道）→ `/reschedule:propose`
    - 直接改約 RequestRescheduleModal → `/reschedule-request`（回非 envelope，重新 GET）
    - 通知延遲 NotifyDelayModal（5-300 分）→ `/notify-delay`
    - 缺料回報 MaterialRequestModal（1-20 項）→ `/material-request`

11. **下載電子工單 PDF**：側欄 cost_detail 「下載電子工單 PDF」→ `api.download(/work-orders/{id}/document)`

> 🚧 規格先行・未實作（互動）：WebSocket 即時更新、標記異常 Modal、要求返工、遠端設備操作、媒體 Lightbox / 打包下載 / 轉傳給技師、ai_analysis 跳轉高亮、conversation 圖片跳轉媒體區、異常手風琴展開。

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop | 左主內容（flex-1）+ 右固定側欄 380px | code 現況：側欄寬度固定 380px（`w-[380px] flex-shrink-0`），**非** 2/3 比例；側欄自身 overflow-auto |
| Tablet / Mobile | 🚧 規格先行・未實作 | code 為固定雙欄佈局，**未見** BottomSheet / 單欄堆疊 / sticky bottom action panel / ProblemCard 摺疊等 RWD 分支 |

### 資料更新策略（code 現況）

- **狀態管理**：React `useState` + `useEffect`（**非** TanStack Query / Zustand）
- **工單主資料**：頁面載入 GET 一次；action 成功後 `setOrder(res.data)` 就地更新
- **子區塊**：各元件 useEffect 內獨立 fetch（problem-card / messages / exception-cases / technicians / quote-items）
- **無 WebSocket、無輪詢**

> 🚧 規格先行・未實作（資料策略）：TanStack Query staleTime / window-focus refetch、WebSocket 即時推送（status_changed / timeline_added / exception_created / device.status_updated / technician.location_updated / media_added）、設備/技師位置輪詢、Zustand client state。

---

## [DATA & API]

- **uses_api**: true
- **endpoint 慣例（code 現況）**：除少數標明者外，全走 `tenantPath()` 注入的 **tenant-scoped v2** 路徑（`/tenants/{tid}/...`）。狀態轉移用 RPC 風格 `:verb`（如 `:accept`），非 `PATCH /status`。回應多為 `WorkOrderEnvelope = { data: WorkOrder }`。
- **endpoints（code 實際呼叫）**:
  - GET `tenantPath(/work-orders/{id})` — 工單主資料 → `WorkOrderEnvelope`（WorkOrder 含 document_number / status / brand / model / address / district / customer_name / customer_phone / serial_number / scheduled_time / actual_arrival / completion_time / completion_status / completion_summary / customer_final_amount / function_tests[] / estimated_reward / service_category / problem_type / warranty_status / sla_deadline / problem_card_id 等）
  - GET `tenantPath(/problem-cards/{pc_id})` — 問題卡 → `ProblemCardEnvelope`（brand / model / category / symptom / urgency / status / confidence_score / conversation_id）
  - GET `tenantPath(/conversations/{conv_id})` — 對話主檔 → `ConversationEnvelope`（display_name / line_user_id）
  - GET `tenantPath(/conversations/{conv_id}/messages?limit=100)` — 對話訊息 → `MessagePage`（items: Message[]，含 role / content / media_url / type / created_at）；media 區與對話區共用此端點
  - GET `tenantPath(/exception-cases?work_order_id={id})` — M15 異常案件 → `{ items: ExceptionCaseItem[] }`（exception_type / status / severity / description / created_at）
  - GET `tenantPath(/technicians/{id})` — 技師 → `TechnicianEnvelope`（name / phone / rating / skills[]）
  - GET `tenantPath(/work-orders/{id}/quote-items)` — 成本拆項 → `{ items: QuoteLineItem[], customer_final_amount, cost_visible }`（item_name / quantity / customer_price / unit_price / is_mock）
  - GET（download）`tenantPath(/work-orders/{id}/document)` — 電子工單 PDF（`api.download`）
  - GET `tenantPath(/dispatch:candidates?work_order_id={id})` — 候選技師 → `{ candidates: CandidateItem[], total }`（technician / score / distance_km / skill_match / availability_eta_minutes）
  - POST `tenantPath(/work-orders/{id}:accept)` — 接受派工 → `WorkOrderEnvelope`
  - POST `tenantPath(/work-orders/{id}:assign)` — 指派 / Body `{ technician_id, reason_code, reason_text? }`
  - POST `tenantPath(/work-orders/{id}:reassign)` — 強制改派（accepted/in_progress，不破壞 wo_id）/ Body `{ technician_id, reason }`（reason 必填）
  - POST `tenantPath(/work-orders/{id}:complete)` — 完工 / Body `{ summary, actual_amount?, photos_before:[], photos_after:[] }`
  - POST `tenantPath(/work-orders/{id}:confirm)` — 確認結案 / Body `{ rating, feedback? }`
  - POST `tenantPath(/work-orders/{id}:escalate)` — 升級 / Body `{ level: 'operations_manager'|'tenant_admin', reason }`
  - POST `tenantPath(/work-orders/{id}/signature)` — 雙簽名 / Body `SignaturePayload { customer_signature, technician_signature, signed_at, gps_lat?, gps_lng? }` → `ApiResponseGeneric`
  - POST `tenantPath(/work-orders/{id}/reschedule:propose)` — 多時段改期提案（CR-0007）/ Body `{ proposed_slots:[{start,end}], message_to_customer, send_via }`（回 proposal 紀錄，非 work_order）
  - POST `/tenants/{tid}/work-orders/{id}/cancel` — 6 階段取消 v2 / Body `{ reason_code, initiator_role, goodwill_waiver, note? }` + Headers `X-Initiator` / `X-Approver`（SoD）→ `CancellationResult { cancellation_stage, customer_fee, travel_fee, technician_penalty, reason_code, audit_event_id }`
  - POST `/tenants/{tid}/work-orders/{id}/reschedule-request` — 直接改約 / Body `{ new_scheduled_at, reason }`（回 dict，前端重新 GET 工單）
  - POST `/tenants/{tid}/work-orders/{id}/notify-delay` — 通知延遲 / Body `{ delay_minutes, reason }`
  - POST `/tenants/{tid}/work-orders/{id}/material-request` — 缺料回報 / Body `{ items:[{brand,model,quantity}], urgency, note? }` → `WorkOrderEnvelope`
  - PATCH `tenantPath(/media/{id}/legal-hold)` — 法務保留 toggle（CR-0109）/ Body `{ hold }` — ➕ 由 `MediaGallery.tsx` 使用；**此工單詳情頁尚未接入**（見 line_media_gallery §legal_hold 註）
  - GET `tenantPath(/work-orders/{id}/media)` — purpose 分組媒體（門面/完工/證據）→ `{ items: MediaItem[] }`（含 purpose / legal_hold）— ➕ 由 `MediaGallery.tsx` 使用；**本頁主內容媒體區改用對話 messages**，此端點未在本頁呼叫

> 🚧 規格先行・未實作 endpoints（原 spec 設計，code 未呼叫）：`/timeline`（分頁歷程）、`/exceptions`（工單內嵌異常，改用 M15 `/exception-cases`）、`/conversation`（改用 `/conversations/{id}/messages`）、issue_bundle `/media`（bundles）+ bundle download/forward、`/completion-report`、統一 `PATCH /status`、`/notify-technician`（催促）、`/devices/{id}/*`（遠端開鎖 / 重置密碼 / 設備狀態）。

- **WebSocket Events**: 🚧 規格先行・未實作 — 現行 code **無任何 WebSocket**。原 spec 設計事件（status_changed / timeline_added / exception_created / device.status_updated / technician.location_updated / media_added）全保留為未來目標。
- **error_cases（code 現況）**:
  - 各 fetch / action 失敗 → 對應區塊紅色錯誤條，格式 `{errorCode} ({status})：{message}`（ApiError）
  - 主工單載入失敗 → 主內容頂部紅色「載入工單失敗：{error}」
  - action 失敗 → detail_header 按鈕列下方 actionError 條 + 按鈕恢復
  - 子區塊（problem-card / messages / exception-cases / technician / quote-items）失敗 → 各自區塊內錯誤提示，不影響其他區塊
- **error_cases — 🚧 規格先行・未實作**：401 導登入、403 導回列表、404 全頁狀態、409 自動 refetch、500 重試按鈕、WebSocket 斷線 Banner、設備操作失敗 / 離線 Toast（這些統一錯誤處理尚未細分；目前一律以區塊紅字呈現）。

---

## [EXCEPTION TO GLOBAL RULES]

- **對話記錄自訂氣泡**：conversation_thread 使用自訂聊天氣泡（user 左白底 + border / assistant 右藍底 / system 居中 pill），模擬 LINE 對話風格 ✅ code 既有
- **SLA 逾時 pulse 動畫**：🚧 規格先行・未實作（code SLA 逾時僅紅色文字，無 pulse）
- **設備狀態圓環圖**：🚧 規格先行・未實作（device panel 全示意，無圓環圖）
- **Sidebar sticky 行為**：差異 — code 側欄為固定寬 380px（`flex-shrink-0`）+ 自身 overflow-auto，**非** `position: sticky`
- **多 WebSocket 訂閱**：🚧 規格先行・未實作（現行無任何 WebSocket）

---

## [ACCEPTANCE CRITERIA]

> **驗收 vs code 現況（2026-06）**：以下 checklist 為**完整設計目標**，包含尚未實作的 🚧 項目。實作完成度請對照各 Section spec 內的「code 現況 / 🚧 規格先行・未實作」標記。
> - **已可驗收（code 現況支援）**：detail_header 編號/狀態群組/緊急度 Badge、SLA 6 節點真實時間軸、動態 action 按鈕列（接受/指派/取消/升級/確認/簽章/改期/改約/延遲/缺料）、ProblemCard 摘要（品牌/型號/類別/對話/症狀/信心度）、客戶上傳媒體縮圖（對話 image/video）、工單歷程（時間戳衍生）、對話記錄、完工報告真實欄位（completion_status/實收金額/摘要/function_tests）、異常列表（M15）、側欄 device/quotation/cost_detail/公單資訊/customer/technician、下載電子工單 PDF。
> - **🚧 尚不可驗收（規格先行）**：所有 SLA pulse / 三態變色 / 節點 ring 動畫、media issue_bundle 手風琴 / Lightbox / 影片播放器 / 下載打包 / 轉傳 / AI 分析、timeline 篩選 / match_factors / WebSocket 即時、conversation 內嵌縮圖 / Quick Reply / Flex、completion 照片分類 / 服務項目 / 零件 / 簽名回顯 / 滿意度、exception 手風琴 / 5 類型展開、device 圓環 / 連線燈 / 遠端操作、customer Google Maps / 風險等級 / 歷史工單、technician mini_map / 距離 / 聯繫、quotation 完整拆項 / 付款狀態 / 發票、催促技師 / 標記異常 / 要求返工 / 進入仲裁、Skeleton、RWD BottomSheet / 單欄堆疊、無障礙 focus trap 等。
>
> ➕ code 既有但原 checklist 未列（補驗收）：升級工單、電子簽章（雙簽名板 + GPS）、送出改期（1-3 時段）、直接改約、通知延遲、缺料回報、6 階段取消（SoD X-Approver）、cost_detail 成本拆項、公單資訊欄位、客戶 LINE ID 獨立列（CR-0102）、media legal_hold（CR-0109，於 `MediaGallery.tsx`，尚未接入本頁）。

### 功能驗收 — 左側主內容

- [ ] Header：工單編號正確顯示（等寬字體；code 顯示 document_number 或 8 字短碼，非 WO-YYYYMMDD-XXXX）
- [ ] Header：狀態群組 Badge 顯示正確配色（code 為狀態群組，非 13 細狀態原文）
- [ ] Header：SLA 6 節點時間軸正確渲染（建立/派工/接受/進行中/完工/確認 + 真實時間戳，接受/確認無時間戳）
- [ ] Header：🚧 SLA 三態（正常/警告/逾時）視覺 — code 僅逾時紅字，無三態進度條變色
- [ ] Header：🚧 複製工單編號功能 — code Copy icon 未綁定動作
- [ ] ProblemCard：摺疊/展開切換正確
- [ ] ProblemCard：症狀描述、domain_attributes、resolution_level、diagnostic_chain 正確顯示
- [ ] ProblemCard：診斷鏈 Symptom→Failure→FailureMode→Defect 流程圖正確
- [ ] ProblemCard：信心度分數顏色梯度正確
- [ ] LINE Media Gallery：工單無媒體時整個 Section 隱藏（不顯示 empty placeholder）
- [ ] LINE Media Gallery：issue 包手風琴展開/摺疊正確（允許同時多個展開）
- [ ] LINE Media Gallery：bundle_header 的觸發訊息摘要、提交時間、媒體數量 Badge（圖片/影片/檔案/語音）正確
- [ ] LINE Media Gallery：source_badge「LINE」與 count_summary 顯示正確
- [ ] LINE Media Gallery：filter_tabs（全部/圖片/影片/Issue 包）切換正確；過濾後全空時顯示提示
- [ ] LINE Media Gallery：圖片縮圖 hover 遮罩 + ZoomIn icon 正確
- [ ] LINE Media Gallery：影片縮圖首幀 + PlayCircle + 時長 Badge 正確
- [ ] LINE Media Gallery：檔案/語音縮圖 icon + 副檔名/波形顯示正確
- [ ] LINE Media Gallery：source_tag（初次報修/補充說明/AI 追問）配色與位置正確
- [ ] LINE Media Gallery：點擊圖片開啟 Lightbox（與 conversation_thread 共用），左右鍵切換正確
- [ ] LINE Media Gallery：點擊影片開啟內嵌播放器 Modal（播放/暫停/seek/音量/倍速 0.5-2x/下載）
- [ ] LINE Media Gallery：AI 分析區塊顯示關鍵字 Chip 群組正確
- [ ] LINE Media Gallery：「→ 關聯 ProblemCard」連結點擊後平滑捲動並高亮 2s
- [ ] LINE Media Gallery：影像識別結果顯示品牌/型號與信心度（色彩梯度正確）
- [ ] LINE Media Gallery：「下載此包 (.zip)」Loading → signed URL → 下載流程正確
- [ ] LINE Media Gallery：「轉傳給技師」二次確認 + LINE Push + Toast 正確
- [ ] LINE Media Gallery：「複製分享連結」複製 signed URL + Toast 正確
- [ ] LINE Media Gallery：媒體過期狀態（LINE 30 天保存期且未備份）縮圖遮罩 + tooltip 正確
- [ ] LINE Media Gallery：已備份至 GCS 的媒體顯示 CloudCheck 標記
- [ ] Conversation：圖片/影片氣泡的「在客戶媒體區檢視」可跳轉至 line_media_gallery 並高亮對應縮圖
- [ ] Timeline：歷程按時間降序正確排列
- [ ] Timeline：每個事件的節點顏色、actor_badge、事件標題正確
- [ ] Timeline：派工記錄顯示 match_score 和 match_factors 明細
- [ ] Timeline：篩選功能正常（狀態變更/派工記錄/系統事件）
- [ ] Timeline：WebSocket 新事件即時插入（滑入動畫 + 高亮）
- [ ] Timeline：「載入更多」分頁正確
- [ ] Conversation：LINE 對話正確渲染（客戶左側、Bot 右側）
- [ ] Conversation：圖片訊息可點擊 Lightbox 放大
- [ ] Conversation：Quick Reply / Flex Message 特殊訊息正確顯示
- [ ] Conversation：捲動時「回到最新」按鈕正確顯示/隱藏
- [ ] Conversation：唯讀模式標示正確
- [ ] Completion Report：僅在 completed/confirmed/archived/rework_required 狀態顯示
- [ ] Completion Report：照片 Gallery 縮圖 + Lightbox 正確
- [ ] Completion Report：服務項目、零件列表、合計正確
- [ ] Completion Report：功能測試結果 CheckCircle/XCircle 正確
- [ ] Completion Report：客戶簽名圖片正確顯示
- [ ] Completion Report：滿意度 5 星評分正確
- [ ] Exception Records：手風琴展開/摺疊正確
- [ ] Exception Records：5 種異常類型（scope_change, material_request, complaint, dispute, refund）內容正確
- [ ] Exception Records：未解決異常紅色左邊框

### 功能驗收 — 右側 Sidebar

- [ ] Device Panel：brand/model 真實顯示 + 🔒 佔位圖
- [ ] Device Panel：🚧 電量圓環 / 連線狀態燈 / 最近操作 / 遠端開鎖 / 重置密碼 / 離線 overlay — 全為示意/disabled
- [ ] Customer Card：客戶名稱 + 電話（空顯「未提供」）+ LINE ID 獨立列（CR-0102）+ 地址 + 查看完整對話連結
- [ ] Customer Card：🚧 地址開 Google Maps / 風險等級 Badge / 查看歷史工單
- [ ] Technician Card：Avatar 色塊 + 姓名 + 星等 + rating + 電話 + 技能 Badge（前 5）
- [ ] Technician Card：🚧 mini_map / 距離 / 聯繫技師 / 真實頭像 / 評價則數
- [ ] Quotation Card：估價（estimated_reward）顯示正確 + 拆項示意提示
- [ ] Quotation Card：🚧 完整 price_breakdown / 付款狀態 / 發票連結
- [ ] ➕ Cost Detail：成本拆項（quote-items，unit_price 僅後台可見）+ 最終金額 + 下載電子工單 PDF
- [ ] ➕ 公單資訊：服務類別/問題類型/保固/門型/安裝環境/付款方式/完工狀態/狀態原因等標準化欄位
- [ ] Action 按鈕列（detail_header）：依 status 顯示對應按鈕（from-set 過濾）正確
- [ ] Action 按鈕列：pending 時全列 disabled；成功 Toast + setOrder；失敗紅色錯誤條
- [ ] Action：手動指派 / 重新指派 開 AssignModal（候選技師 + reason_code）正確
- [ ] Action：接受派工（直接 POST :accept）正確
- [ ] Action：取消工單（6 階段 + X-Approver SoD + goodwill_waiver）正確
- [ ] ➕ Action：升級工單（operations_manager / tenant_admin）正確
- [ ] ➕ Action：電子簽章（客戶 + 技師雙簽名板 base64 + GPS）正確
- [ ] ➕ Action：送出改期（1-3 時段提案）/ 直接改約（單一新時間）正確
- [ ] ➕ Action：通知延遲（5-300 分）/ 缺料回報（1-20 項）正確
- [ ] Action：確認結案 ConfirmModal（5 星 + 回饋）正確
- [ ] 🚧 Action：催促技師 / 標記異常 / 要求返工 / 進入仲裁 — code 未提供（側欄「標記異常」disabled）
- [ ] 🚧 Action：cancelled / archived info_text / Alert 區塊

### 狀態驗收

- [ ] Empty 狀態：ProblemCard 無資料、Conversation 無對話、Media 無媒體、Exception 無異常（均顯示空狀態提示，**非整段隱藏**）
- [ ] Error 狀態：各區塊獨立紅字錯誤（格式 `errorCode (status)：message`）
- [ ] 🚧 Loading Skeleton：code 為文字「載入中…」提示，無 Skeleton（CLS 未優化）
- [ ] 🚧 404 全頁狀態 / 401 導登入 / 403 導回列表 / 409 自動 refetch — 統一錯誤處理未細分
### 即時更新驗收 — 🚧 規格先行・未實作（現行 code 無 WebSocket）

- [ ] 🚧 WebSocket 連線建立（訂閱工單 + 設備 + 技師位置）
- [ ] 🚧 工單狀態變更即時反映（現行靠 action 後 setOrder 同步，非推送）
- [ ] 🚧 Timeline 即時新增事件（滑入動畫 + 高亮）
- [ ] 🚧 設備狀態 / 技師位置即時更新
- [ ] 🚧 客戶 LINE 新上傳媒體即時推送
- [ ] 🚧 WebSocket 斷線 Banner + 自動重連

### RWD 驗收

- [ ] Desktop：左主內容 flex-1 + 右固定側欄 380px（code 現況；**非** 2/3 + sticky）
- [ ] 🚧 Tablet：sidebar 變 BottomSheet（三段式）— 未實作
- [ ] 🚧 Mobile：單欄堆疊 + action_panel 固定底部 — 未實作

### 效能驗收

- [ ] 頁面首次載入 LCP < 2.5s
- [ ] 對話記錄 100+ 則訊息不卡頓
- [ ] 🚧 CLS < 0.1（需 Skeleton；code 目前用文字提示，未預留高度）

### 無障礙驗收

- [ ] 圖片有 alt 文字（media 縮圖、簽名板）
- [ ] 狀態群組 Badge 同時包含顏色 + 文字標籤
- [ ] 色彩對比度達 WCAG 2.1 AA
- [ ] Modal Escape 關閉（部分 Modal 點背景關閉）
- [ ] 🚧 完整 Tab 順序 / focus trap / aria-disabled tooltip — 未完整驗證

---

## T1.4 補強：候選技師手動排序 UI + 客訴升級指示器

> 🚧 **規格先行・未實作（整段 T1.4）**：以下三區塊（manual_dispatch_candidate_list 側欄候選清單拖曳排序、complaint_escalation_indicator 客訴升級指示器、dispute_link_badge 爭議連結徽章）**現行 code 皆未實作**，保留設計意圖。
> 現況對照：候選技師排序僅存在於 AssignModal 內（按 score 顯示，無拖曳排序 / 無 session 自訂順序）；客訴 / 爭議 indicator 與 banner 未在工單詳情頁呈現。
>
> 補 Flow 2 拒單重派、Flow 9 客訴升級在工單詳情頁的 UI 顯示缺口。

### [SECTION] manual_dispatch_candidate_list

**觸發**：當工單狀態為 `assigning` 或 `reassign_required`，且管理員角色具 `dispatch.manual.override` 權限，在 sidebar 展開此區塊。

#### 位置與樣式

- 位置：右側 sidebar 第三張卡（位於派工紀錄卡之後）
- 高度：最多 480px（超過內滾）
- 標題：「候選技師（手動介入）」+「進階排序」IconButton（開啟 A37 完整頁）

#### 元件

- **candidate_row**（最多顯示前 5 位，其餘「查看更多」跳 A37）
  - avatar + name + online dot
  - score_bar: 綜合分數水平進度條（0-100%）
  - quick_stats: 距離 / 評分 / 技能匹配 chips
  - quick_assign_btn: 「指派」Primary（點擊開啟 decision_reason_modal）

- **sort_switcher**（下拉）
  - 綜合分數（預設）
  - 距離
  - 評分
  - 可用性（立即 → 1 小時）

- **drag_sort_mode**（進階）
  - 開關啟用後：每列出現 drag handle，可手動拖曳排序
  - 儲存自訂順序到本 session（不跨工單）
  - 送出指派時自動帶入使用者手動順序作為決策理由的一部分

- **deep_link_to_a37_btn**：「進入完整介入頁 →」跳 A37 派工人工介入面板

#### 狀態

- `auto_dispatch_trying`: 顯示「自動派工進行中...（2/3 次）」，候選清單半透明
- `manual_mode_active`: 候選完全可用，行色 highlight
- `all_rejected_3x`: 紅色 banner「已連續 3 次拒單，建議立即指派或升級」+ 強制顯示

### [SECTION] complaint_escalation_indicator

**觸發**：工單關聯的客訴（complaint）中有 `anger_level >= 4` 或 `status in (escalated, reopened)` 時。

#### 位置與樣式

- 位置：工單 header 正下方 alert banner（全寬）
- 顏色：anger 4 → warning 橙；anger 5 或 reopened → critical 紅閃爍
- 高度：64px，可折疊為 24px 單行

#### 元件

- **severity_icon**：⚠ warning / 🔥 critical
- **complaint_ref**: 「客訴 #CMP-017 已升級」連結到 A22 / 客訴專屬視圖
- **anger_label**: 「憤怒等級 4/5」
- **elapsed_label**: 「升級已 2h 05min」（即時計時）
- **sla_countdown**: 依 Flow 9 §12.7 表計時（高 anger → 15min-4h）
- **quick_actions**:
  - 「聯絡客戶」→ 開 LINE 對話 + 記錄
  - 「升主管」→ 觸發 Flow 9 escalate
  - 「進入客訴詳情」→ A22 或專屬視圖

#### 狀態

- default: 顯示
- dismissed: 收合（僅顯示單行；重啟需重進頁）
- resolved: 變綠色「已結案」+ 3 秒後自動隱藏

### [SECTION] dispute_link_badge

**觸發**：工單關聯有 active dispute（G4 爭議）時。

- 位置：header 區域 next to status_badge
- 樣式：`⚖ 爭議處理中` 紅 Chip，點擊跳 A22 爭議詳情
- 若同時有 complaint + dispute（符合 Flow 9 補遺 §27.2）→ 兩 badge 並列，且 complaint 標記 `merged_into_dispute` 灰字

### [INTERACTION] T1.4 補

- `manual_dispatch_candidate_list` 手動拖曳排序後送出指派 → 順序進入 audit_event.metadata（透明化決策）
- `complaint_escalation_indicator` 的倒數計時過 SLA → 自動觸發 Flow 9 下一升級層級
- 爭議 / 客訴 indicator 呼叫的 quick_actions 皆須有 `Idempotency-Key`

### [DATA & API] T1.4 補

```
GET /api/v1/work-orders/{id}/candidates?limit=5
  → 同 A37 candidate API（共用）

GET /api/v1/work-orders/{id}/complaint-summary
  → { has_active_complaint, anger_level, complaint_id, escalation_level, sla_deadline }

GET /api/v1/work-orders/{id}/dispute-summary
  → { has_active_dispute, dispute_id, stage, dual_sign_pending }
```

WebSocket 訂閱同既有：`/realtime/work-orders/{id}`；新事件 `complaint.sla_warning` 可觸發 banner 閃爍。

### [ACCEPTANCE CRITERIA] T1.4

- [ ] `assigning` 狀態下 candidate_list 自動顯示 top 5
- [ ] 3 次拒單達成後紅色強制 banner
- [ ] 手動拖曳排序儲存至 session 並進入 audit_event
- [ ] anger_level >= 4 時 indicator 自動顯示
- [ ] SLA 倒數即時更新（WS 推播）
- [ ] anger 5 或 reopened 紅色閃爍動畫
- [ ] 同時存在 complaint + dispute 時兩 badge 並列顯示
- [ ] quick_actions 全部有 Idempotency-Key

### 校對檢核表（T1.4）

- [ ] sidebar 候選清單 5 位是否足夠？
- [ ] 自動 vs 手動派工切換的權限門檻（`dispatch.manual.override` 是否為新增權限碼）？
- [ ] anger_level 5 的閃爍動畫是否會干擾其他操作？
- [ ] complaint_escalation_indicator 的倒數計時過 SLA 自動升級 — 是否會與 Flow 9 主流程的升級重複？
- [ ] dispute badge 與既有 status_badge 位置是否衝突？


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
