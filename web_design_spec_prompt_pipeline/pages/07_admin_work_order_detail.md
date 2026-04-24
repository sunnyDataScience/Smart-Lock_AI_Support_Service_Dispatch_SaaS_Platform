# Page-Level Prompt: 工單詳情頁

> 工單全生命週期的單一真實來源 (Single Source of Truth)。整合診斷鏈、派工紀錄、對話記錄、設備狀態、完工報告、異常記錄於一頁。
> 依據 `02_smartlock_dispatch_brand_system.md` 風格 E（嵌入設備狀態面板）+ 時間軸 + 對話記錄。

---

## [PAGE META]

- **page_name**: 工單詳情 (Work Order Detail)
- **route_path**: `/work-orders/[id]`
- **page_type**: detail (左右雙欄)
- **ia_pages**: A12
- **openapi_ops**: getWorkOrder, assignWorkOrder, listDispatchCandidates
- **asyncapi_ops**: subscribeWorkOrderUpdates
- **primary_goal**: 讓管理員完整掌握單一工單的所有資訊，並執行對應的狀態操作（指派、催促、確認、仲裁等）
- **secondary_goal**: 整合設備即時狀態，支援遠端操作（開鎖、重置密碼）；回溯完整服務歷程供稽核使用
- **target_users**:
  - 主要：客服主管、營運管理者（處理工單問題、審核完工）
  - 次要：品牌商管理者（查看特定案例）；技師主管（查看團隊工單）
- **entry_point**: 工單列表頁行點擊、Kanban 卡片點擊、Dashboard 工單連結、通知連結、地圖 Popup「查看詳情」
- **expected_time_on_page**: 2-10 分鐘（視工單複雜度，簡單查看 2 分鐘，異常處理可達 10 分鐘）

---

## [STRUCTURE: SECTIONS]

### 左側主內容區（Left 2/3）

1. **detail_header**
   - section_type: page_header + SLA_timeline
   - section_purpose: 顯示工單編號、狀態、SLA 進度視覺化

2. **problem_card_summary**
   - section_type: collapsible_card
   - section_purpose: 展示 AI 診斷結果摘要（ProblemCard 核心內容）

3. **line_media_gallery**
   - section_type: media_gallery + issue_bundle_accordion
   - section_purpose: 集中展示客戶透過 LINE 上傳的圖片/影片與 AI 自動彙整的 issue 包（原始診斷證據）

4. **work_timeline**
   - section_type: vertical_timeline
   - section_purpose: 記錄工單完整生命週期的所有狀態變更與事件

5. **conversation_thread**
   - section_type: embedded_chat
   - section_purpose: 顯示原始 LINE 客服對話記錄（唯讀）

6. **completion_report**
   - section_type: detail_card
   - section_purpose: 完工後的服務報告（照片、零件、測試、簽名、評分）

7. **exception_records**
   - section_type: accordion_cards
   - section_purpose: 異常事件完整記錄（範圍變更、缺料、投訴、爭議、退款）

### 右側側邊欄（Right 1/3）

8. **device_status_panel**
   - section_type: device_info_card
   - section_purpose: 鎖具即時狀態與遠端操作（風格 E）

9. **customer_info_card**
   - section_type: info_card
   - section_purpose: 客戶基本資訊與聯繫方式

10. **technician_info_card**
    - section_type: info_card
    - section_purpose: 指派技師資訊與即時位置

11. **quotation_card**
    - section_type: pricing_card
    - section_purpose: 報價明細與付款狀態

12. **action_panel**
    - section_type: contextual_actions
    - section_purpose: 根據當前工單狀態顯示對應操作按鈕

---

## [SECTION COMPONENT SPEC]

### Section: detail_header

- **layout**: 全寬（佔左側 2/3 主內容區寬度），垂直排列
- **elements**:
  - breadcrumb: Breadcrumb / required / 「首頁 > 工單管理 > 工單列表 > {wo_number}」/ 「工單列表」可點擊返回
  - header_row: 水平排列，垂直置中：
    - back_button: IconButton Ghost / ChevronLeft icon / 「返回列表」tooltip / 點擊返回上一頁（保留篩選條件）
    - wo_number: H1 (`text.heading.xl` 28px, 700) / required / 等寬字體 JetBrains Mono / 格式 `WO-YYYYMMDD-XXXX` / `color.text.primary`
    - status_badge: StatusBadge lg / required / 對應 13 狀態語義色 / 大尺寸版本：
      - padding: `space.2` (8px) 水平，`space.1` (4px) 垂直
      - font-size: `text.body.md` (14px)，font-weight 600
      - border-radius: `radius.sm` (4px)
      - 背景色：對應語義色 10% 透明度
      - 文字色：對應語義色 100%
    - copy_wo_button: IconButton Ghost / Copy icon / 點擊複製工單編號 + Toast「已複製工單編號」
  - sla_timeline_bar: SLA 水平時間軸 / required / 全寬進度條：
    - 容器：高度 56px，背景 `color.bg.page` (#F8FAFC)，`radius.lg` (8px)，padding `space.3` (12px)
    - 進度軌道：高度 8px，背景 Slate 200 (#E2E8F0)，`radius.full`
    - 進度填充：左至右，顏色依當前狀態：
      - 正常進度：`color.primary` (#2563EB) 漸變填充
      - SLA 警告（<= 30min）：`color.warning` (#F59E0B) 漸變填充
      - SLA 逾時：`color.error` (#EF4444) 填充 + pulse 動畫
    - 節點標記：進度條上方等距放置狀態節點（圓形 12px）：
      - 已通過節點：填充對應語義色 + 白色勾號
      - 當前節點：填充對應語義色 + 外圈 2px ring 動畫
      - 未到達節點：灰色邊框圓圈（Slate 300）
      - 節點下方標籤：狀態名稱 (`text.caption` 11px)
      - 節點標籤之間連線：已通過=實線語義色，未到達=虛線灰色
    - 節點序列（簡化顯示主線程）：建立 → 派工 → 接受 → 進行中 → 完工 → 確認
    - 若有異常分支：在對應節點下方顯示分支標記（小三角 + 異常狀態名）
    - sla_countdown: 進度條右側：
      - 正常：`text.body.md`，`color.text.secondary`，「剩餘 HH:mm」
      - 警告：`text.body.md`，bold，`color.warning`，「剩餘 HH:mm」
      - 逾時：`text.body.md`，bold，`color.error`，「逾時 HH:mm」+ pulse
    - 時間標記：進度條下方每個已完成節點顯示時間戳 (`text.caption`)
- **states**:
  - default: 顯示工單編號 + 狀態 Badge + SLA 進度條
  - loading: Skeleton（標題長條 + 進度條橫條 + 節點圓形）
  - sla_normal: 進度條藍色，文字灰色
  - sla_warning: 進度條橙色，文字橙色 bold
  - sla_overdue: 進度條紅色 + pulse，文字紅色 bold
  - completed: 進度條全滿綠色，所有節點打勾，不顯示倒數
  - cancelled: 進度條灰色，當前節點紅色 X，後續節點灰色虛線
- **copy_constraints**: 工單編號固定格式 16 字元；狀態文字最多 4 字

---

### Section: problem_card_summary

- **layout**: 全寬可摺疊卡片（Collapsible Card），白色背景，`radius.lg`，`shadow.sm`
- **elements**:
  - card_header: 水平排列，可點擊切換展開/摺疊：
    - icon: FileText icon，`color.primary`
    - title: H3 (`text.heading.md` 20px, 600) / 「問題診斷摘要」
    - badge: Badge / 「ProblemCard」/ `color.primary` 背景 10%，Primary 文字
    - chevron: ChevronDown icon（展開時旋轉 180 度），transition 200ms
  - card_body（展開時顯示）:
    - symptom_summary: 區塊 / required：
      - label: 「症狀描述」/ `text.body.sm`，`color.text.secondary`，font-weight 600
      - content: `text.body.lg` (16px)，`color.text.primary` / 完整症狀文字描述
    - domain_attributes: 區塊 / required / Grid 2x2 佈局：
      - 每個屬性為 label + value 組合
      - label: `text.body.sm`，`color.text.secondary`
      - value: `text.body.md`，`color.text.primary`，font-weight 500
      - 典型屬性：品牌、型號、安裝年份、問題類型、是否在保固期
    - resolution_level: 區塊 / required：
      - label: 「解決層級」
      - value: Badge 格式
        - Level 1 (自助解決)：Emerald Badge
        - Level 2 (遠端協助)：Blue Badge
        - Level 3 (現場維修)：Amber Badge
    - diagnostic_chain: 區塊 / required / 水平流程圖：
      - 四個節點：Symptom → Failure → FailureMode → Defect
      - 每個節點：圓角矩形 (`radius.md`)，Slate 100 背景，padding `space.2`
      - 節點內：上方 label (`text.caption`，`color.text.secondary`)，下方 value (`text.body.sm`，`color.text.primary`，bold)
      - 節點間：箭頭 → icon，`color.text.disabled`
      - 若某個節點尚未確定：虛線邊框 + 「待確認」灰字
    - confidence_score: 右上角小字 / optional / 「AI 診斷信心度 {score}%」/ 分數 >= 80% 綠色，60-79% 橙色，< 60% 紅色
- **states**:
  - default: 摺疊狀態（僅顯示 card_header + symptom_summary 前 2 行預覽）
  - expanded: 展開顯示所有區塊
  - loading: Skeleton（標題 + 4 行文字區塊）
  - empty: 「此工單尚未產生診斷摘要」+ 灰色 FileQuestion icon
  - no_problem_card: 「手動建立的工單無診斷資料」灰字
- **copy_constraints**: 症狀描述最多 500 字（超出截斷 + 「顯示更多」）；每個 domain_attribute value 最多 30 字

---

### Section: line_media_gallery

- **layout**: 全寬卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.6` (24px)
- **section_purpose**: 集中展示客戶透過 LINE 上傳的所有媒體資料（圖片、影片、檔案、語音）與 AI 自動彙整的 issue 包；作為 ProblemCard 背後的原始診斷證據，供客服/主管溯源
- **visibility_rule**: 工單關聯 `bundles` 陣列長度 > 0 時顯示；全空則整個 Section 隱藏（不顯示 empty placeholder）
- **elements**:
  - section_header: 水平排列，垂直置中：
    - icon: Images icon，`color.primary`
    - title: H3 (`text.heading.md` 20px, 600) / 「客戶上傳媒體」
    - source_badge: Badge sm / 「LINE」/ `color.primary.light` (#DBEAFE) 背景 + Primary 文字 + LINE icon
    - count_summary: `text.body.sm`，`color.text.secondary` / 「共 {total} 筆（{photo_count} 圖片・{video_count} 影片・{file_count} 檔案）」
    - filter_tabs: 右側 / Tabs 切換：「全部 / 圖片 / 影片 / Issue 包」/ 預設「全部」
  - issue_bundles: IssueBundle[] / required / 垂直排列手風琴卡片，gap `space.4` (16px)：
    - 每個 bundle 代表一次完整的客戶報修事件（觸發訊息 + 附帶媒體 + AI 彙整結果）
    - 同一工單可能有多個 bundle（例如：初次報修包、補充說明包、AI 追問後的補件包）
    - bundle_header: 水平排列，可點擊展開/摺疊，Slate 50 (#F8FAFC) 背景，`radius.md`，padding `space.3` (12px)：
      - bundle_icon: Package icon / `color.primary` / 24px / 左側
      - bundle_meta: 垂直排列，flex-grow：
        - trigger_text: `text.body.md` (14px)，font-weight 600，`color.text.primary` / 觸發訊息摘要（客戶首條文字訊息），超出截斷，最多 60 字
        - submitted_at: `text.caption` (11px)，`color.text.secondary` / 「提交時間 YYYY-MM-DD HH:mm」
      - media_count_badges: 水平 Badge 群組 / 中右：
        - photo_badge: 「{n} 張」+ Camera icon / Slate 背景 / 若 n=0 不顯示
        - video_badge: 「{n} 支」+ Video icon / Slate 背景 / 若 n=0 不顯示
        - file_badge: 「{n} 檔」+ FileText icon / Slate 背景 / 若 n=0 不顯示
        - audio_badge: 「{n} 則」+ Mic icon / Slate 背景 / 若 n=0 不顯示
      - ai_insight_badge: Badge sm / optional / 「AI 已分析」+ Sparkles icon / Emerald 背景 / 表示該包已產生 ProblemCard
      - chevron: ChevronDown icon（展開時旋轉 180 度），transition 200ms
    - bundle_body（展開時顯示）:
      - trigger_full_text: 完整觸發訊息 / `text.body.md`，`color.text.primary`，預留換行；超過 500 字時顯示「顯示全文」切換
      - media_grid: 縮圖網格 / required / CSS grid，`grid-template-columns: repeat(auto-fill, minmax(128px, 1fr))`，gap `space.2` (8px)：
        - media_thumbnail: 統一 128x128px，`radius.md`，object-fit cover，position relative，overflow hidden：
          - **圖片項**: 直接顯示縮圖；hover 時覆蓋半透明黑色遮罩 (rgba(0,0,0,0.3)) + ZoomIn icon（白色，24px）；點擊開啟 Lightbox（與 conversation_thread 共用 lightbox 元件）
          - **影片項**: 顯示首幀靜態預覽（背景圖）；中央覆蓋 PlayCircle icon（40px，白色 + `shadow.md`）；右下角覆蓋時長 Badge 「MM:SS」黑色半透明 (rgba(0,0,0,0.6)) 背景 + 白字 `text.caption`；點擊開啟內嵌影片播放器 Modal（max-width 960px，元件含 play/pause/seek/音量/倍速 0.5x-2x/下載）
          - **檔案項**: Slate 100 背景，中央顯示 FileText icon (40px，`color.primary`)；下方小字顯示副檔名（如「PDF」「DOCX」）；點擊觸發下載
          - **語音項**: Slate 100 背景，中央顯示 Mic icon (40px)；底部 mini 波形條；時長 Badge 於右下角；點擊開啟 audio player 浮層（含 play/pause/seek）
          - 縮圖左上角：index 序號 Badge（黑色半透明底 + 白字 `text.caption`，如「#1」）
          - 縮圖右上角：source_tag Badge / `text.caption`：
            - 「初次報修」(initial): Primary 背景
            - 「補充說明」(supplementary): Amber 背景
            - 「AI 追問」(ai_followup): Emerald 背景
        - 縮圖下方：`text.caption`，`color.text.secondary` / 檔名（含副檔名）；若無則 fallback「{type}_{index}」
      - ai_analysis_block: optional / 僅在 `ai_analysis` 存在時顯示：
        - 容器：Emerald 50 背景，left border 3px Emerald (#10B981)，`radius.md`，padding `space.3`
        - header: Sparkles icon + 「AI 自動分析」/ `text.body.sm`，font-weight 600，Emerald 700
        - extracted_keywords: Chip 群組 / 從媒體抽取的症狀/部件關鍵字（最多 8 個）/ 白色背景 + Emerald 邊框 + `text.caption`
        - linked_problem_card: Link / `text.body.sm` / 「→ 關聯 ProblemCard #{id}」/ 點擊頁面平滑捲動至 problem_card_summary 並高亮背景 2s（Primary light 漸淡）
        - vision_identified_model: `text.body.sm` / optional / 「影像識別：{brand} {model}（信心度 {score}%）」/ 信心度 >= 80% 綠色，60-79% 橙色，< 60% 紅色
      - bundle_actions: 水平按鈕列 / 右側對齊，gap `space.2`：
        - download_bundle_button: Button Secondary sm / icon Download / 「下載此包 (.zip)」/ 點擊 → POST 打包 API → Loading → 成功取得 signed URL 觸發瀏覽器下載
        - forward_to_technician_button: Button Secondary sm / icon Send / 「轉傳給技師」/ 點擊 → 二次確認 Modal「將此 issue 包推送至當前指派技師 {name} 的 LINE？」→ 成功 Toast
        - copy_link_button: IconButton Ghost / icon Link / tooltip「複製分享連結」/ 點擊 → 複製 signed URL → Toast
- **states**:
  - default: 所有 issue 包摺疊（僅顯示 bundle_header）
  - expanded: 點擊單個 bundle 展開；允許同時多個展開
  - loading: Skeleton（3 個 bundle_header 灰條，最上一個展開顯示 media_grid 8 格縮圖灰塊）
  - video_playing: 影片播放器 Modal 開啟，背景頁面灰色 overlay，Escape 可關閉
  - audio_playing: 語音浮層於縮圖下方展開，不遮擋其他媒體
  - lightbox_open: Lightbox 開啟，支援左右鍵切換（含同一 bundle 中所有圖片項）；Escape 關閉
  - download_in_progress: download_bundle_button → Spinner + 「打包中...」Disabled
  - download_failed: Toast Error「媒體打包失敗：{reason}，請稍後再試」+ 按鈕恢復
  - forward_in_progress: forward_to_technician_button → Spinner + Disabled
  - forward_success: Toast Success「已轉傳給技師 {name}」
  - media_expired: LINE 原始媒體超過 30 天（LINE 官方保存期）且尚未備份至 GCS 時，縮圖覆蓋灰色半透明 + ImageOff icon + tooltip「媒體已過 LINE 保存期，原始檔不可用」；已備份者正常顯示
  - backed_up_indicator: 已備份至 GCS 的媒體，縮圖右下角小 CloudCheck icon（灰色 12px）
  - filter_applied: 切換「圖片/影片/Issue 包」tabs 時，非對應類型縮圖隱藏；若過濾後該 bundle 無匹配媒體則 bundle 整體隱藏；全部隱藏則 Section 顯示「目前篩選無資料」灰字
  - empty: 此 Section 整體隱藏（透過 visibility_rule）
- **copy_constraints**: 觸發訊息摘要最多 60 字；完整觸發訊息超 500 字顯示「顯示全文」；影片/語音時長格式「MM:SS」（> 1 小時則「HH:MM:SS」）；檔名最多 24 字（超出中間截斷 `filename...ext`）

---

### Section: work_timeline

- **layout**: 全寬垂直時間軸，白色背景卡片，`radius.lg`，`shadow.sm`，padding `space.6` (24px)
- **elements**:
  - section_header: H3 / 「工單歷程」/ 右側：篩選下拉（全部 / 狀態變更 / 派工記錄 / 系統事件）
  - timeline_list: TimelineItem[] / required / 垂直排列，左側時間軸線：
    - 時間軸線：2px 寬，`color.border.default` (#E2E8F0)，左側 margin 20px
    - 每個 TimelineItem：
      - node_circle: 圓形 12px，背景依事件類型：
        - 狀態變更：對應目標狀態語義色
        - 派工記錄：`color.primary` (#2563EB)
        - 系統事件：Slate 400 (#94A3B8)
        - 異常事件：`color.error` (#EF4444)
      - timestamp: `text.caption` (11px)，`color.text.secondary`，格式「YYYY-MM-DD HH:mm:ss」
      - actor_badge: Badge sm：
        - 「系統」：Slate 背景
        - 「管理員 {name}」：Primary 背景
        - 「技師 {name}」：Blue 背景
        - 「客戶」：Amber 背景
      - event_title: `text.body.md` (14px)，font-weight 600，`color.text.primary`
        - 狀態變更：「狀態變更：{old_status} → {new_status}」
        - 派工指派：「技師指派：{technician_name}」
        - 派工匹配：「AI 匹配完成」
        - 異常觸發：「異常事件：{exception_type}」
      - event_detail: `text.body.sm` (12px)，`color.text.secondary` / optional：
        - 備註文字（管理員/技師填寫的原因）
        - 派工匹配時顯示匹配詳情：
          - match_score: 「匹配分數：{score}」
          - match_factors: 水平排列 4 個小 Badge：
            - 「距離 {distance_pct}%」
            - 「技能 {skills_pct}%」
            - 「評分 {rating_pct}%」
            - 「負荷 {load_pct}%」
          - 背景色：總分 >= 80 Emerald，60-79 Blue，< 60 Amber
      - event_attachments: optional / 附件列表（照片縮圖、文件連結）
  - load_more_button: Button Ghost / 「載入更多歷程」/ 預設顯示最近 20 筆
- **states**:
  - default: 按時間降序顯示（最新在上）
  - loading: Skeleton timeline items（圓形 + 長條 x3）
  - empty: 「尚無任何歷程記錄」+ Clock icon
  - filtered: 篩選後僅顯示對應類型事件，其他隱藏
  - live_update: WebSocket 推送新事件時，新項目從頂部滑入（300ms ease）+ 2s 高亮背景（Primary Light 漸淡）
  - expanded_detail: 點擊某個 timeline item 可展開查看完整備註與附件
- **copy_constraints**: 事件標題最多 40 字；備註最多 200 字（超出截斷 + 展開）

---

### Section: conversation_thread

- **layout**: 全寬卡片，白色背景，`radius.lg`，`shadow.sm`
- **elements**:
  - section_header: H3 / 「LINE 對話記錄」/ 右側：「在新視窗開啟」Link icon
  - chat_container: 嵌入式聊天視圖 / required / max-height 480px，垂直捲動：
    - 背景：Slate 50 (#F8FAFC)，模擬聊天視窗
    - message_bubble: 每則訊息：
      - 客戶訊息：左對齊，白色背景氣泡，`radius.lg`，max-width 70%
      - Bot/系統訊息：右對齊，`color.primary.light` (#DBEAFE) 背景氣泡，`radius.lg`
      - 技師訊息：右對齊，Emerald 10% 背景氣泡
    - 每個氣泡內：
      - sender_name: `text.caption`，`color.text.secondary`，font-weight 600
      - message_content: `text.body.md`，`color.text.primary`
      - timestamp: `text.caption`，`color.text.disabled`，右下角
    - 特殊訊息類型：
      - 圖片訊息：顯示縮圖（max-width 240px），可點擊放大（Lightbox）；氣泡右下角附小 Link icon「在客戶媒體區檢視」，點擊捲動至 line_media_gallery 並高亮對應縮圖 2s
      - 影片訊息：顯示首幀預覽（max-width 240px）+ 中央 PlayCircle icon（40px，白色+陰影）+ 右下角時長 Badge「MM:SS」（黑色半透明底）；點擊開啟內嵌播放器 Modal；同樣提供「在客戶媒體區檢視」跳轉入口
      - 檔案訊息：File icon + 檔名 + 大小 + 下載按鈕，水平排列於氣泡內
      - 語音訊息：Mic icon + 播放按鈕 + mini 波形 + 時長；點擊展開 audio player
      - Quick Reply 選擇：顯示為 Chip 群組，已選中的 Chip 高亮
      - Flex Message：簡化渲染（卡片佈局）
      - 系統事件訊息：居中灰色文字（如「對話已轉接人工客服」）
    - scroll_to_bottom: 當捲動離底部 > 200px 時，右下角顯示「↓ 回到最新」浮動按鈕
  - read_only_indicator: 底部灰色橫條 / 「唯讀模式 — 此為 LINE 對話備份」(`text.body.sm`，`color.text.disabled`)
- **states**:
  - default: 顯示完整對話記錄，可捲動瀏覽
  - loading: Skeleton 氣泡（左右交替 3-5 個）
  - empty: 「此工單無關聯對話記錄」+ MessageCircle icon
  - image_lightbox: 點擊圖片後全螢幕 Lightbox 顯示原圖，支援左右切換
  - scrolled_up: 顯示「回到最新」浮動按鈕
- **copy_constraints**: 單則訊息無截斷（完整顯示）；發送者名稱最多 15 字

---

### Section: completion_report

- **layout**: 全寬卡片，白色背景，`radius.lg`，`shadow.sm`；僅在工單狀態為 `completed`、`confirmed`、`archived` 時顯示
- **visibility_rule**: 工單 status in [`completed`, `confirmed`, `archived`, `rework_required`] 時顯示；其他狀態隱藏此 Section
- **elements**:
  - section_header: H3 / 「完工報告」/ 右側：提交時間 (`text.body.sm`，`color.text.secondary`)
  - photos_gallery: 照片區塊 / required：
    - label: 「現場照片」
    - thumbnails: 水平排列縮圖列表（每張 96x96px，`radius.md`，object-fit cover）
    - 最多顯示 6 張，超出顯示「+{count}」覆蓋層
    - 點擊縮圖 → Lightbox 全螢幕瀏覽，支援左右切換
    - 照片分類標籤：「維修前」「維修中」「維修後」（Badge 覆蓋在縮圖左上角）
  - service_items: 服務項目列表 / required：
    - label: 「服務項目」
    - 表格或列表：項目名稱 + 數量 + 單價 + 小計
    - 底部合計列
  - parts_used: 使用零件列表 / required：
    - label: 「使用零件」
    - 表格：零件名稱 + 零件編號 + 數量 + 單價 + 小計
    - 若無使用零件：「本次服務未使用零件」灰字
  - functional_test_results: 功能測試結果 / required：
    - label: 「功能測試」
    - 測試項目清單：每項為 CheckCircle (Emerald) 或 XCircle (Red) + 測試項目名稱
    - 典型項目：指紋解鎖、密碼解鎖、卡片解鎖、APP 連線、自動上鎖、電池電壓
  - customer_signature: 客戶簽名 / required：
    - label: 「客戶簽名確認」
    - 簽名圖片：max-width 320px，border 1px `color.border.default`，`radius.md`
    - 簽署人姓名 + 簽署時間
    - 若尚未簽名：「待客戶簽名」灰字 + Pending Badge
  - satisfaction_rating: 客戶滿意度 / optional：
    - label: 「客戶滿意度」
    - 5 星評分：已填星 Amber (#F59E0B)，空星 Slate 200，星星大小 24px
    - 評分文字：1=「非常不滿意」2=「不滿意」3=「一般」4=「滿意」5=「非常滿意」
    - 客戶備註：`text.body.sm`，斜體
    - 若尚未評分：「待客戶評分」灰字
- **states**:
  - default: 展開顯示所有區塊
  - loading: Skeleton（圖片方塊 + 表格列 + 簽名區塊）
  - incomplete: 部分資料尚未提交（如缺照片），缺失區塊顯示黃色 Warning 提示「技師尚未上傳現場照片」
  - rework_note: 若狀態為 `rework_required`，頂部顯示紅色 Alert「此報告需要返工修正」+ 返工原因
- **copy_constraints**: 服務項目名稱最多 30 字；零件名稱最多 20 字

---

### Section: exception_records

- **layout**: 全寬，垂直排列手風琴卡片（Accordion）；僅在工單有異常記錄時顯示
- **visibility_rule**: 工單 exceptions 陣列長度 > 0 時顯示
- **elements**:
  - section_header: H3 / 「異常記錄」/ 右側：異常數量 Badge（Red 背景白字）
  - exception_accordion: Accordion / required / 每個異常為一張可展開卡片：
    - accordion_header: 水平排列，可點擊展開/摺疊：
      - exception_type_badge: Badge md，依類型配色：
        - 「範圍變更」(scope_change)：Amber Badge
        - 「缺料申請」(material_request)：Amber Badge
        - 「客戶投訴」(complaint)：Red Badge
        - 「爭議」(dispute)：Red Badge
        - 「退款」(refund)：Red Badge
      - exception_title: `text.body.md`，font-weight 600，摘要描述
      - exception_time: `text.body.sm`，`color.text.secondary`
      - exception_status: Badge sm / 「處理中」(Amber) / 「已解決」(Emerald) / 「待處理」(Red)
      - chevron: ChevronDown icon
    - accordion_body（展開時）:
      - 依異常類型顯示不同內容區塊：
      - **scope_change（範圍變更）**：
        - 原始範圍描述
        - 變更後範圍描述
        - 變更原因
        - 價格影響：原價 → 新價（差額標示）
        - 客戶確認狀態
      - **material_request（缺料申請）**：
        - 需求零件清單（名稱 + 規格 + 數量）
        - 預計到貨時間
        - 供應商資訊
        - 當前處理狀態
      - **complaint（客戶投訴）**：
        - 投訴內容（完整文字）
        - 投訴管道（LINE / 電話 / 其他）
        - 處理紀錄（時間軸）
        - 處理結果
      - **dispute（爭議）**：
        - 爭議方（客戶 / 技師 / 雙方）
        - 爭議內容
        - 雙方陳述
        - 仲裁紀錄
        - 仲裁結果
      - **refund（退款）**：
        - 退款原因
        - 退款金額
        - 原交易資訊
        - 退款狀態（申請中 / 審核中 / 已退款 / 已拒絕）
        - 審核紀錄
- **states**:
  - default: 所有手風琴摺疊（僅顯示 header）
  - expanded: 點擊展開單一手風琴，其他保持摺疊（允許同時多開）
  - loading: Skeleton accordion items
  - empty: 此 Section 整體隱藏（不顯示空狀態）
  - unresolved_highlight: 未解決的異常卡片左側邊框 3px Red
- **copy_constraints**: 異常摘要最多 50 字；完整內容無截斷

---

### Section: device_status_panel（風格 E — 側邊欄頂部）

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4` (16px)
- **elements**:
  - device_image: 鎖具圖片 / required：
    - 容器：width 100%，aspect-ratio 4:3，背景 Slate 50，`radius.md`，居中顯示
    - 圖片：object-fit contain，max-height 160px
    - 若無圖片：顯示通用鎖具 icon 佔位（Lock icon，64px，Slate 300）
  - device_model: `text.heading.md` (20px, 600) / required / 品牌 + 型號名稱
  - device_serial: `text.body.sm`，`color.text.secondary` / optional / 序號「S/N: {serial_number}」
  - metric_cards: 3 張小指標卡片 / required / 水平 3 等分排列，gap `space.2` (8px)：
    - **battery_card**:
      - 容器：Slate 50 背景，`radius.md`，padding `space.2`，text-align center
      - icon: 電池圓環圖（SVG 圓環，36px）：
        - 圓環填充比例 = 電量百分比
        - 顏色：> 50% = Emerald (#10B981)；20-50% = Amber (#F59E0B)；< 20% = Red (#EF4444) + pulse 動畫
        - 中心文字：電量數字 `text.body.sm`，bold
      - label: 「電量」`text.caption`，`color.text.secondary`
    - **connectivity_card**:
      - 容器：同上
      - icon: 圓形狀態燈（12px）：
        - 在線：Emerald (#10B981) + 微弱光暈
        - 離線：Slate 400 (#94A3B8)
        - 連線中：Amber (#F59E0B) + 閃爍
      - status_text: 「在線」(Emerald) / 「離線」(Red) / 「連線中」(Amber) / `text.body.sm`，bold
      - label: 「連線」`text.caption`，`color.text.secondary`
    - **last_operation_card**:
      - 容器：同上
      - icon: Clock icon，Slate 500
      - time_text: 相對時間「{X} 分鐘前」/ `text.body.sm`
      - label: 「最近操作」`text.caption`，`color.text.secondary`
  - quick_actions: 操作按鈕組 / required / 垂直排列，gap `space.2`：
    - remote_unlock_button: Button CTA (Amber) / full width / icon LockOpen / 「遠端開鎖」
      - 點擊 → 二次確認 Modal「確定要遠端開鎖嗎？此操作將記錄在稽核日誌中。」
      - 確認後 → Loading → 成功 Toast「已成功遠端開鎖」/ 失敗 Toast
    - reset_password_button: Button Secondary / full width / icon Key / 「重置密碼」
      - 點擊 → 二次確認 Modal「確定要重置此鎖具密碼嗎？原密碼將立即失效。」
      - 確認後 → Loading → 成功顯示新密碼（可複製）
  - device_offline_overlay: 設備離線時覆蓋層 / conditional：
    - 半透明灰色覆蓋（opacity 0.6）+ 「設備離線，無法執行遠端操作」文字
    - 操作按鈕 Disabled
- **states**:
  - default: 顯示設備資訊 + 即時指標 + 可操作按鈕
  - loading: Skeleton（圖片佔位 + 3 個圓形 + 按鈕條）
  - online: 三項指標正常顯示，按鈕可用
  - offline: connectivity 顯示「離線」，quick_actions 按鈕 Disabled + overlay
  - low_battery: 電量環變紅色 + pulse，若 < 10% 顯示 Warning Badge「電量極低」
  - no_device: 「此工單未關聯設備資訊」灰字 + Lock icon
  - unlocking: 遠端開鎖中，按鈕 Spinner + 「開鎖中...」
- **copy_constraints**: 型號名稱最多 25 字；序號最多 20 字

---

### Section: customer_info_card

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **elements**:
  - card_title: H4 (`text.heading.sm` 16px, 600) / 「客戶資訊」
  - customer_name: `text.body.md`，font-weight 600，`color.text.primary` / 客戶姓名
  - phone_number: `text.body.md`，`color.primary` (#2563EB)，可點擊（`tel:` 連結）/ icon Phone / 格式「09XX-XXX-XXX」
  - address: `text.body.sm`，`color.primary`，可點擊（開啟 Google Maps 外部連結）/ icon MapPin / 完整地址，可換行
  - risk_level_badge: Badge / optional / 風險等級：
    - 「一般」：Slate Badge（大多數客戶）
    - 「VIP」：Amber Badge（高價值客戶）
    - 「高風險」：Red Badge（有投訴歷史）
  - preferred_technician: `text.body.sm` / optional / 「偏好技師：{name}」/ 若無偏好：不顯示此行
  - order_history_link: Link / `text.body.sm` / 「查看歷史工單 ({count} 筆) →」/ 導航至工單列表頁並帶上客戶篩選
- **states**:
  - default: 顯示客戶完整資訊
  - loading: Skeleton（姓名 + 電話 + 地址）
  - no_customer: 「客戶資訊未填寫」灰字
- **copy_constraints**: 姓名最多 10 字；地址最多 50 字（可換行）

---

### Section: technician_info_card

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **elements**:
  - card_title: H4 / 「指派技師」
  - technician_avatar: Avatar 48px 圓形 / 技師頭像
  - technician_name: `text.body.md`，font-weight 600 / 技師姓名
  - rating_stars: 5 星評分，星星 16px，Amber 填充
  - rating_number: `text.body.sm`，`color.text.secondary` / 「{rating}/5.0 ({review_count} 則評價)」
  - skill_badges: Badge 群組 / 技能標籤：
    - 每個技能一個 Badge，Slate 背景，`radius.sm`，`text.body.sm`
    - 最多顯示 5 個，超出「+{count}」
  - mini_map: 嵌入式小地圖 / optional / 高度 120px，`radius.md`：
    - 顯示技師當前位置（Blue 圓點）
    - 工單地址位置（Red 圓點）
    - 兩點間灰色路線
    - 地圖不可互動（僅展示），點擊開啟完整地圖
  - distance_info: `text.body.sm`，`color.text.secondary` / 「距離工單地址 {distance} km」
  - contact_button: Button Secondary sm / icon Phone / 「聯繫技師」/ 點擊開啟通訊選項（電話/LINE）
  - unassigned_state: 未指派時的替代顯示：
    - 灰色虛線邊框卡片
    - UserPlus icon (48px，Slate 300)
    - 「尚未指派技師」`text.body.md`，`color.text.secondary`
    - 「手動指派」Button Primary / 點擊開啟 assign Modal
- **states**:
  - default: 顯示技師完整資訊 + 小地圖
  - loading: Skeleton（Avatar 圓 + 姓名 + 星星 + 地圖灰塊）
  - unassigned: 顯示 unassigned_state 替代內容
  - technician_offline: 小地圖上技師圓點灰色 + 「技師目前離線」Badge
  - map_loading: 小地圖區域 Skeleton + Spinner
  - map_error: 小地圖區域灰色 + 「地圖載入失敗」小字
- **copy_constraints**: 技師姓名最多 8 字；技能標籤每個最多 6 字

---

### Section: quotation_card

- **layout**: 側邊欄卡片，白色背景，`radius.lg`，`shadow.sm`，padding `space.4`
- **elements**:
  - card_title: H4 / 「報價明細」
  - price_breakdown: 列表 / required：
    - 每行：項目名稱 (`text.body.sm`，左對齊) + 金額 (`text.body.sm`，右對齊，等寬字體)
    - 典型項目：
      - 「工資」NT$ {amount}
      - 「零件費」NT$ {amount}
      - 「出勤費」NT$ {amount}
      - 「加急費」NT$ {amount}（若有）
      - 「折扣」-NT$ {amount}（紅色，若有）
    - Divider 線
    - total_row: 「合計」(`text.body.md`，bold) + NT$ {total} (`text.heading.sm`，bold，`color.text.primary`)
  - payment_status: Badge / required：
    - 「待報價」：Slate Badge
    - 「待付款」：Amber Badge
    - 「已付款」：Emerald Badge
    - 「已退款」：Red Badge
    - 「部分退款」：Amber Badge
  - payment_method: `text.body.sm`，`color.text.secondary` / optional / 「付款方式：{method}」
  - invoice_link: Link / `text.body.sm` / 「查看發票 →」/ 開啟發票 PDF / optional
  - no_quotation_state: 未報價時：
    - 「尚未建立報價」灰字 + Receipt icon
- **states**:
  - default: 顯示完整價格明細
  - loading: Skeleton（4 行 + 合計行）
  - no_quotation: 顯示 no_quotation_state
  - payment_overdue: payment_status Badge Red + 「逾期未付款」提示文字
- **copy_constraints**: 項目名稱最多 15 字；金額格式「NT$ X,XXX」

---

### Section: action_panel

- **layout**: 側邊欄底部固定卡片（sticky bottom within sidebar），白色背景，`radius.lg`，`shadow.sm`，padding `space.4`，border-top 2px `color.border.default`
- **elements**: 依工單當前狀態動態顯示不同按鈕組合：

  - **status = `created`（已建立）**：
    - primary_action: Button Primary full-width / icon UserPlus / 「手動指派」/ 點擊開啟 assign Modal
    - secondary_action: Button Danger Ghost full-width / 「取消工單」/ 確認 Modal

  - **status = `assigned`（已派工）**：
    - primary_action: Button CTA (Amber) full-width / icon Bell / 「催促技師」/ 點擊 → 發送催促通知 + Toast「已發送催促通知」
    - secondary_action: Button Secondary full-width / icon RefreshCcw / 「重新派工」/ 開啟 assign Modal（重新選技師）
    - tertiary_action: Button Danger Ghost full-width / 「取消工單」/ 確認 Modal

  - **status = `accepted`（已接受）**：
    - info_text: `text.body.sm`，`color.text.secondary` / 「技師已接受工單，等待前往現場」
    - secondary_action: Button Secondary full-width / 「重新派工」（特殊情況下更換技師）

  - **status = `in_progress`（進行中）**：
    - primary_action: Button CTA (Amber) full-width / icon AlertTriangle / 「標記異常」/ 點擊開啟異常類型選擇 Modal：
      - 「範圍變更」(scope_change)
      - 「缺料」(material_pending)
      - 「延遲」(delayed)
      - 需填寫備註
    - info_text: `text.body.sm` / 「技師正在現場作業中」

  - **status = `scope_changed` / `material_pending` / `delayed`（異常狀態）**：
    - exception_info: Alert Warning / 異常描述摘要
    - primary_action: Button Primary full-width / 「恢復進行中」/ 確認 Modal

  - **status = `completed`（已完工）**：
    - primary_action: Button Primary full-width / icon CheckCircle / 「確認完工」/ 確認 Modal「確認完工後將進入客戶確認流程」
    - secondary_action: Button Danger full-width / icon RotateCcw / 「要求返工」/ 開啟返工 Modal：
      - 選擇返工原因（下拉）
      - 填寫返工說明（Textarea）
      - 確認後工單狀態變更為 `rework_required`

  - **status = `rework_required`（返工中）**：
    - exception_info: Alert Danger / 「此工單需要返工」+ 返工原因
    - info_text: 「等待技師重新處理」

  - **status = `confirmed`（已確認）**：
    - success_info: Alert Success / 「工單已確認完工」
    - secondary_action: Button Secondary full-width / 「歸檔」/ 工單狀態變更為 `archived`

  - **status = `disputed`（爭議中）**：
    - exception_info: Alert Danger / 「此工單存在爭議」
    - primary_action: Button Danger full-width / icon Gavel / 「進入仲裁」/ 導航至爭議仲裁頁面 `/admin/disputes/{dispute_id}`
    - secondary_action: Button Secondary full-width / 「查看爭議詳情」

  - **status = `cancelled`（已取消）**：
    - info_text: Alert Slate / 「此工單已取消」+ 取消原因
    - 無操作按鈕

  - **status = `archived`（已歸檔）**：
    - info_text: Alert Slate / 「此工單已歸檔」
    - 無操作按鈕

- **states**:
  - default: 依當前狀態顯示對應按鈕
  - loading: Skeleton 按鈕（2 個長條）
  - action_processing: 點擊按鈕後 → 按鈕變為 Loading Spinner + Disabled
  - action_success: Toast Success + 頁面即時刷新（SLA timeline + status_badge + work_timeline 新增紀錄）
  - action_failure: Toast Error「操作失敗：{error_message}」+ 按鈕恢復可用
  - permission_denied: 無權限操作 → 按鈕 Disabled + tooltip「你沒有權限執行此操作」
- **copy_constraints**: 按鈕文字最多 6 字；info_text 最多 40 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **頁面載入**：
   - 從 URL 取得 `[id]` → 並行請求：
     - GET `/api/v1/work-orders/{id}`（工單主資料 + 客戶 + 技師 + 報價 + 設備）
     - GET `/api/v1/work-orders/{id}/timeline`（歷程時間軸）
     - GET `/api/v1/work-orders/{id}/exceptions`（異常記錄）
   - 所有資料載入完成 → 渲染頁面
   - 建立 WebSocket 連線（訂閱此工單的即時更新）

2. **狀態操作（Action Panel 按鈕）**：
   - 點擊操作按鈕 → 顯示確認 Modal（若需要）
   - 確認 → PATCH `/api/v1/work-orders/{id}/status` → Loading
   - 成功 → Toast Success + 即時更新：
     - detail_header: status_badge 變更 + SLA timeline 節點推進
     - work_timeline: 新增歷程記錄（WebSocket 或手動 refetch）
     - action_panel: 按鈕組合依新狀態切換
   - 失敗 → Toast Error + 按鈕恢復

3. **手動指派（created 狀態）**：
   - 點擊「手動指派」→ 開啟 assign Modal
   - Modal 載入候選技師 → 選擇 → 指派
   - 成功 → Modal 關閉 + 狀態變更為 `assigned` + technician_info_card 更新

4. **標記異常（in_progress 狀態）**：
   - 點擊「標記異常」→ 選擇異常類型 + 填寫備註
   - 確認 → 狀態變更為對應異常狀態 + exception_records 新增記錄

5. **確認完工 / 要求返工（completed 狀態）**：
   - 「確認完工」→ 狀態變更為 `confirmed`
   - 「要求返工」→ 填寫返工原因 → 狀態變更為 `rework_required` + exception_records 新增記錄

6. **遠端設備操作**：
   - 點擊「遠端開鎖」/「重置密碼」→ 二次確認 Modal
   - 確認 → API 請求 → 結果 Toast
   - 操作記錄自動記入 work_timeline 與設備稽核日誌

7. **瀏覽客戶上傳媒體（LINE Media Gallery）**：
   - 進入頁面 → 並行請求 GET `/api/v1/work-orders/{id}/media` 取得 issue 包列表
   - 點擊 bundle_header → 展開媒體縮圖網格（允許同時多個展開）
   - 切換 filter_tabs（全部/圖片/影片/Issue 包）→ 前端即時過濾縮圖，不重新發送 API
   - 點擊圖片縮圖 → 開啟 Lightbox（與 conversation_thread 共用元件）；左右鍵切換同 bundle 內其他圖片
   - 點擊影片縮圖 → 開啟內嵌播放器 Modal（play/pause/seek/音量/倍速 0.5-2x/下載）；Escape 關閉
   - 點擊檔案/語音縮圖 → 直接下載 / 展開 audio player
   - 點擊「下載此包」→ POST `/api/v1/work-orders/{id}/media/bundles/{bundle_id}/download` → Server 打包 zip → 回傳 signed URL → 瀏覽器觸發下載
   - 點擊「轉傳給技師」→ 二次確認 Modal → POST `/api/v1/work-orders/{id}/media/bundles/{bundle_id}/forward` → Toast 成功/失敗
   - 點擊 ai_analysis_block 的「→ 關聯 ProblemCard」→ 頁面平滑捲動至 problem_card_summary 並背景高亮 2s
   - 點擊 conversation_thread 圖片/影片氣泡的「在客戶媒體區檢視」→ 捲動至 line_media_gallery 並高亮對應縮圖 2s

8. **對話記錄瀏覽**：
   - 捲動瀏覽 LINE 對話 → 點擊圖片 → Lightbox 放大
   - 「在新視窗開啟」→ 全螢幕對話視窗

9. **異常記錄互動**：
   - 點擊手風琴 header → 展開/摺疊詳情
   - 可同時展開多個異常記錄

10. **即時更新（WebSocket）**：
    - 工單狀態變更 → 全頁面相關區塊即時更新
    - 新歷程記錄 → timeline 頂部插入新項目（滑入動畫 + 高亮 2s）
    - 設備狀態變更 → device_status_panel 指標更新
    - 技師位置變更 → mini_map 位置點移動
    - 客戶於 LINE 新增上傳 → line_media_gallery 對應 bundle 內新增縮圖（滑入 + 高亮 2s）；若為新 bundle 則整張卡片從頂部插入

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop LG (> 1440px) | 左 2/3 + 右 1/3 雙欄 | 完整體驗，sidebar 固定可見 |
| Desktop (1024-1440px) | 左 2/3 + 右 1/3 雙欄 | sidebar 稍窄（min-width 320px） |
| Tablet (768-1023px) | 全寬單欄 + sidebar 變為底部上滑面板 (BottomSheet) | 主內容全寬；sidebar 內容收入 BottomSheet，三段式高度：Collapsed (顯示 action_panel) → Half (50%) → Full (90%)；預設 Collapsed |
| Mobile (< 768px) | 全寬單欄堆疊 | sidebar 各卡片堆疊在主內容下方；action_panel 固定底部 (sticky bottom 56px)；ProblemCard 預設摺疊；conversation_thread max-height 300px；mini_map 隱藏 |

### 資料更新策略

- **工單主資料**：TanStack Query，staleTime 60 秒，背景 refetch on window focus
- **時間軸**：初次載入 + WebSocket 增量更新
- **設備狀態**：30 秒輪詢 + WebSocket 事件
- **技師位置**：30 秒輪詢（僅 mini_map 使用）
- **WebSocket 即時推送**：
  - Event: `work_order.{id}.status_changed` → 更新 header + action_panel + timeline
  - Event: `work_order.{id}.timeline_added` → timeline 新增項目
  - Event: `work_order.{id}.exception_created` → exception_records 新增
  - Event: `device.{device_id}.status_updated` → device_status_panel 更新
- **Zustand Client State**：
  - `expandedSections: Set<string>` — 展開的可摺疊區塊
  - `lightboxState: { open: boolean, images: string[], currentIndex: number }` — 圖片瀏覽器
  - `assignModalOpen: boolean` — 指派 Modal 狀態
  - `confirmModalState: { open: boolean, action: string, payload: any }` — 確認 Modal

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/work-orders/{id}` — 取得工單完整資料（含客戶、技師、設備、報價、ProblemCard 摘要）
    - Response: `{ work_order: WorkOrderDetail }`
    - WorkOrderDetail 包含：`id, wo_number, status, customer, technician, device, quotation, problem_card_summary, sla_deadline, sla_status, created_at, updated_at`
  - GET `/api/v1/work-orders/{id}/timeline` — 取得工單歷程時間軸
    - Query params: `page`, `page_size`, `event_type`
    - Response: `{ events: TimelineEvent[], total: number }`
    - TimelineEvent: `{ id, event_type, title, detail, actor: { type, name }, timestamp, metadata: { match_score?, match_factors?, exception_type? }, attachments?: [] }`
  - GET `/api/v1/work-orders/{id}/exceptions` — 取得工單異常記錄
    - Response: `{ exceptions: ExceptionRecord[] }`
    - ExceptionRecord: `{ id, type, title, status, created_at, detail: { ... type-specific fields } }`
  - GET `/api/v1/work-orders/{id}/conversation` — 取得關聯 LINE 對話記錄
    - Response: `{ messages: ConversationMessage[] }`
    - ConversationMessage: `{ id, sender: { type, name }, content_type, content, timestamp, metadata? }`
  - GET `/api/v1/work-orders/{id}/media` — 取得工單關聯的客戶上傳媒體與 issue 包
    - Response: `{ bundles: IssueBundle[] }`
    - IssueBundle: `{ id, trigger_text, submitted_at, source: 'line', channel_message_ids: string[], media_count: { photo, video, file, audio }, media: MediaItem[], ai_analysis?: AIAnalysis }`
    - MediaItem: `{ id, type: 'image'|'video'|'file'|'audio', url, thumbnail_url?, file_name, mime_type, duration_sec?, size_bytes, source_tag: 'initial'|'supplementary'|'ai_followup', is_expired, is_backed_up, uploaded_at }`
    - AIAnalysis: `{ keywords: string[], linked_problem_card_id?: string, vision_model?: { brand: string, model: string, confidence: number } }`
  - POST `/api/v1/work-orders/{id}/media/bundles/{bundle_id}/download` — 打包下載 issue 包（zip）
    - Response: `{ download_url: string, expires_at: string, size_bytes: number }`
    - download_url 為 signed URL，15 分鐘有效
  - POST `/api/v1/work-orders/{id}/media/bundles/{bundle_id}/forward` — 轉傳 issue 包至指派技師 LINE
    - Body: `{ target: 'assigned_technician' | technician_id, message?: string }`
    - Response: `{ success: boolean, pushed_message_id?: string }`
  - GET `/api/v1/work-orders/{id}/completion-report` — 取得完工報告
    - Response: `{ report: CompletionReport }`
  - PATCH `/api/v1/work-orders/{id}/status` — 變更工單狀態
    - Body: `{ status: string, note?: string, exception_type?: string, rework_reason?: string }`
    - Response: `{ success: boolean, work_order: WorkOrderDetail }`
  - PATCH `/api/v1/work-orders/{id}/assign` — 指派技師
    - Body: `{ technician_id: string }`
    - Response: `{ success: boolean, work_order: WorkOrderDetail }`
  - GET `/api/v1/work-orders/dispatch/candidates/{id}` — 取得候選技師
    - Response: `{ candidates: TechnicianCandidate[] }`
  - POST `/api/v1/work-orders/{id}/notify-technician` — 催促技師通知
    - Body: `{ notification_type: 'reminder' }`
    - Response: `{ success: boolean }`
  - POST `/api/v1/devices/{device_id}/remote-unlock` — 遠端開鎖
    - Response: `{ success: boolean, operation_id: string }`
  - POST `/api/v1/devices/{device_id}/reset-password` — 重置密碼
    - Response: `{ success: boolean, new_password: string }`
  - GET `/api/v1/devices/{device_id}/status` — 取得設備即時狀態
    - Response: `{ battery_level, connectivity, last_operation_at, is_online }`
- **WebSocket Events**:
  - Channel: `ws://api/v1/ws/work-orders/{id}`
  - Events:
    - `work_order.status_changed`: `{ old_status, new_status, actor, timestamp }`
    - `work_order.timeline_added`: `{ event: TimelineEvent }`
    - `work_order.exception_created`: `{ exception: ExceptionRecord }`
    - `device.status_updated`: `{ battery_level, connectivity, last_operation_at }`
    - `technician.location_updated`: `{ lat, lng, timestamp }`
    - `work_order.media_added`: `{ bundle_id, is_new_bundle: boolean, bundle?: IssueBundle, media?: MediaItem }` — 客戶於 LINE 新上傳媒體時即時推送（新 bundle 時帶完整物件，既有 bundle 追加時僅帶單筆 media）
- **error_cases**:
  - 網路錯誤：頂部 Warning Banner + 使用快取資料
  - API 401 Unauthorized：導向登入頁
  - API 403 Forbidden：Toast Error「你沒有權限查看此工單」+ 3 秒後導回列表
  - API 404 Not Found：全頁 404 狀態（「找不到工單 {id}，可能已被刪除」+ 「返回列表」按鈕）
  - API 409 Conflict：Toast Error「工單狀態已被其他人變更，頁面將自動刷新」+ 自動 refetch
  - API 500 Server Error：Toast Error + 重試按鈕
  - WebSocket 斷線：頂部 Warning Banner + 自動重連
  - 設備操作失敗：Toast Error「遠端開鎖失敗：設備無回應，請確認設備連線狀態」
  - 設備離線：操作按鈕 Disabled + tooltip「設備離線，無法執行遠端操作」

---

## [EXCEPTION TO GLOBAL RULES]

- **SLA 逾時 pulse 動畫**：同工單列表頁，SLA 逾時使用持續性 CSS pulse 動畫（1.5s infinite），屬合理例外
- **對話記錄自訂氣泡**：conversation_thread 使用自訂聊天氣泡元件（非 shadcn/ui 標準元件），因為需要模擬 LINE 對話風格，屬合理例外
- **設備狀態圓環圖**：battery_card 使用自訂 SVG 圓環圖（非 Recharts），因為是簡單的單指標環，不需引入完整圖表庫
- **Sidebar sticky 行為**：右側 sidebar 在 Desktop 斷點下使用 `position: sticky; top: 80px`（導航列高度 + gap），跟隨主內容捲動但保持可見
- **多 WebSocket 訂閱**：此頁面同時訂閱工單事件 + 設備事件 + 技師位置，可能有 3 條 WebSocket 連線

---

## [ACCEPTANCE CRITERIA]

### 功能驗收 — 左側主內容

- [ ] Header：工單編號正確顯示（等寬字體 JetBrains Mono）
- [ ] Header：StatusBadge 顯示正確語義色（13 狀態 x 6 色）
- [ ] Header：SLA 時間軸正確渲染（節點狀態、進度填充、倒數計時）
- [ ] Header：SLA 三態（正常/警告/逾時）視覺正確
- [ ] Header：複製工單編號功能正常
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

- [ ] Device Panel：鎖具圖片或佔位 icon 正確
- [ ] Device Panel：電量圓環顏色（綠/黃/紅）依電量等級正確
- [ ] Device Panel：連線狀態燈（綠=在線/灰=離線/黃=連線中）正確
- [ ] Device Panel：最近操作時間（相對時間格式）正確
- [ ] Device Panel：「遠端開鎖」二次確認 + API 呼叫 + Toast 回饋
- [ ] Device Panel：「重置密碼」二次確認 + 新密碼顯示
- [ ] Device Panel：設備離線時操作按鈕 Disabled + overlay
- [ ] Customer Card：電話可點擊撥號（tel: 連結）
- [ ] Customer Card：地址可點擊開啟 Google Maps
- [ ] Customer Card：風險等級 Badge 正確（一般/VIP/高風險）
- [ ] Customer Card：「查看歷史工單」連結導航正確
- [ ] Technician Card：Avatar + 姓名 + 星星評分正確
- [ ] Technician Card：技能 Badge 顯示正確（最多 5 個 + 溢出計數）
- [ ] Technician Card：Mini Map 顯示技師與工單位置
- [ ] Technician Card：未指派時顯示 unassigned_state + 「手動指派」按鈕
- [ ] Technician Card：「聯繫技師」按鈕正確
- [ ] Quotation Card：價格明細（工資/零件/出勤/加急/折扣/合計）正確
- [ ] Quotation Card：付款狀態 Badge 正確
- [ ] Quotation Card：發票連結正確
- [ ] Action Panel：13 種狀態對應的按鈕組合全部正確
- [ ] Action Panel：所有按鈕 Loading → 成功/失敗處理正確
- [ ] Action Panel：「手動指派」開啟 assign Modal 正確
- [ ] Action Panel：「催促技師」發送通知 + Toast 正確
- [ ] Action Panel：「重新派工」開啟 assign Modal 正確
- [ ] Action Panel：「標記異常」開啟異常類型選擇 Modal 正確
- [ ] Action Panel：「確認完工」確認 Modal + 狀態變更正確
- [ ] Action Panel：「要求返工」填寫原因 + 狀態變更正確
- [ ] Action Panel：「進入仲裁」導航正確
- [ ] Action Panel：cancelled / archived 狀態無操作按鈕

### 狀態驗收

- [ ] Loading 狀態：所有 Section Skeleton 正確（預留高度避免 CLS）
- [ ] Empty 狀態：ProblemCard 無資料、Conversation 無對話、Exception 隱藏
- [ ] Error 狀態：API 錯誤友善訊息 + 重試
- [ ] 404 狀態：工單不存在全頁 404 + 返回列表按鈕

### 即時更新驗收

- [ ] WebSocket 連線建立成功（訂閱工單 + 設備 + 技師位置）
- [ ] 工單狀態變更即時反映（header Badge + SLA timeline + action_panel）
- [ ] Timeline 即時新增事件（滑入動畫 + 高亮 2s）
- [ ] 設備狀態即時更新（電量/連線/最近操作）
- [ ] 技師位置即時更新（mini_map 點移動）
- [ ] 客戶於 LINE 新上傳媒體即時推送至 line_media_gallery（新 bundle 整張卡片頂部插入 / 既有 bundle 內新增縮圖 + 高亮 2s）
- [ ] WebSocket 斷線 Warning Banner + 自動重連

### RWD 驗收

- [ ] Desktop LG (> 1440px)：左 2/3 + 右 1/3 雙欄，sidebar sticky
- [ ] Desktop (1024-1440px)：雙欄，sidebar min-width 320px
- [ ] Tablet (768-1023px)：全寬 + sidebar 變 BottomSheet（三段式）
- [ ] Mobile (< 768px)：單欄堆疊 + action_panel 固定底部

### 效能驗收

- [ ] 頁面首次載入 LCP < 2.5s
- [ ] Timeline 載入 20 筆事件 < 500ms
- [ ] 對話記錄 100+ 則訊息不卡頓
- [ ] 設備狀態輪詢不影響主線程
- [ ] CLS < 0.1（所有區塊預留 Skeleton 高度）

### 無障礙驗收

- [ ] Tab 順序：header → main content sections → sidebar cards → action_panel
- [ ] 所有可互動元素可透過鍵盤操作（包含手風琴展開/摺疊）
- [ ] 圖片有 alt 文字
- [ ] StatusBadge 同時包含顏色 + 文字標籤
- [ ] 色彩對比度達 WCAG 2.1 AA
- [ ] Modal focus trap 正確；Escape 關閉
- [ ] 設備操作按鈕 Disabled 時有 aria-disabled + tooltip 說明

---

## T1.4 補強：候選技師手動排序 UI + 客訴升級指示器

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
