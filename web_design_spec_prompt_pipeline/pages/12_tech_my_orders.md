# Page-Level Prompt: 技師端 — 我的工單

> 技師已接工單管理、現場作業流程、完工報告提交。涵蓋列表頁與詳情頁兩個路由。

---

## [PAGE META]

- **page_name**: 我的工單 My Orders
- **route_path**: `/my-orders`（列表）、`/my-orders/[id]`（詳情 + 完工報告）
- **page_type**: list + detail + form (multi-view)
- **primary_goal**: 管理進行中工單，完成現場作業流程並提交完工報告
- **secondary_goal**: 查看歷史工單紀錄與完工資料
- **target_users**:
  - 主要：已接單的外派技師（作業中頻繁使用）
  - 次要：無
- **entry_point**: 底部導航第 2 個 Tab「我的工單」/ 接單成功後自動跳轉 / Push Notification 點擊
- **expected_time_on_page**: 列表 30 秒–1 分鐘，詳情頁 5–30 分鐘（視作業時間）

---

## [STRUCTURE: SECTIONS]

### `/my-orders` 列表頁

1. **page_header**
   - section_type: header
   - section_purpose: 頁面標題

2. **tab_bar**
   - section_type: tab_navigation
   - section_purpose: 切換進行中 / 待確認 / 歷史工單

3. **order_card_list**
   - section_type: scrollable_list
   - section_purpose: 顯示該分類下的工單卡片，pull-to-refresh

### `/my-orders/[id]` 詳情頁

4. **detail_header**
   - section_type: status_header
   - section_purpose: 工單狀態條 + 工單編號

5. **customer_section**
   - section_type: info_block
   - section_purpose: 客戶聯絡資訊與特殊備註

6. **device_section**
   - section_type: info_block
   - section_purpose: 鎖具品牌型號 + 自動生成的工具/安全檢查清單

7. **problem_card_section**
   - section_type: collapsible_card
   - section_purpose: AI 診斷的症狀與推理摘要

8. **action_section**
   - section_type: dynamic_actions
   - section_purpose: 依工單狀態顯示不同操作區塊

9. **completion_report_form**
   - section_type: form
   - section_purpose: 完工報告表單（作業項目、零件、照片、測試、簽名）

10. **bottom_navigation**
    - section_type: navigation
    - section_purpose: 三 Tab 底部導航列（我的工單 active）

---

## [SECTION COMPONENT SPEC]

### Section: page_header（列表頁）

- **layout**: 固定頂部，高度 56px，背景白色，左對齊，padding 0 16px
- **elements**:
  - page_title: H2 / required / 「我的工單」，Noto Sans TC 20px SemiBold，色 #1E293B
- **states**:
  - default: 顯示標題

### Section: tab_bar

- **layout**: 固定於 header 下方（sticky），高度 48px，背景白色，下方 1px border #E2E8F0，三等分
- **elements**:
  - tab_active: Tab / required / 「進行中」，active 底線 2px #2563EB，字體 14px SemiBold #2563EB，touch area 全寬/3 × 48px（≥ 44×44px）
    - 包含狀態：`accepted`, `in_progress`, `scope_changed`, `material_pending`, `delayed`
    - 顯示數量 Badge（如有工單）：圓形紅底白字，右上角
  - tab_pending: Tab / required / 「待確認」，inactive 字體 #64748B，touch area 同上
    - 包含狀態：`completed`（等待客戶/管理確認）
  - tab_history: Tab / required / 「歷史」，inactive 字體 #64748B，touch area 同上
    - 包含狀態：`confirmed`, `archived`
- **states**:
  - default: 「進行中」tab active
  - switching: tab 切換時內容區 fade 過渡（150ms）
- **gestures**:
  - 點擊 tab 切換
  - 左右滑動內容區切換 tab（swipe gesture）

### Section: order_card_list

- **layout**: 垂直可捲動列表，padding 16px，gap 12px，padding-bottom 預留 bottom_navigation 高度（56px + safe-area）
- **elements**:
  - order_card: Card / repeated / 全寬，圓角 12px，背景白色，shadow-sm，padding 16px，包含：
    - card_top_row: Flex Row / required /
      - wo_number: Body SM / required / 工單編號，字體 Inter 13px，色 #64748B
      - status_badge: Badge / required / 狀態標籤：
        - `accepted`：藍色 Badge「已接單」
        - `in_progress`：琥珀色 Badge「作業中」
        - `scope_changed`：紫色 Badge「範圍變更」
        - `material_pending`：橘色 Badge「等待材料」
        - `delayed`：紅色 Badge「延遲」
        - `completed`：綠色 Badge「已完工」
        - `confirmed`：灰色 Badge「已確認」
        - `archived`：灰色 Badge「已歸檔」
    - address_text: Body MD Bold / required / 客戶地址，Noto Sans TC 15px SemiBold，最多 2 行
    - navigate_shortcut: IconButton / required / 右側 Navigation 圖示，touch area 44×44px，點擊開啟 Google Maps 導航
    - schedule_row: Flex Row / required /
      - calendar_icon: Icon / required / Calendar 16px
      - scheduled_time: Body SM / required / 預約時間，14px，色 #64748B
    - device_row: Flex Row / required /
      - lock_icon: Icon / required / Lock 16px
      - brand_model: Body SM / required / 鎖具品牌型號，14px
    - sla_countdown: CountdownBadge / conditional / SLA 倒數計時（僅進行中狀態顯示）：
      - 充裕（>2h）：綠底白字
      - 警告（1-2h）：橘底白字
      - 危急（<1h）：紅底白字，脈衝動畫
- **states**:
  - default: 依時間排序的工單列表
  - loading: 3 張 skeleton 卡片
  - empty_active: 插圖（技師休息中）+ 「目前沒有進行中的工單」+ 「前往案件池接單」按鈕（min 44×44px）→ 跳轉 `/pool`
  - empty_pending: 「沒有待確認的工單」
  - empty_history: 「還沒有歷史紀錄」
  - error: 錯誤訊息 + 重試按鈕
  - pull_to_refresh: 頂部下拉 Spinner
- **gestures**:
  - 點擊卡片 → 導航至 `/my-orders/{id}`
  - 點擊導航圖示 → 開啟 Google Maps
  - 下拉 → pull-to-refresh
  - 左右滑動 → 切換 tab

### Section: detail_header（詳情頁）

- **layout**: 頂部全寬色條，高度 64px，包含返回按鈕 + 狀態 + 工單編號
- **elements**:
  - back_btn: IconButton / required / 左上角 ChevronLeft，touch area 44×44px，返回 `/my-orders`
  - status_bar: FullWidthBar / required / 全寬色條，高度 48px，根據狀態變色：
    - `accepted`：#2563EB（藍）
    - `in_progress`：#F59E0B（琥珀）
    - `scope_changed`：#8B5CF6（紫）
    - `material_pending`：#F97316（橘）
    - `delayed`：#EF4444（紅）
    - `completed`：#10B981（綠）
    - `confirmed`：#6B7280（灰）
  - status_text: Body MD Bold / required / 狀態中文名稱，白色字體，16px Bold
  - wo_number: Body SM / required / 工單編號，白色字體 80% opacity，13px

### Section: customer_section

- **layout**: 單欄 padding 16px，背景白色，margin-top 8px，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「客戶資訊」，Noto Sans TC 16px SemiBold，色 #1E293B
  - customer_name: Body MD / required / 客戶姓名，15px
  - phone_button: Button Primary / required / 圖示 Phone + 電話號碼，full-width，高度 48px，背景 #2563EB，點擊觸發 `tel:` 系統撥號，字體 16px Bold 白色
  - address_button: Button Outline / required / 圖示 MapPin + 「導航至現場」，full-width，高度 48px，邊框 #2563EB，字體 #2563EB 16px，點擊開啟 Google Maps 導航
  - special_notes_card: AlertCard / optional / 背景 #FEF3C7，左邊框 4px #F59E0B，padding 12px，圖示 AlertTriangle + 特殊備註文字（Noto Sans TC 14px），例「大樓需要門禁卡，請先聯繫管理員」
- **states**:
  - default: 顯示客戶資訊
  - no_notes: special_notes_card 不顯示
  - calling: phone_button 短暫顯示「撥號中...」狀態

### Section: device_section

- **layout**: 單欄 padding 16px，背景白色，margin-top 8px，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「鎖具資訊」，16px SemiBold
  - brand_model_card: Card / required / 品牌 Logo 圖片（48×48px，圓角 8px）+ 品牌名稱 + 型號，padding 12px，背景 #F8FAFC
  - checklist_title: Body SM Bold / required / 「作業前檢查清單」，14px SemiBold，色 #64748B
  - auto_checklist: CheckboxList / required / 根據品牌型號自動生成：
    - 每個 item：Checkbox（24×24px，touch area 44×44px）+ 文字標籤
    - 範例項目：
      - 「已準備 {品牌} 專用工具組」
      - 「已確認電源狀況」
      - 「已閱讀安全注意事項」
      - 「已拍攝施工前照片」
    - 已勾選項目顯示刪除線 + 色 #94A3B8
- **states**:
  - default: 清單全部未勾選
  - partial: 部分勾選
  - complete: 全部勾選，標題旁顯示綠色 Checkmark

### Section: problem_card_section

- **layout**: 單欄 padding 16px，背景白色，margin-top 8px，圓角 12px，shadow-sm
- **elements**:
  - collapsible_header: Flex Row / required /
    - section_title: H3 / required / 「問題診斷摘要」，16px SemiBold
    - toggle_icon: IconButton / required / ChevronDown/ChevronUp，touch area 44×44px
  - symptom_text: Body MD / required / 「症狀：」+ 症狀描述，15px
  - diagnosis_text: Body MD / required / 「AI 診斷：」+ 推理摘要，15px，色 #64748B
  - confidence_badge: Badge / optional / AI 信心度（例「信心度 85%」），背景 #DBEAFE
- **states**:
  - collapsed: 僅顯示 header，預設收合
  - expanded: 展開顯示完整內容，動畫 200ms
- **copy_constraints**: 症狀最多 100 字，診斷摘要最多 200 字

### Section: action_section

> 此區塊根據工單狀態動態切換，為頁面核心操作區。

- **layout**: 單欄 padding 16px，背景白色，margin-top 8px，圓角 12px，shadow-sm

#### 狀態：`accepted`（已接單，前往現場）

- **elements**:
  - navigate_btn: Button Primary / required / 圖示 Navigation + 「導航前往」，full-width，高度 56px，背景 #2563EB，字體 18px Bold，點擊開啟 Google Maps 導航
  - arrived_btn: Button CTA / required / 圖示 MapPin + 「已到達現場」，full-width，高度 56px，背景 #F59E0B，字體 18px Bold 白色，margin-top 12px
    - 點擊 → 確認 Dialog「確定已到達現場？」→ 確認 → PATCH status → `in_progress`
- **states**:
  - default: 兩個按鈕都可點擊
  - navigating: navigate_btn 顯示「導航中...」（Google Maps 已開啟）
  - arriving: arrived_btn Spinner + 「確認中...」，disabled

#### 狀態：`in_progress`（作業中）

- **elements**:
  - progress_title: H3 / required / 「作業進度」，16px SemiBold
  - sop_checklist: CheckboxList / required / SOP 步驟清單（根據服務類型自動生成），每項：
    - Checkbox（24×24px，touch area 44×44px）+ 步驟描述
    - 勾選時記錄時間戳
  - report_issue_section: CollapsibleSection / required /
    - trigger_btn: Button Outline / required / 圖示 AlertTriangle + 「回報異常」，full-width，高度 48px，紅色邊框
    - issue_type_selector: RadioGroup / required（展開時）/ 三個選項：
      - 「範圍變更」（scope_change）— 工作內容超出原報價
      - 「需要材料」（material_needed）— 缺少零件需調貨
      - 「施工延遲」（delay）— 無法按時完成
    - issue_note: TextArea / required（展開時）/ placeholder「請描述異常狀況...」，max 200 字，min 高度 80px
    - submit_issue_btn: Button Destructive / required / 「提交異常報告」，高度 48px
    - 每個 radio 選項 touch area ≥ 44×44px
  - photo_capture_section: SectionBlock / required /
    - photo_title: Body SM Bold / required / 「施工照片（至少 1 張）」
    - photo_grid: Grid 3-column / required / 已拍照片縮圖（80×80px，圓角 8px）
    - add_photo_btn: Button Outline / required / 圖示 Camera + 「拍照」，寬度 80px 高度 80px（符合 grid），touch area 80×80px
    - 點擊 → 開啟系統相機（`<input type="file" accept="image/*" capture="environment">`）
    - 照片自動壓縮至 1MB 以下再上傳
  - complete_btn: Button CTA / required / 「完成作業」，full-width，高度 56px，背景 #F59E0B，字體 18px Bold 白色
    - **disabled 條件**：SOP 清單未全部勾選 OR 照片數量 < 1
    - disabled 狀態：背景 #CBD5E1，不可點擊，底部提示文字說明缺少什麼
- **states**:
  - default: 顯示清單 + 拍照 + 完成按鈕（disabled）
  - checklist_progress: 已勾 X / 總共 Y，進度條
  - photo_uploading: 照片位置顯示上傳進度環
  - issue_reporting: 異常回報區域展開
  - ready_to_complete: 所有條件滿足，complete_btn 啟用（#F59E0B）
  - completing: complete_btn Spinner + 「提交中...」

#### 狀態：`scope_changed`（範圍變更，需新報價）

- **elements**:
  - scope_change_notice: AlertCard / required / 背景 #F3E8FF，「工作範圍已變更，請提交新報價」
  - quote_form: Form / required /
    - item_list: DynamicList / required / 可新增/刪除項目
      - item_row: Flex Row / 項目名稱（Input, flex-grow）+ 金額（Input type=number, width 120px）+ 刪除按鈕（touch area 44×44px）
    - add_item_btn: Button Ghost / required / 圖示 Plus + 「新增項目」，min touch 44×44px
    - total_display: Body LG Bold / required / 「報價總計：${amount}」，自動加總，18px Bold 色 #1E293B
    - submit_quote_btn: Button Primary / required / 「提交新報價」，full-width，高度 48px
- **states**:
  - default: 空白表單，一個預設項目 row
  - filled: 已填入項目
  - submitting: submit_quote_btn Spinner
  - submitted: 成功 Toast + 等待客戶確認狀態

#### 狀態：`material_pending`（等待材料）

- **elements**:
  - material_status_card: Card / required / 背景 #FFF7ED，顯示材料請求狀態：
    - 請求的材料列表
    - 各材料狀態（已訂購/運送中/已到貨）
    - 預計到貨時間
  - material_arrived_btn: Button Primary / required / 「材料已到，繼續作業」，full-width，高度 48px
    - 點擊 → PATCH status → `in_progress`
- **states**:
  - default: 等待材料
  - material_arrived: 按鈕可用

### Section: completion_report_form

> 點擊「完成作業」後滑入的表單頁面（full-screen overlay 或 push route）。

- **layout**: 全螢幕表單，背景 #F8FAFC，padding 16px，可垂直捲動，底部固定提交按鈕

- **elements**:

  - form_header: Flex Row / required / 「完工報告」H2 20px SemiBold + 關閉按鈕（X，touch area 44×44px，返回 detail）

  - service_items_section: SectionBlock / required /
    - section_title: H3 / required / 「服務項目」，16px SemiBold
    - service_checklist: CheckboxList / required / 預設選項（根據服務類型）：
      - 「鎖芯更換」「電池更換」「韌體更新」「門框調整」「全鎖安裝」等
      - 每項 touch area ≥ 44×44px
    - custom_item_input: Input + AddButton / optional / 「新增自訂項目」，min touch 44×44px

  - parts_used_section: SectionBlock / required /
    - section_title: H3 / required / 「使用零件」，16px SemiBold
    - parts_list: DynamicList / required /
      - part_row: Flex Row / 零件名稱（Input）+ 數量（Stepper, min 1, touch area 44×44px）+ 單價（Input type=number）
      - 小計自動計算顯示
    - add_part_btn: Button Ghost / required / 圖示 Plus + 「新增零件」，min touch 44×44px
    - parts_total: Body MD Bold / required / 「零件小計：${amount}」

  - photo_gallery_section: SectionBlock / required /
    - section_title: H3 / required / 「施工照片（至少 2 張）」，16px SemiBold
    - photo_requirement: Caption / required / 「需包含：施工前、施工後照片」，色 #64748B
    - photo_grid: Grid 3-column / required / 照片縮圖（圖片 ratio 1:1，圓角 8px）
      - 每張照片可點擊 → 全螢幕預覽（Lightbox，pinch-to-zoom，左右滑動切換）
      - 每張照片右上角刪除按鈕（touch area 44×44px）
    - add_photo_btn: DashedCard / required / 虛線邊框 + Camera 圖示 + 「拍照/上傳」，80×80px，touch area 80×80px
    - photo_count: Caption / required / 「{N}/2 張（最少 2 張）」，未達標時紅色
  - **photo_validation**: 照片不足 2 張時提交按鈕 disabled + 紅色提示

  - functional_test_section: SectionBlock / required /
    - section_title: H3 / required / 「功能測試結果」，16px SemiBold
    - test_items: TestToggleList / required / 四項測試：
      - 「門鎖開啟」：Pass(綠)/Fail(紅) Toggle，touch area 44×44px
      - 「自動上鎖」：Pass/Fail Toggle
      - 「鍵盤回應」：Pass/Fail Toggle
      - 「電池電量」：Pass/Fail Toggle + 電量輸入（如 Pass，Input type=number + "%" suffix）
    - 每項測試 Fail 時展開備註 TextArea（「請說明異常」，min 高度 60px）
    - test_summary: Badge / required / 全部 Pass → 綠色「全部通過」/ 有 Fail → 紅色「{N} 項異常」

  - signature_section: SectionBlock / required /
    - section_title: H3 / required / 「客戶簽名」，16px SemiBold
    - signature_instruction: Caption / required / 「請客戶在下方簽名確認」，色 #64748B
    - signature_pad: Canvas / required / 高度 200px，full-width，border 2px dashed #CBD5E1，圓角 12px，背景白色
      - 觸控繪製簽名（touch events，筆觸寬度 2px，色 #1E293B）
      - 繪製時 border 轉為 solid #2563EB
    - clear_signature_btn: Button Ghost / required / 「清除重簽」，min touch 44×44px
    - signature_status: Caption / required / 未簽名時：紅色「尚未簽名」/ 已簽名：綠色「已取得簽名」

  - amount_summary: Card / required / 背景 #F0FDF4，padding 16px，圓角 12px，margin-top 16px
    - labor_fee: InfoRow / required / 「工資」+ 金額
    - parts_fee: InfoRow / required / 「零件費用」+ 金額
    - commission_rate: InfoRow / required / 「佣金比例」+ 比例值
    - commission_amount: InfoRow Bold / required / 「您的佣金」+ 金額，18px Bold 色 #059669
    - total_amount: InfoRow Bold / required / 「客戶應付總額」+ 金額，20px Bold 色 #1E293B，上方分隔線

  - submit_area: FixedBottom / required / 固定底部，背景白色，padding 16px + safe-area-inset-bottom，shadow-up
    - submit_btn: Button CTA / required / 「提交完工報告」，full-width，高度 56px，背景 #F59E0B，字體 18px Bold 白色
    - **disabled 條件**：照片 < 2 張 OR 未簽名 OR 功能測試未全部完成
    - disabled 狀態：背景 #CBD5E1，底部顯示缺少項目提示（紅色小字）

- **states**:
  - default: 空白表單
  - filling: 部分填寫
  - ready: 所有必填完成，submit_btn 啟用
  - submitting: submit_btn Spinner + 「提交中...」，全表單 disabled
  - success: 全螢幕成功動畫（Checkmark + 「完工報告已提交」），2 秒後返回 `/my-orders`
  - upload_error: Toast「照片上傳失敗，請重試」
  - offline_draft: 表單頂部黃色 Banner「離線模式 — 報告已儲存為草稿，上線後自動提交」

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

1. **列表頁載入**：
   - GET `/api/v1/technicians/me/orders` → 分類至三個 tab
   - 預設開啟「進行中」tab

2. **查看工單詳情**：
   - 點擊卡片 → 導航至 `/my-orders/{id}` → GET `/api/v1/work-orders/{id}`
   - 渲染 detail_header + customer_section + device_section + problem_card + action_section

3. **已接單 → 到達現場**：
   - 點「導航前往」→ 開啟 Google Maps
   - 到達後點「已到達現場」→ 確認 Dialog → PATCH status `in_progress`
   - 自動記錄到達時間 → SLA 計時參考

4. **作業中流程**：
   - 依 SOP checklist 逐項勾選
   - 拍攝施工照片（相機直拍 → 自動壓縮 → POST upload）
   - 若遇異常 → 展開「回報異常」→ 選擇類型 + 填寫說明 → 提交
   - 全部 checklist 勾選 + ≥ 1 張照片 →「完成作業」按鈕啟用

5. **完工報告提交**：
   - 點「完成作業」→ 進入 completion_report_form
   - 填寫：服務項目 → 使用零件 → 補充照片（≥ 2 張）→ 功能測試 → 客戶簽名
   - 系統自動計算金額
   - 點「提交完工報告」→ POST `/api/v1/work-orders/{id}/completion-report` → 成功返回列表
   - 工單狀態 → `completed`，出現在「待確認」tab

6. **範圍變更流程**：
   - 回報 scope_change → 狀態轉 `scope_changed`
   - 填寫新報價項目 → POST 提交 → 等待客戶確認
   - 客戶確認後（Push Notification）→ 狀態回 `in_progress`

7. **材料等待流程**：
   - 回報 material_needed → 狀態轉 `material_pending`
   - 材料到貨 → 點「材料已到」→ 狀態回 `in_progress`

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Mobile (<480px) | 單欄全寬（主要設計） | 標準體驗，所有功能完整 |
| Tablet (481–768px) | 單欄 max-width 480px 居中 | 左右留白 |
| Desktop (769px+) | 不支援（技師端為純 Mobile PWA） | 顯示「請使用手機操作」提示頁 |

### 資料更新策略

- **列表頁**：每次進入頁面重新取得，pull-to-refresh 手動更新
- **詳情頁**：進入時取得最新資料，狀態變更透過 WebSocket 即時更新
- **完工報告草稿**：每 10 秒自動儲存至 IndexedDB（防止意外關閉遺失）
- **照片上傳**：拍攝後立即背景上傳，不阻塞表單填寫

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - GET `/api/v1/technicians/me/orders` — 取得技師所有工單。查詢參數：`status`（可多選）, `page`, `per_page`
  - GET `/api/v1/work-orders/{id}` — 取得單一工單完整詳情（含客戶資訊、鎖具資訊、ProblemCard、SOP checklist）
  - PATCH `/api/v1/work-orders/{id}/status` — 更新工單狀態。Body: `{ status, note?, issue_type? }`
  - POST `/api/v1/work-orders/{id}/completion-report` — 提交完工報告。Body: `{ service_items[], parts_used[], test_results{}, signature_image_url, photos[], total_amount }`
  - POST `/api/v1/work-orders/{id}/photos` — 上傳施工照片（multipart/form-data）。回傳 `{ photo_id, url, thumbnail_url }`
  - POST `/api/v1/work-orders/{id}/quote` — 提交範圍變更新報價。Body: `{ items[{name, amount}], total, note }`
- **error_cases**:
  - 網路錯誤：
    - 列表頁：顯示快取資料 + 離線 Banner
    - 詳情頁：顯示快取資料（可能非最新）
    - 完工報告：儲存至 IndexedDB 草稿，Banner 提示「離線模式 — 上線後自動提交」
    - 照片上傳：加入背景上傳佇列（Background Sync API）
  - API 錯誤（5xx）：Toast「伺服器忙碌中」+ 重試按鈕
  - 狀態衝突（409）：Toast「工單狀態已變更，重新載入」+ 自動重新取得
  - 權限不足（401/403）：導向登入頁
  - 照片上傳失敗：Toast + 重試按鈕，不影響其他表單填寫

---

## [EXCEPTION TO GLOBAL RULES]

- **completion_report_form 為全螢幕 overlay**：覆蓋整個畫面（含 BottomNav），提供沉浸式表單填寫體驗，避免誤觸導航
- **signature_pad 使用 Canvas touch 事件**：需攔截頁面滑動手勢（`touch-action: none`），防止簽名時頁面跟著滾動
- **照片自動壓縮**：前端使用 `canvas.toBlob()` 壓縮至 1MB 以下再上傳，不傳原檔
- **SLA 倒數計時**：使用前端 `setInterval` 每秒更新，不依賴 API polling
- **detail_header 色條**：此頁面使用全寬色條取代標準 AppBar，不受 container padding 限制

---

## [ACCEPTANCE CRITERIA]

### 列表頁
- [ ] 三個 Tab 正確篩選工單：進行中 / 待確認 / 歷史
- [ ] 進行中 Tab 顯示工單數量 Badge
- [ ] 工單卡片顯示：編號、狀態 Badge、地址、時間、品牌型號
- [ ] SLA 倒數正確顯示且顏色隨剩餘時間變化（綠/橘/紅）
- [ ] 點擊導航圖示開啟 Google Maps
- [ ] Pull-to-refresh 正常運作
- [ ] 左右滑動可切換 Tab
- [ ] Loading / Error / Empty 三態完備

### 詳情頁
- [ ] 頂部狀態色條根據工單狀態正確變色
- [ ] 電話按鈕觸發系統撥號（`tel:` protocol）
- [ ] 導航按鈕開啟 Google Maps
- [ ] 特殊備註以警示卡片樣式顯示
- [ ] 品牌型號自動生成作業前檢查清單
- [ ] ProblemCard 可展開/收合

### 作業中流程
- [ ] SOP checklist 可逐項勾選
- [ ] 拍照按鈕開啟系統相機
- [ ] 照片自動壓縮 + 背景上傳
- [ ] 「回報異常」展開三種類型選擇
- [ ] 「完成作業」按鈕在 checklist 全勾 + ≥ 1 照片後啟用
- [ ] disabled 狀態顯示缺少項目提示

### 完工報告
- [ ] 服務項目 checklist 可勾選 + 自訂新增
- [ ] 零件列表可動態新增/刪除，小計自動計算
- [ ] 照片 grid 顯示縮圖，點擊全螢幕預覽
- [ ] 照片不足 2 張時紅色警示 + 提交按鈕 disabled
- [ ] 功能測試 Pass/Fail toggle 正常運作
- [ ] Fail 項目展開備註欄位
- [ ] 簽名板觸控繪製流暢，不觸發頁面滾動
- [ ] 清除重簽功能正常
- [ ] 金額自動計算（工資 + 零件 = 總額，佣金 = 工資 × 比例）
- [ ] 提交成功後動畫 + 返回列表
- [ ] 離線模式：草稿自動儲存 + 上線後同步
- [ ] 所有可點擊元素 touch target ≥ 44×44px
- [ ] 操作按鈕高度 ≥ 48px，主要 CTA ≥ 56px
- [ ] BottomNav 正確顯示，我的工單 Tab active
