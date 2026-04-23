# Page-Level Prompt: Admin Conversations 對話管理

> 管理者檢視所有客戶對話紀錄的列表與詳情雙視圖頁面，支援篩選、即時訊息推送、AI 回覆標記回饋。

---

## [PAGE META]

- **page_name**: Admin Conversations
- **route_path**: `/conversations`（列表）、`/conversations/[id]`（詳情）
- **page_type**: list + detail（雙視圖）
- **primary_goal**: 讓管理者瀏覽與監控所有客戶對話，快速掌握對話狀態、AI 回覆品質，並在必要時介入處理
- **secondary_goal**: 透過 AI 回覆標記功能建立回饋循環，持續優化 AI 診斷品質
- **target_users**:
  - 主要：品牌／經銷商客服管理員（每日頻繁查看）
  - 次要：AI 訓練管理員（定期審查 AI 回覆品質與標記資料）
- **entry_point**: 側邊欄點擊「對話管理」/ Dashboard 通知點擊跳轉 / 工單詳情頁反向連結
- **expected_time_on_page**: 列表頁 1-2 分鐘（篩選瀏覽）；詳情頁 3-10 分鐘（閱讀對話 + 處理回饋）

---

## [STRUCTURE: SECTIONS]

1. **conversation_list_header**
   - section_type: header_with_filters
   - section_purpose: 頁面標題 + 狀態篩選列 + 搜尋框 + 排序控制

2. **conversation_table**
   - section_type: data_table
   - section_purpose: 以表格呈現所有對話摘要，支援排序、篩選與分頁

3. **chat_timeline**
   - section_type: message_list
   - section_purpose: 對話詳情頁左側主區域，以氣泡式時間軸呈現完整對話紀錄

4. **detail_sidebar**
   - section_type: info_panel
   - section_purpose: 對話詳情頁右側資訊面板，包含客戶資訊卡、問題摘要卡、關聯工單

5. **ai_feedback_controls**
   - section_type: action_bar
   - section_purpose: 讓管理者對 AI 回覆進行正確/不正確標記，建立回饋循環

6. **detail_header**
   - section_type: header
   - section_purpose: 詳情頁頂部：返回按鈕 + 對話 ID + 狀態 Badge + 操作按鈕

7. **realtime_indicator**
   - section_type: status_indicator
   - section_purpose: 指示新訊息即時推送連線狀態

---

## [SECTION COMPONENT SPEC]

### Section: conversation_list_header

- **layout**: 全寬，上下兩列 — 第一列：標題 + 操作按鈕；第二列：篩選列（狀態 tabs + 搜尋 + 頻道篩選 + 排序）
- **elements**:
  - page_title: H1 / required / "對話管理"，font: Inter 24px/600
  - total_count: Badge / required / 顯示目前篩選結果總數 "共 {n} 筆"
  - export_button: Button Secondary / optional / "匯出" 下載對話紀錄 CSV
  - status_tabs: TabGroup / required / 5 個狀態標籤：全部、待處理(idle)、收集中(collecting)、處理中(resolving)、已解決(resolved)、已升級(escalated)，各標籤旁顯示計數 Badge
  - search_input: SearchInput / required / placeholder "搜尋客戶名稱、對話內容..."，支援即時搜尋（debounce 300ms）
  - channel_filter: Select / required / 選項：全部頻道 / LINE / Web / 其他
  - sort_select: Select / required / 排序選項：最新訊息優先（預設）/ 建立時間優先 / 等待時間最長
- **states**:
  - default: 所有篩選器顯示預設值，"全部" tab 選中
  - active_filter: 選中的 tab 底部 2px #2563EB 指示線 + 計數 Badge 高亮
  - searching: 搜尋框右側顯示 spinner + "搜尋中..."
  - loading: 計數 Badge 顯示 Skeleton
  - error: 計數顯示 "—"
- **copy_constraints**: 搜尋 placeholder 最多 20 字；Tab 標籤最多 4 字 + 計數

### Section: conversation_table

- **layout**: 全寬資料表格，白色卡片包裹，圓角 8px，shadow-sm，支援分頁（每頁 20 筆）
- **elements**:
  - table_header: TableHead / required / 欄位：對話編號、客戶名稱、狀態、頻道、建立時間、最後訊息預覽
  - table_rows: TableRow[] / required / 每列對應一筆對話摘要
    - conversation_id: Body SM Mono / required / 格式 "CONV-XXXXXXXX"，點擊導航至詳情
    - customer_name: Body SM / required / 客戶顯示名稱，最多 10 字
    - status: Badge / required / idle(灰 #94A3B8) / collecting(藍 #2563EB) / resolving(琥珀 #F59E0B) / resolved(綠 #10B981) / escalated(紅 #EF4444)
    - channel: Badge Outline / required / LINE(綠 #06C755) / Web(藍 #2563EB) / 圖標 + 文字
    - created_at: Caption / required / 相對時間 "N 分鐘前" 或日期格式
    - last_message_preview: Body SM / required / 最後一則訊息摘要，最多 40 字，超出 truncate + "..."
  - unread_indicator: Dot / optional / 有新未讀訊息的列左側顯示藍色圓點
  - pagination: Pagination / required / 頁碼導航 + "每頁 20 筆" + 總頁數
- **states**:
  - default: 表格正常顯示，奇偶列交替背景（#FFFFFF / #F8FAFC）
  - hover: 列背景變為 #EFF6FF，游標 pointer
  - loading: 20 列 Skeleton rows
  - error: 表格區域顯示 "對話載入失敗" + 重試按鈕
  - empty: 若套用篩選後無結果 → "沒有符合條件的對話，請調整篩選條件"；若完全無資料 → 插圖 + "還沒有任何對話紀錄"
  - selected: 當前檢視的對話列背景 #DBEAFE（藍色高亮）
  - new_message: 有新訊息時該列短暫閃爍 + 自動排至頂部（若排序為最新訊息優先）
- **copy_constraints**: 對話編號固定 13 字元；客戶名稱最多 10 字；最後訊息預覽最多 40 字

### Section: detail_header

- **layout**: 全寬單列，左側返回 + 對話資訊，右側操作按鈕，高度 64px，背景 #FFFFFF，底部 1px border #E2E8F0
- **elements**:
  - back_button: IconButton / required / ChevronLeft 圖標 + "返回列表"，點擊導航至 `/conversations`
  - conversation_id: Body SM Mono / required / "CONV-XXXXXXXX"
  - status_badge: Badge / required / 目前對話狀態，同列表的顏色編碼
  - channel_badge: Badge Outline / required / 來源頻道
  - customer_name: H2 / required / 客戶名稱
  - duration_label: Caption / optional / "對話持續 {N} 分鐘" 或 "已結束於 {time}"
  - escalate_button: Button Destructive / optional / "升級處理"，僅在非 escalated 狀態顯示
  - resolve_button: Button Primary / optional / "標記已解決"，僅在非 resolved 狀態顯示
  - more_menu: DropdownMenu / optional / 更多操作：匯出對話、複製連結、刪除對話
- **states**:
  - default: 顯示所有資訊與可用操作按鈕
  - loading: conversation_id + customer_name 顯示 Skeleton
  - escalated: escalate_button 隱藏，status_badge 顯示紅色 "已升級"
  - resolved: resolve_button 隱藏，escalate_button 隱藏，status_badge 顯示綠色 "已解決"
- **copy_constraints**: 客戶名稱最多 10 字；持續時間標籤最多 20 字

### Section: chat_timeline

- **layout**: 詳情頁左側 2/3 寬度（8-col），垂直滾動訊息列表，底部固定觀察區，背景 #F8FAFC
- **elements**:
  - date_separator: Divider / required / 日期分隔線 "── 2026年4月21日 ──"，居中灰色文字
  - message_bubble_user_raw: ChatBubble / required / 客戶原始訊息，靠右對齊，背景 #2563EB，文字白色，圓角 16px 左上 + 左下 + 右下（右上 4px），顯示時間戳 + "原始" 小標籤
  - message_bubble_user: ChatBubble / optional / AI 清洗後的客戶訊息，靠右對齊，背景 #DBEAFE，文字 #1E293B，圓角同上，顯示 "已整理" 標籤，hover 可展開查看 diff
  - message_bubble_ai: ChatBubble / required / AI 回覆訊息，靠左對齊，背景 #FFFFFF，文字 #1E293B，border 1px #E2E8F0，圓角 16px 右上 + 左下 + 右下（左上 4px），左上角 AI 頭像 + "AI 助理" 標籤
  - message_system: SystemMessage / required / 系統訊息（狀態變更、升級通知等），居中對齊，背景 #F1F5F9，圓角 8px，文字 #64748B，font-size 12px
  - timestamp: Caption / required / 每則訊息下方顯示 HH:mm 時間
  - scroll_to_bottom_fab: FAB / optional / 當使用者往上捲動時，右下角顯示 "↓ 新訊息" 浮動按鈕
  - typing_indicator: TypingDots / optional / AI 正在生成回覆時顯示三點動畫
- **states**:
  - default: 訊息由上至下按時間排列，自動捲動至最新訊息
  - hover_ai_message: AI 訊息右上角顯示 feedback 操作按鈕（thumbs up / thumbs down / flag）
  - hover_user_raw: 若有對應 cleaned 版本，顯示 "查看整理版" tooltip
  - loading: 訊息區域顯示 3-5 個 Skeleton 氣泡（交替左右）
  - error: "訊息載入失敗" + 重試按鈕，居中顯示
  - empty: "這個對話還沒有任何訊息" 居中文字
  - new_message_arriving: 新訊息以 slide-up + fade-in 動畫出現（0.3s ease-out）
  - loading_more: 向上捲動至頂部時顯示 "載入更早的訊息..." spinner（infinite scroll）
- **copy_constraints**: 訊息氣泡最大寬度 70% 容器寬度；系統訊息最多 60 字；時間戳格式 HH:mm

### Section: detail_sidebar

- **layout**: 詳情頁右側 1/3 寬度（4-col），垂直堆疊資訊卡片，背景 #FFFFFF，左側 1px border #E2E8F0，padding 24px，可獨立捲動
- **elements**:
  - customer_info_card: Card / required / 標題 "客戶資訊"
    - customer_name: Body MD / required / 客戶姓名
    - phone: Body SM / optional / 電話號碼（可點擊撥打）
    - line_id: Body SM / optional / LINE 用戶 ID
    - address: Body SM / optional / 地址（若已收集）
    - history_count: Caption / optional / "歷史對話 {N} 次"
    - view_history_link: Link / optional / "查看歷史 →" 導向客戶歷史頁
  - problem_card: Card / required / 標題 "問題摘要"（ProblemCard）
    - problem_summary: Body SM / required / AI 歸納的問題摘要，最多 100 字
    - lock_brand: Badge / optional / 鎖具品牌
    - lock_model: Badge / optional / 鎖具型號
    - symptom_tags: TagGroup / optional / AI 辨識的症狀標籤（如 "無法開鎖"、"電池耗盡"、"密碼錯誤"）
    - ai_diagnosis: Body SM / optional / AI 初步診斷結論
    - confidence_score: ProgressBar / optional / AI 信心分數 0-100%
  - linked_work_order_card: Card / optional / 標題 "關聯工單"（僅在已建立工單時顯示）
    - order_id: Body SM Mono / required / 工單編號，可點擊跳轉
    - order_status: Badge / required / 工單狀態
    - assigned_technician: AvatarName / optional / 指派技師
    - scheduled_time: Body SM / optional / 預約時間
    - create_order_button: Button Primary / conditional / 當無關聯工單時顯示 "建立工單" 按鈕
  - conversation_meta_card: Card / optional / 標題 "對話資訊"
    - created_at: Body SM / required / 建立時間
    - updated_at: Body SM / required / 最後更新
    - message_count: Body SM / required / 訊息總數
    - ai_response_count: Body SM / optional / AI 回覆次數
    - flagged_count: Caption / optional / 被標記不正確的 AI 回覆數
- **states**:
  - default: 所有卡片垂直堆疊，間距 16px
  - loading: 各卡片顯示 Skeleton 內容
  - error: 個別卡片顯示 "載入失敗" + 重試
  - empty_problem: problem_card 顯示 "AI 尚未收集到足夠資訊" + 淺灰背景
  - empty_work_order: linked_work_order_card 區域顯示 "建立工單" CTA 按鈕
  - mobile: Sidebar 收合為底部可展開面板（Sheet），預設隱藏
- **copy_constraints**: 問題摘要最多 100 字；症狀標籤每個最多 8 字、最多 5 個；AI 診斷最多 80 字

### Section: ai_feedback_controls

- **layout**: 內嵌於每則 AI 訊息氣泡右上角，hover 時顯示的操作列
- **elements**:
  - thumbs_up: IconButton / required / ThumbsUp 圖標，標記此回覆正確
  - thumbs_down: IconButton / required / ThumbsDown 圖標，標記此回覆不正確
  - flag_button: IconButton / required / Flag 圖標，標記此回覆需要人工審查
  - feedback_dialog: Dialog / conditional / 點擊 thumbs_down 或 flag 後彈出
    - feedback_category: Select / required / 選項：回答錯誤 / 資訊不完整 / 語氣不當 / 推薦了錯誤型號 / 其他
    - feedback_note: Textarea / optional / 備註說明，最多 200 字
    - correct_answer: Textarea / optional / 提供正確答案（選填）
    - submit_button: Button Primary / required / "提交回饋"
    - cancel_button: Button Ghost / required / "取消"
- **states**:
  - default: 操作按鈕隱藏，僅 hover AI 訊息時顯示
  - hover: 三個 IconButton 以 fade-in 動畫出現（0.15s），背景半透明白色 pill
  - thumbs_up_active: ThumbsUp 圖標填充綠色 #10B981，其餘按鈕隱藏
  - thumbs_down_active: ThumbsDown 圖標填充紅色 #EF4444，觸發 feedback_dialog
  - flagged: Flag 圖標填充琥珀色 #F59E0B，訊息氣泡左側增加 2px 琥珀色邊框
  - submitting: Dialog submit_button 顯示 spinner + "提交中..."
  - submitted: Dialog 關閉，顯示 Toast "回饋已提交，感謝您的協助"
  - error: Dialog 內顯示 inline 錯誤 "提交失敗，請重試"
- **copy_constraints**: 回饋備註最多 200 字；正確答案最多 500 字；Toast 訊息最多 20 字

### Section: realtime_indicator

- **layout**: detail_header 右側小型狀態指示器
- **elements**:
  - connection_dot: StatusDot / required / 綠色 = WebSocket 連線中；琥珀色 = polling 降級；紅色 = 離線
  - new_message_toast: Toast / optional / 在列表頁時收到新訊息推送 → 顯示 "CONV-XXXX 有新訊息" toast
- **states**:
  - connected: 綠色圓點 + 微弱 pulse 動畫
  - polling_fallback: 琥珀色圓點
  - disconnected: 紅色圓點 + "離線" 文字
  - reconnecting: 琥珀色 + 旋轉動畫
- **copy_constraints**: Toast 訊息最多 25 字

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. 頁面載入（列表）→ 請求 `GET /api/v1/conversations` 預設排序最新優先 → 表格渲染
2. 點擊狀態 Tab（如 "已升級"）→ query param 更新 `?status=escalated` → 表格重新載入篩選結果
3. 輸入搜尋關鍵字 → debounce 300ms → `GET /api/v1/conversations?search=xxx` → 表格更新
4. 點擊表格列 → 導航至 `/conversations/[id]` → 並行請求對話詳情 + 訊息列表
5. 詳情頁載入 → 建立 WebSocket 訂閱該對話頻道 → 新訊息即時 append
6. 捲動至對話頂部 → 觸發 infinite scroll → `GET /api/v1/conversations/{id}/messages?before={cursor}` → 載入更早訊息
7. Hover AI 回覆訊息 → 顯示 feedback 操作按鈕
8. 點擊 ThumbsDown → 彈出回饋 Dialog → 填寫原因與備註 → 提交 `POST /api/v1/conversations/{id}/messages/{msg_id}/feedback`
9. 點擊 "建立工單" → 導航至 `/work-orders/new?conversation_id={id}`，自動帶入問題摘要
10. 點擊 "升級處理" → 確認 Dialog → `POST /api/v1/conversations/{id}/escalate` → 狀態更新 + 系統訊息 append
11. 點擊 "標記已解決" → 確認 Dialog → `PATCH /api/v1/conversations/{id}` body `{status: "resolved"}` → 狀態更新
12. 點擊返回按鈕 → 導航回 `/conversations`，保留先前的篩選與分頁狀態

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Desktop (≥1280px) | 列表：全寬表格 + 篩選列。詳情：左 2/3 聊天 + 右 1/3 sidebar | 完整體驗，sidebar 常駐可見 |
| Tablet (768-1279px) | 列表：表格隱藏 "最後訊息預覽" 欄。詳情：聊天全寬，sidebar 改為右側可收合面板（預設收合） | 點擊 "資訊" 按鈕展開 sidebar overlay |
| Mobile (<768px) | 列表：改為卡片列表（每張卡片含 ID、名稱、狀態、時間）。詳情：聊天全寬，sidebar 改為底部 Sheet | 上滑展開 Sheet 查看客戶資訊；feedback 操作改為長按觸發 |

### 資料更新策略

- 對話列表：頁面載入時請求，狀態 Tab 切換時重新請求，WebSocket 推送新訊息時更新對應列的 last_message_preview 與排序
- 對話訊息：進入詳情頁時載入最新 50 則，向上捲動觸發 infinite scroll 載入歷史訊息（每次 20 則）
- 新訊息推送：WebSocket 即時推送，降級為 10 秒 polling（僅詳情頁開啟時）
- 快取策略：TanStack Query staleTime 設為 30s（列表）/ 0s（訊息，always fresh），列表 query key 包含篩選參數
- 離開詳情頁時：取消 WebSocket 訂閱該對話頻道，釋放連線資源
- 瀏覽器切回（visibilitychange）：列表頁 invalidate conversations query；詳情頁 refetch 最新訊息

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/conversations` — 取得對話列表，支援 query params：`status`、`channel`、`search`、`sort`、`page`、`limit`（預設 20）
  - GET `/api/v1/conversations/{id}` — 取得單筆對話詳情（含客戶資訊、問題摘要、關聯工單）
  - GET `/api/v1/conversations/{id}/messages` — 取得對話訊息列表，支援 `before`（cursor）、`limit`（預設 50）分頁
  - POST `/api/v1/conversations/{id}/messages/{msg_id}/feedback` — 提交 AI 回覆回饋，body：`{type: "correct"|"incorrect"|"flagged", category?, note?, correct_answer?}`
  - POST `/api/v1/conversations/{id}/escalate` — 升級對話，觸發通知
  - PATCH `/api/v1/conversations/{id}` — 更新對話狀態（如標記已解決），body：`{status: "resolved"}`
  - WS `/ws/conversations` — WebSocket 頻道，推送新訊息、狀態變更事件；訂閱特定對話 `{action: "subscribe", conversation_id: "{id}"}`
- **request_headers**:
  - Authorization: Bearer {access_token}
  - X-Tenant-ID: {tenant_id}（多租戶隔離）
- **error_cases**:
  - 網路錯誤：列表頁顯示 Toast "網路異常"，使用快取繼續顯示；詳情頁聊天區顯示 "連線中斷" 橫幅
  - API 錯誤（5xx）：對應區塊顯示 inline 錯誤 + 重試按鈕
  - API 錯誤（404）：對話不存在 → 顯示 "對話不存在或已被刪除" + 返回列表按鈕
  - 權限不足（401/403）：導向登入頁 `/login`，保留 redirect 參數
  - 回饋提交失敗：Dialog 內顯示 inline 錯誤，不關閉 Dialog，允許重試
  - WebSocket 斷線：自動重連（指數退避），3 次失敗後切換 polling
  - 訊息載入超時（>5s）：顯示 "載入時間較長，請耐心等候" 提示，15 秒後顯示重試按鈕

---

## [EXCEPTION TO GLOBAL RULES]

- 聊天氣泡使用 16px 圓角（大於全域預設 4-8px），因對話介面需要較柔和的視覺風格
- 客戶原始訊息（user_raw）與整理後訊息（user）使用不同背景色區分（#2563EB vs #DBEAFE），此為對話頁專屬設計
- AI 回覆的 hover feedback 操作為此頁面專屬互動模式，其餘頁面不使用 hover reveal pattern
- Infinite scroll 取代標準分頁元件，僅用於訊息載入（列表頁仍使用標準分頁）

---

## [ACCEPTANCE CRITERIA]

- [ ] 列表頁：對話表格正常顯示所有 6 個欄位（對話編號、客戶名稱、狀態、頻道、建立時間、最後訊息預覽）
- [ ] 列表頁：5 種狀態 Tab 篩選功能正常，切換時表格即時更新，計數 Badge 正確
- [ ] 列表頁：搜尋功能正常（debounce 300ms），支援客戶名稱與對話內容搜尋
- [ ] 列表頁：頻道篩選與排序功能正常
- [ ] 列表頁：分頁功能正常，每頁 20 筆
- [ ] 列表頁：新訊息推送時對應列即時更新 last_message_preview
- [ ] 詳情頁：三種訊息氣泡樣式正確（user_raw 藍底白字靠右 / user 淺藍底靠右 / AI 白底靠左 / system 居中灰底）
- [ ] 詳情頁：訊息時間軸按時間順序排列，日期分隔線正確顯示
- [ ] 詳情頁：WebSocket 新訊息即時 append + slide-up 動畫
- [ ] 詳情頁：向上捲動觸發 infinite scroll 載入歷史訊息
- [ ] 詳情頁：Sidebar 客戶資訊卡、問題摘要卡（ProblemCard）、關聯工單卡正確顯示
- [ ] 詳情頁：無關聯工單時顯示 "建立工單" 按鈕，點擊正確帶入 conversation_id
- [ ] AI 回覆 hover 顯示 feedback 按鈕（thumbs up / down / flag）
- [ ] ThumbsDown 與 Flag 點擊後彈出回饋 Dialog，提交成功顯示 Toast
- [ ] "升級處理" 與 "標記已解決" 功能正常，含確認 Dialog
- [ ] Loading / Error / Empty 三態在所有 Section 均已實作
- [ ] RWD 三個斷點（Desktop / Tablet / Mobile）佈局行為正確
- [ ] Mobile 下列表改為卡片模式，Sidebar 改為底部 Sheet
- [ ] 返回列表時保留先前的篩選與分頁狀態
- [ ] API 錯誤時各區塊獨立處理，不影響其他區塊
- [ ] 首次列表載入 < 2 秒；詳情頁訊息載入 < 3 秒
- [ ] 符合 Design System 色彩規範（Primary #2563EB / Accent #F59E0B / BG #F8FAFC）
- [ ] 多租戶隔離正確，僅顯示當前租戶資料


---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State Persistence / Error Navigation 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`（本檔對應段落）。

本 spec 覆蓋的 IA 頁面依 `MAPPING.md §2` 查找。
