# Page-Level Prompt: 技師端 — 工單非 Happy Path 子流程（6 頁合一）

> 技師 PWA 工單現場例外處理與交付收尾。涵蓋 T5 範圍變更、T6 缺料回報、T7 延遲通知、T8 門面外觀檢核、T9 雙方電子簽章、T10 我的排班。
> 對齊 `E5x--work-order-interaction-flows` Flow 3/4/5/10、`specs/e-signature-spec.md`、`specs/inventory-management-spec.md`、`specs/sla-availability-spec.md`、`E5x--frontend-architecture.md` §3.3 / §8.5 / §8.7。

---

## [PAGE META]

- **page_name**: 工單子流程 Work Order Subflows
- **route_path**:
  - `/my-orders/[id]/scope-change`（T5 範圍變更申請）
  - `/my-orders/[id]/material-request`（T6 缺料回報）
  - `/my-orders/[id]/delay`（T7 延遲通知）
  - `/my-orders/[id]/door-check`（T8 門面外觀檢核）
  - `/my-orders/[id]/signature`（T9 雙方電子簽章）
  - `/account/schedule`（T10 我的排班）
- **page_type**: mobile-first form set + read-only calendar（6 個路由共用設計語彙）
- **primary_goal**: 技師在現場遇到非 Happy Path 例外時（範圍追加、缺料、延遲、外觀變更、收尾簽章），能以單手操作快速提交結構化資料，保障雙方權益並維持 SLA 與合規
- **secondary_goal**: 讓技師自主管理可服務時段（T10），減少管理員介入派工排程
- **target_users**:
  - 主要：已接單且正在作業中的外派技師（現場 Mobile PWA，常伴隨弱網/隧道/戶外強光）
  - 次要：客戶（在技師手機上現場簽名 / 透過 LINE 收通知並回應）
- **entry_point**:
  - T5–T9：`/my-orders/[id]` 詳情頁 action_section 的「回報異常」或「完工收尾」按鈕 push 進入子路由
  - T10：底部導航第 3 個 Tab「帳戶」→ 「我的排班」/ 管理員推播「排班已更新」通知點擊
- **expected_time_on_page**: T5 3–8 分鐘、T6 2–4 分鐘、T7 1–2 分鐘、T8 2–5 分鐘、T9 1–3 分鐘、T10 1–5 分鐘

---

## [STRUCTURE: SECTIONS]

> 6 個路由依子流程獨立列出 sections。共用 `offline_queue_indicator` 與 `sub_page_header` 於所有子路由頂部。

### 共用結構

1. **sub_page_header**（所有子路由）
   - section_type: header
   - section_purpose: 返回鈕 + 子流程標題 + 工單編號徽章

2. **offline_queue_indicator**（所有子路由）
   - section_type: status_banner
   - section_purpose: 離線模式提示 + 待同步動作數量

### T5 `/my-orders/[id]/scope-change` 範圍變更申請

3. **scope_context_card**
   - section_type: info_block
   - section_purpose: 顯示原工單摘要（原報價、原工項、預估工時）供對照

4. **scope_reason_form**
   - section_type: form
   - section_purpose: 變更事由說明 + 現場照片佐證

5. **scope_items_editor**
   - section_type: dynamic_list_form
   - section_purpose: 新增/編輯追加工項（名稱、單價、數量、小計）

6. **scope_price_compare**
   - section_type: comparison_card
   - section_purpose: 原報價 vs 新報價並列，差額百分比 + 超標警示

7. **scope_submit_area**
   - section_type: fixed_bottom_cta
   - section_purpose: 提交申請按鈕 + 提交後等待客戶核准狀態說明

### T6 `/my-orders/[id]/material-request` 缺料回報

8. **material_context_card**
   - section_type: info_block
   - section_purpose: 當前工單工項與預設材料清單

9. **material_missing_list**
   - section_type: dynamic_list_form
   - section_purpose: 缺件清單（品牌/型號/數量），支援從庫存主檔搜尋選擇

10. **material_alternative_picker**
    - section_type: form
    - section_purpose: 替代方案選擇（是否可用替代品、替代型號、差價說明）

11. **partial_completion_decision**
    - section_type: radio_group
    - section_purpose: 現場決策（完全等待 / 部分完工 / 客戶取消）

12. **material_submit_area**
    - section_type: fixed_bottom_cta
    - section_purpose: 提交缺料回報並切換工單狀態為 `material_pending`

### T7 `/my-orders/[id]/delay` 延遲通知

13. **delay_reason_selector**
    - section_type: radio_group
    - section_purpose: 延遲事由快選（塞車 / 前案超時 / 設備問題 / 其他）

14. **new_eta_picker**
    - section_type: datetime_picker
    - section_purpose: 新預計到達/完工時間選擇

15. **delay_severity_preview**
    - section_type: preview_card
    - section_purpose: 根據新 ETA 預覽延遲等級與對 SLA 的影響提示

16. **delay_submit_area**
    - section_type: fixed_bottom_cta
    - section_purpose: 送出延遲通知（自動推 LINE 客戶 + > 2h 升級管理員）

### T8 `/my-orders/[id]/door-check` 門面外觀檢核

17. **door_check_stepper**
    - section_type: stepper
    - section_purpose: 三步驟視覺引導（抵達拍 → 施工中 → 完工拍）

18. **arrival_photo_group**
    - section_type: photo_capture_grid
    - section_purpose: 抵達時拍原始狀態（門扇全貌 / 側板特寫 / 切割區標記 / 現有孔位，≥ 4 張）

19. **appearance_notice_sheet**
    - section_type: consent_sheet
    - section_purpose: 自動生成「門外觀變更告知書」供客戶現場過目

20. **completion_photo_group**
    - section_type: photo_capture_grid
    - section_purpose: 完工後對比照（同角度 ≥ 2 張），與抵達照自動疊圖比對

21. **customer_field_confirm**
    - section_type: dual_action
    - section_purpose: 客戶現場按讚（同意）或拒絕 + 文字備註

### T9 `/my-orders/[id]/signature` 雙方電子簽章

22. **signature_intro_card**
    - section_type: info_block
    - section_purpose: 顯示簽章文件類型（WORK_ORDER_COMPLETION / APPEARANCE_CHANGE / SCOPE_CHANGE）+ 租戶法律等級

23. **technician_signature_pad**
    - section_type: canvas_signature
    - section_purpose: 技師簽章區（上半部）

24. **customer_signature_pad**
    - section_type: canvas_signature
    - section_purpose: 客戶簽章區（下半部）+ 客戶姓名口頭確認 checkbox

25. **signature_metadata_preview**
    - section_type: metadata_card
    - section_purpose: 即時顯示將寫入稽核的元資料（時間戳、GPS、IP、裝置指紋）

26. **signature_submit_area**
    - section_type: fixed_bottom_cta
    - section_purpose: 雙簽完成 → 生成 PDF → 寄 LINE 給客戶 + 寫 `audit-events`

### T10 `/account/schedule` 我的排班

27. **schedule_month_header**
    - section_type: header_with_switcher
    - section_purpose: 月份切換 + 本月休假/備勤額度摘要

28. **schedule_calendar_view**
    - section_type: month_grid
    - section_purpose: 唯讀月曆，顯示每日工單數、上/下班時段、休假/備勤標記

29. **leave_request_form**
    - section_type: bottom_sheet_form
    - section_purpose: 申請休假表單（日期區間、事由、是否影響已接工單）

30. **standby_request_form**
    - section_type: bottom_sheet_form
    - section_purpose: 申請備勤加班表單（日期、時段、備註）

31. **close_today_accept_switch**
    - section_type: toggle_action
    - section_purpose: 關閉本日接單 toggle（1h 內無工單立即生效，否則完工後生效）

32. **pending_requests_list**
    - section_type: list
    - section_purpose: 尚未審核的休假/備勤申請列表 + 取消按鈕

### 共用底部導航

33. **bottom_navigation**
    - section_type: navigation
    - section_purpose: 三 Tab 底部導航列（T5–T9 被 sub-page 覆蓋隱藏、T10 顯示且「帳戶」active）

---

## [SECTION COMPONENT SPEC]

### Section: sub_page_header（共用）

- **layout**: 固定頂部 sticky，高度 56px，背景白色，下方 1px border #E2E8F0，z-index 20，padding 0 16px，`flex items-center justify-between`
- **elements**:
  - back_btn: IconButton / required / 左側 ChevronLeft 24×24px，touch area 44×44px，點擊返回 `/my-orders/[id]` 詳情頁（T10 返回 `/account`）
  - page_title: H2 / required / Noto Sans TC 18px SemiBold 色 #1E293B，最多 10 字（例：「範圍變更申請」「缺料回報」「延遲通知」「門面檢核」「雙方簽章」「我的排班」）
  - wo_badge: Badge / optional（T5–T9）/ 工單編號簡碼（例 `#0032`），背景 #F1F5F9 字體 13px 色 #64748B，點擊彈出完整編號 Tooltip
- **states**:
  - default: 三元素正常顯示
  - submitting: back_btn disabled（防止中斷提交）
- **copy_constraints**: 標題最多 10 個繁體中文字，超過截斷

### Section: offline_queue_indicator（共用）

- **layout**: sticky 於 sub_page_header 下方，全寬，高度 40px，z-index 19，背景 #FEF3C7，文字 #92400E，`flex items-center gap-2 px-4`
- **elements**:
  - offline_icon: Icon / required / WifiOff 16px
  - queue_text: Body SM / required / 「離線模式 — 已有 {N} 個動作待同步」，Noto Sans TC 13px
  - sync_hint: Caption / optional / 「恢復連線後自動送出」，字體 12px
- **states**:
  - hidden: `navigator.onLine === true` 且佇列為空時不顯示
  - visible: 離線或有待同步項目時 slideDown 200ms
  - syncing: 文字改「同步中 {已同步}/{總數}...」+ Spinner
  - synced: 背景轉 #D1FAE5 文字「已全部同步」，2 秒後淡出

---

### Section: scope_context_card（T5）

- **layout**: 單欄 padding 16px，背景 #F8FAFC，margin 16px，圓角 12px，無 shadow（次要資訊區）
- **elements**:
  - section_title: Caption / required / 「原工單摘要」，色 #64748B 字體 12px
  - original_items_list: InfoList / required / 原工項列表（名稱 + 單價 × 數量），每行 14px
  - original_total: InfoRow Bold / required / 「原報價：${amount}」，18px SemiBold 色 #1E293B
  - original_duration: InfoRow / required / 圖示 Clock + 「預估工時 {N} 小時」
- **states**:
  - default: 顯示原始資料
  - loading: skeleton 3 行

### Section: scope_reason_form（T5）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「變更原因」，16px SemiBold
  - reason_textarea: TextArea / required / placeholder「現場發現 ...（例：鎖匣內機構變形需更換、門框需重新校正）」，min 高度 100px，字體 15px，max 300 字，字數 counter 右下角
  - evidence_photo_title: Body SM Bold / required / 「現場佐證照片（至少 2 張）」，14px
  - photo_grid: Grid 3-column / required / gap 8px，每張縮圖 ratio 1:1 圓角 8px
  - add_photo_btn: DashedCard / required / 虛線邊框 + Camera 圖示 + 「拍照」，80×80px，touch area 80×80px，呼叫 `<input type="file" accept="image/*" capture="environment">`，前端壓縮至 1MB
  - photo_counter: Caption / required / 「{N}/2 張」，未達 2 張時紅色
- **states**:
  - default: 空白表單
  - filled: 已填寫
  - photo_uploading: 照片縮圖位置顯示上傳進度環
  - photo_queued_offline: 照片縮圖右下角顯示 ⏱ 圖示（暫存本地，上線後上傳）
- **copy_constraints**: 事由最多 300 字

### Section: scope_items_editor（T5）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「追加工項」，16px SemiBold
  - item_row: DynamicRow / repeated / padding 12px，背景 #F8FAFC，圓角 8px，margin-bottom 8px，每列：
    - item_name_input: Input / required / placeholder「工項名稱」，高度 48px，字體 16px，`flex-grow`
    - item_price_input: Input type=number / required / placeholder「單價」，寬度 100px 高度 48px，字體 16px，右側「元」suffix
    - item_qty_stepper: Stepper / required / `-` 按鈕 44×44px + 數字 + `+` 按鈕 44×44px，min 1 max 99
    - subtotal_text: Caption / required / 「小計 ${price × qty}」，色 #64748B
    - delete_btn: IconButton / required / Trash 圖示 24×24px，touch area 44×44px，點擊確認後刪除該列
  - add_item_btn: Button Outline / required / full-width 圖示 Plus + 「新增工項」，高度 48px，邊框 #2563EB 字體 #2563EB 16px
- **states**:
  - default: 1 個預設空白項目
  - filled: ≥ 1 個項目已填
  - empty: 全部刪除後顯示「至少保留 1 個項目」紅色提示，add_item_btn 脈衝動畫
- **copy_constraints**: 工項名稱最多 30 字

### Section: scope_price_compare（T5）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px，shadow-sm
- **elements**:
  - compare_row: Flex Row / required / 兩欄並列
    - original_block: Block / 左欄 / 「原報價」Caption 12px 色 #64748B + 金額 20px Bold
    - arrow_icon: Icon / required / ArrowRight 16px 色 #94A3B8
    - new_block: Block / 右欄 / 「新報價」Caption 12px + 金額 20px Bold（依差額變色：增加 → #DC2626 / 持平 → #1E293B / 減少 → #059669）
  - diff_badge: Badge / required / 「+${diff}（+{pct}%）」，差額 > 0 時背景 #FEE2E2 字體 #B91C1C / 差額 < 0 時背景 #D1FAE5 字體 #065F46
  - threshold_alert: AlertCard / conditional / 當 `new_price > original_price × 2` 時顯示：
    - 背景 #FEE2E2，左邊框 4px #DC2626，padding 12px，圖示 AlertTriangle + 「超過原報價 2 倍，將進入主管審核流程（預計 1–4 小時）」字體 14px
- **states**:
  - below_threshold: 無 threshold_alert
  - above_threshold: 顯示紅色 threshold_alert + 提交按鈕文案改「送出並等待主管審核」

### Section: scope_submit_area（T5）

- **layout**: 固定底部 sticky，背景白色，padding 16px + safe-area-inset-bottom，shadow-up，z-index 15
- **elements**:
  - submit_btn: Button CTA / required / 「送出範圍變更申請」，full-width 高度 56px 背景 #F59E0B 字體 18px Bold 白色
  - post_submit_hint: Caption / optional（提交成功後顯示）/ 「已推送 LINE 給客戶，24 小時內回覆否則管理員介入」，色 #64748B 12px
- **states**:
  - default: 啟用
  - disabled: 事由空 OR 工項數 < 1 OR 照片 < 2 張 → 背景 #CBD5E1，下方紅色小字列出缺少項目
  - submitting: Spinner + 「提交中...」
  - submitted_waiting_customer: 按鈕改為 disabled 灰色「等待客戶核准」，倒數計時 24h
  - submitted_waiting_supervisor: 按鈕改「等待主管審核」（超標情境）
  - websocket_customer_approved: 全屏 Toast「客戶已核准 ✓」2 秒後返回詳情頁
  - websocket_customer_rejected: Dialog「客戶已拒絕新報價」+ 三選項（僅完成原範圍 / 取消工單 / 電話協商）

---

### Section: material_context_card（T6）

- **layout**: 單欄 padding 16px，背景 #F8FAFC，margin 16px，圓角 12px
- **elements**:
  - section_title: Caption / required / 「工單工項與預設材料」，色 #64748B 12px
  - expected_parts_list: InfoList / required / 預設所需材料（依鎖具型號），每行：名稱 + 規格 + 預設數量

### Section: material_missing_list（T6）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「缺件清單」，16px SemiBold
  - missing_row: DynamicRow / repeated / padding 12px，圓角 8px，背景 #FFF7ED margin-bottom 8px
    - part_picker: SearchableSelect / required / placeholder「搜尋零件主檔...」，點擊彈出全螢幕搜尋（輸入 2 字以上 GET `/api/v1/inventory/parts?q=`），高度 48px
    - selected_part_display: ChipList / required / 已選零件：品牌 Logo + 名稱 + 型號（PN）
    - stock_eta_badge: Badge / required（選擇零件後顯示）/
      - 現貨充足：綠底白字「倉內有貨 {N}」
      - 需調貨：橘底白字「預計 {N} 天到貨」
      - 缺貨：紅底白字「無 ETA 需特別訂購」
    - qty_stepper: Stepper / required / min 1 max 99，控制尺寸 44×44px
    - delete_btn: IconButton / required / 44×44px
  - add_missing_btn: Button Outline / required / 「新增缺件」，full-width 高度 48px
- **states**:
  - default: 空白，一個預設空 row
  - searching: 開啟全螢幕搜尋面板（輸入框 + 結果列表，每列 height 56px）
  - part_selected: 自動帶入 stock_eta_badge（來自 `specs/inventory-management-spec.md`）
- **copy_constraints**: 搜尋關鍵字 ≥ 2 字才發請求

### Section: material_alternative_picker（T6）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px
- **elements**:
  - section_title: H3 / required / 「替代方案」，16px SemiBold
  - has_alternative_toggle: Toggle / required / 「是否可用替代品？」，Switch 44×28px
  - alternative_fields: CollapsibleBlock / conditional（toggle ON 時展開）/
    - alt_part_picker: SearchableSelect / required / 同 material_missing_list 的 part_picker
    - price_diff_input: Input type=number / required / 「替代品差價」，可正可負，suffix「元」
    - alt_note_textarea: TextArea / optional / placeholder「替代說明（客戶能否接受等）」，min 80px max 150 字
- **states**:
  - collapsed: 僅顯示 toggle
  - expanded: 展開欄位，動畫 200ms

### Section: partial_completion_decision（T6）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px
- **elements**:
  - section_title: H3 / required / 「現場決策」，16px SemiBold
  - radio_group: RadioGroup / required / 三選項，每選項 touch area 全寬 × 56px：
    - option_wait: Radio + Label / 「完全等待備料到貨（工單維持 `material_pending`）」
    - option_partial: Radio + Label / 「部分完工（完成可做部分，剩餘開立關聯工單 `linked_work_order_id`）」+ 副說明「原工單佣金按完成比例計算」
    - option_cancel: Radio + Label / 「客戶選擇取消（豁免車馬費）」+ 副說明「對齊派工營運 §3，本次不收費」
- **states**:
  - default: 無預選
  - selected: 選中項左側 16px 藍色圓點 + 背景 #DBEAFE
- **copy_constraints**: 每選項 label 最多 50 字

### Section: material_submit_area（T6）

- **layout**: 固定底部 sticky，background 白，padding 16px + safe-area-inset-bottom
- **elements**:
  - submit_btn: Button CTA / required / 「提交缺料回報」，full-width 高度 56px 背景 #F59E0B 字體 18px Bold
- **states**:
  - disabled: 缺件 < 1 OR 決策未選 → 灰色 + 缺少項目提示
  - submitting: Spinner
  - submitted: 工單狀態轉 `material_pending`，返回詳情頁 + Toast「已通知管理員調貨，LINE 已推送客戶」
  - partial_submitted: 額外 Dialog 顯示新建的 `linked_work_order_id`，含「查看關聯工單」按鈕

---

### Section: delay_reason_selector（T7）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「延遲事由」，16px SemiBold
  - reason_grid: Grid 2-column / required / gap 12px，每選項為 Card 按鈕：
    - option_traffic: Card Button / 圖示 Car + 「塞車」，高度 80px，圓角 12px，邊框 2px #E2E8F0
    - option_prev_overrun: Card Button / 圖示 Clock + 「前案超時」
    - option_equipment: Card Button / 圖示 Tool + 「設備問題」
    - option_other: Card Button / 圖示 MoreHorizontal + 「其他」
  - other_reason_input: TextArea / conditional（選 option_other 時展開）/ placeholder「請說明...」，min 80px max 150 字
- **states**:
  - default: 無預選，邊框 #E2E8F0
  - selected: 選中項邊框 #2563EB 2px + 背景 #DBEAFE + 圖示變藍
  - other_selected: 展開文字輸入區

### Section: new_eta_picker（T7）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px
- **elements**:
  - section_title: H3 / required / 「新預計時間」，16px SemiBold
  - current_eta_display: Caption / required / 「原預計：YYYY-MM-DD HH:mm」色 #64748B
  - datetime_picker: DateTimePicker / required / 原生 `<input type="datetime-local">`，高度 48px 字體 16px，min = now() + 10min
  - quick_offset_chips: ChipGroup / required / 快選按鈕 gap 8px：「+15 分」「+30 分」「+1 小時」「+2 小時」，每顆 min 48×44px
- **states**:
  - default: 預設 now() + 30min
  - picking: 開啟原生 picker
- **copy_constraints**: 僅允許晚於現在時間，超過 8 小時需額外事由說明

### Section: delay_severity_preview（T7）

- **layout**: 單欄 padding 16px，margin 16px 16px 0，圓角 12px，背景依嚴重度變色
- **elements**:
  - severity_badge: Badge / required /
    - 輕微（≤ 15 分）：背景 #D1FAE5 字體 #065F46 「輕微延遲」
    - 中度（15–30 分）：背景 #FEF3C7 字體 #92400E 「中度延遲（客戶會收到 LINE 通知）」
    - 嚴重（> 30 分）：背景 #FEE2E2 字體 #B91C1C 「嚴重延遲（客戶將收到改期/取消選項）」
    - 超長（> 2h）：背景 #FEE2E2 字體 #991B1B + 圖示 AlertTriangle 「超長延遲 — 將同步通知管理員介入，影響技師 KPI」
  - sla_impact_text: Body SM / required / 「SLA 時鐘將重置為新 ETA」色 #475569 14px
  - kpi_warning_text: Body SM / conditional（嚴重/超長）/ 「本次延遲將計入 KPI（影響月結獎懲）」色 #B91C1C 14px
- **states**:
  - default: 跟隨 new_eta_picker 即時計算嚴重度

### Section: delay_submit_area（T7）

- **layout**: 固定底部 sticky
- **elements**:
  - submit_btn: Button CTA / required / 「送出延遲通知」，full-width 高度 56px，依嚴重度變色（輕微 #2563EB / 中度 #F59E0B / 嚴重 #DC2626）
- **states**:
  - disabled: 事由未選 OR ETA 未改 → 灰色
  - submitting: Spinner + 「提交中...」
  - submitted: Toast「已推送 LINE 給客戶」+ 返回詳情頁，工單狀態轉 `delayed`
  - submitted_escalated: 額外 Toast「已同步通知管理員」（> 2h 情境）

---

### Section: door_check_stepper（T8）

- **layout**: 全寬 sticky 於 offline_queue_indicator 下方，背景白色高度 64px，下方 1px border
- **elements**:
  - step_indicator: Stepper / required / 三步驟水平排列：
    - step_1: 「抵達拍」（Circle 24px 編號 1）
    - step_2: 「客戶同意」
    - step_3: 「完工拍」
    - 當前步驟背景 #2563EB 白字，已完成 #10B981 勾號，未開始 #E2E8F0
  - progress_line: Line / required / 連接三個 Circle，已完成段 #10B981
- **states**:
  - step_1_active: 僅 step_1 為藍
  - step_2_active: step_1 完成，step_2 為藍
  - step_3_active: step_1/2 完成，step_3 為藍

### Section: arrival_photo_group（T8）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「1. 抵達時拍攝原始狀態（最少 4 張）」，16px SemiBold
  - required_shots_checklist: CheckList / required / 必拍清單，每項 Checkbox + 文字：
    - 「門扇全貌（含門框）」
    - 「側板特寫」
    - 「將切割/加工區域標記」
    - 「現有鎖孔/孔位」
  - photo_grid: Grid 2-column / required / gap 8px，每張縮圖 ratio 1:1 圓角 8px
  - add_photo_btn: DashedCard / required / 拍照入口同 T5
  - photo_count_text: Caption / required / 「{N}/4 張」未達 4 張紅色
  - exif_toggle: Toggle / required / 「保留照片 GPS 與時間戳（建議開啟）」預設 ON，14px
- **states**:
  - default: 空 grid + 4 項 checklist 未勾
  - filled: 對應 checklist 項目勾選（建議技師逐項拍）
- **copy_constraints**: 照片檔名 + hash 於上傳時一併記錄（SHA-256）

### Section: appearance_notice_sheet（T8）

- **layout**: 全螢幕 overlay（從底部滑入），背景白色，padding 24px 16px，可捲動
- **elements**:
  - notice_title: H2 / required / 「門外觀變更告知書」20px SemiBold
  - auto_generated_content: Prose Block / required / 系統依工單與照片自動生成內容：
    - 工單編號、客戶姓名、日期時間
    - 「變更原因：{technician_input}」
    - 「影響區域：{area_from_photo_tags}」
    - 「可能風險：油漆起泡、變色、不可逆加工（依 Flow 10 BR-003）」
    - 「公司不承擔外觀損害責任」免責聲明（粗體紅色）
  - original_photos_mini_grid: MiniGrid 4-column / required / 抵達照縮圖嵌入書面
  - customer_read_checkbox: Checkbox / required / 「客戶已閱讀並了解以上內容」，touch area 44×44px，未勾則下一步 disabled
  - customer_decision_buttons: ButtonGroup / required /
    - agree_btn: Button Primary / 「客戶同意 → 前往簽章」，full-width 高度 56px 背景 #2563EB
    - refuse_btn: Button Outline / 「客戶拒絕 → 提供替代方案」，高度 48px，邊框 #DC2626 字體 #DC2626
- **states**:
  - default: 展開告知書，checkbox 未勾
  - read: checkbox 勾選後 agree_btn 啟用
  - agree_clicked: 跳轉至 T9 簽章頁，帶 `document_type=APPEARANCE_CHANGE`
  - refuse_clicked: 開啟替代方案 Dialog（換鎖款 / 轉接片 / 取消安裝）→ 對應 Flow 10
- **copy_constraints**: 自動生成內容段落 ≤ 500 字

### Section: completion_photo_group（T8）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px
- **elements**:
  - section_title: H3 / required / 「3. 完工後對比照（最少 2 張）」
  - overlay_compare_helper: ComparisonCard / required / 並列縮圖（抵達 vs 完工），滑動分隔條可左右對比，高度 240px
  - photo_grid: Grid 2-column / required / 新拍完工照
  - add_photo_btn: DashedCard / required
  - diff_hint: Caption / optional / AI 自動識別差異區域（若 vision 服務啟用）+ 標記紅框
- **states**:
  - empty: 僅顯示抵達照
  - partial: 單張完工照，overlay 啟動
  - complete: ≥ 2 張完工照

### Section: customer_field_confirm（T8）

- **layout**: 固定底部 sticky，背景白色 padding 16px + safe-area
- **elements**:
  - like_btn: Button CTA / required / 圖示 ThumbsUp + 「客戶確認無損壞」，高度 56px 背景 #10B981 字體 18px Bold 白色，寬度 65%
  - refuse_btn: Button Outline / required / 「客戶有異議」，邊框 #DC2626 字體 #DC2626，寬度 35%
  - note_input: Input / optional（展開時）/ placeholder「客戶備註（選填）」，高度 48px
- **states**:
  - default: 兩顆按鈕並列
  - like_clicked: 跳轉 T9 簽章（document_type=WORK_ORDER_COMPLETION）
  - refuse_clicked: 自動建立爭議案件 → POST `/api/v1/disputes` → 導向 `/admin/disputes/{id}`（實際由後台處理，技師端顯示「已通知管理員」）

---

### Section: signature_intro_card（T9）

- **layout**: 單欄 padding 16px，背景 #F0FDF4（綠）或 #FEF3C7（橘，依文件類型），margin 16px，圓角 12px
- **elements**:
  - doc_type_badge: Badge / required / 依 `document_type` 顯示：
    - WORK_ORDER_COMPLETION：綠底「工單完工確認」
    - APPEARANCE_CHANGE：橘底「外觀變更同意」
    - SCOPE_CHANGE：紫底「範圍變更核准」
  - legal_level_text: Body SM / required / 依租戶設定顯示法律等級：
    - `typed`：「鍵入姓名確認（具初步證據效力）」
    - `drawn`：「手寫簽名（符合電子簽章法第 4 條）」
    - `certificate`：「憑證簽章（具最高法律效力）」
  - required_parties_text: Body MD Bold / required / 「本文件需 技師 + 客戶 雙方簽章」
- **states**:
  - default: 顯示文件類型與法律等級

### Section: technician_signature_pad（T9）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px，shadow-sm
- **elements**:
  - section_title: H3 / required / 「技師簽章」+ 右側 Badge「您」16px SemiBold
  - technician_name_display: Body MD / required / 顯示技師姓名（自動帶入登入使用者）
  - canvas: Canvas / required / 高度 180px full-width，border 2px dashed #CBD5E1，圓角 12px，`touch-action: none`（防止頁面滾動）
    - 繪製中：border 轉 solid #2563EB，筆觸 2px 色 #1E293B
  - clear_btn: Button Ghost / required / 「清除重簽」min touch 44×44px
  - signature_status_text: Caption / required / 未簽：紅色「尚未簽名」/ 已簽：綠色「✓ 已取得技師簽章」
- **states**:
  - empty: 空白畫布
  - drawing: 繪製中
  - signed: 儲存 Base64 + `integrity_hash` 前端預計算

### Section: customer_signature_pad（T9）

- **layout**: 單欄 padding 16px，背景白色，margin 16px 16px 0，圓角 12px，shadow-sm，與技師簽章區視覺區隔（左邊框 4px #F59E0B 提示這是客戶區）
- **elements**:
  - section_title: H3 / required / 「客戶簽章」+ 右側 Badge「請客戶簽」背景 #FEF3C7
  - customer_name_confirm: Checkbox + Input / required / 「已口頭向客戶確認姓名：」+ Input（從工單帶入客戶姓名，可修正），高度 48px
  - canvas: Canvas / required / 同技師 canvas 規格
  - clear_btn: Button Ghost / required / 「清除重簽」
  - hand_device_hint: Caption / required / 「請將手機橫交給客戶，方便簽名」色 #64748B 13px
  - signature_status_text: Caption / required / 同技師
- **states**:
  - empty: 空白
  - drawing: 繪製中，全螢幕禁止其他手勢（避免技師誤觸）
  - signed: 完成
- **copy_constraints**: 客戶姓名最多 20 字

### Section: signature_metadata_preview（T9）

- **layout**: 單欄 padding 16px，背景 #F8FAFC，margin 16px，圓角 12px，字體偏小（稽核資訊）
- **elements**:
  - section_title: Caption / required / 「以下資料將寫入稽核紀錄（不可修改）」12px 色 #64748B
  - meta_grid: InfoGrid 2-column / required /
    - timestamp_row: InfoRow / 「時間戳」+ 即時時間（ISO 8601 + 時區）
    - gps_row: InfoRow / 「GPS 座標」+ 經緯度（或「已關閉」），右側 Toggle 允許技師與客戶協商關閉
    - ip_row: InfoRow / 「IP 位址」+ 自動取得
    - device_row: InfoRow / 「裝置指紋」+ User-Agent 摘要
    - doc_id_row: InfoRow / 「文件 ID」+ UUID 簡碼
    - hash_row: InfoRow / 「完整性雜湊」+ SHA-256 前 12 碼... （對齊 `e-signature-spec.md` §5.1）
- **states**:
  - default: 即時顯示
  - gps_denied: GPS 座標顯示「權限未開啟」紅字
  - offline: 提示「IP 將於上線同步時記錄」

### Section: signature_submit_area（T9）

- **layout**: 固定底部 sticky，背景白色，padding 16px + safe-area
- **elements**:
  - submit_btn: Button CTA / required / 「完成雙方簽章」，full-width 高度 56px 背景 #F59E0B 字體 18px Bold
  - post_submit_hint: Caption / optional / 「完成後自動生成 PDF 並透過 LINE 寄送客戶」色 #64748B 12px
- **states**:
  - disabled: 任一方未簽 OR 客戶姓名未確認 → 灰色 + 底部紅字提示
  - submitting: Spinner + 「生成 PDF 中...」
  - pdf_generated: 全屏成功動畫（綠勾 + 「簽章完成，PDF 已寄出」），2.5 秒後返回詳情頁或 completion_report
  - line_send_failed: Toast「LINE 推送失敗，已存檔於工單附件」，允許重試
  - offline_queued: 按鈕改「離線簽章（上線後送出）」，本地 IndexedDB 保存含 Idempotency-Key

---

### Section: schedule_month_header（T10）

- **layout**: sticky 於 sub_page_header 下方，全寬，高度 72px，背景白色，下方 1px border，padding 12px 16px
- **elements**:
  - month_switcher: Flex Row / required /
    - prev_btn: IconButton / required / ChevronLeft 44×44px，點擊切前一月
    - current_month_text: H3 / required / 「YYYY 年 M 月」，18px SemiBold 居中
    - next_btn: IconButton / required / ChevronRight 44×44px（未來 3 個月內可切）
  - quota_row: Flex Row / required / gap 12px，三個 Chip：
    - leave_quota: Chip / 「本月休假 {used}/{total} 天」，已用完時紅底
    - standby_quota: Chip / 「備勤 {N} 小時」
    - workload_chip: Chip / 「本月工單 {N} 件」
- **states**:
  - default: 當月
  - future_limited: 未來月份僅顯示已排定的班與休假，`next_btn` 超過 3 個月禁用

### Section: schedule_calendar_view（T10）

- **layout**: 全寬月曆格線（7 欄 × N 列），padding 8px 16px，格子正方形 `aspect-square`
- **elements**:
  - weekday_header: GridRow 7-col / required / 日–六 Caption 12px 色 #64748B
  - day_cell: Cell / repeated /
    - date_number: Body SM / required / 日期，14px，當日粗體 + 藍底圓圈
    - workorder_count: Badge / conditional / 右下角紅色圓點 + 工單數字
    - leave_marker: Stripe / conditional / 對角線條紋 + 「休」字，色 #F59E0B
    - standby_marker: Icon / conditional / 右上角 Moon 圖示，色 #8B5CF6
    - off_today_marker: Ribbon / conditional / 「已關閉接單」灰色條
  - tap_interaction: OnTap / required / 點擊日期彈出 BottomSheet 顯示該日詳情（工單列表 + 時段）
- **states**:
  - default: 月曆顯示
  - today_highlight: 今日藍底白字
  - past_date: 過去日期 opacity 0.5 僅唯讀
  - day_detail_open: BottomSheet 彈出

### Section: leave_request_form（T10）

- **layout**: BottomSheet 全螢幕 90%，圓角上方 16px，padding 16px
- **elements**:
  - sheet_title: H2 / required / 「申請休假」18px SemiBold
  - date_range_picker: DateRangePicker / required / 起始日 + 結束日 各高 48px，max 7 天（超過需主管另批）
  - reason_select: Select / required / 選項：「個人事假」「病假」「婚喪假」「其他」，高度 48px
  - reason_note: TextArea / conditional（選其他時必填）/ min 80px
  - conflict_warning: AlertCard / conditional / 若日期已有工單：背景 #FEE2E2「該日期已有 {N} 件工單，將通知管理員重新派工」
  - submit_leave_btn: Button Primary / required / 「送出申請（需主管審核）」，full-width 高度 48px
- **states**:
  - default: 空表單
  - has_conflict: 顯示警告 + submit 按鈕變橘色
  - submitting: Spinner
  - submitted: Toast「已送審，預計 24 小時內回覆」+ 關閉 sheet

### Section: standby_request_form（T10）

- **layout**: BottomSheet 同 leave_request_form
- **elements**:
  - sheet_title: H2 / required / 「申請備勤加班」
  - date_picker: DatePicker / required
  - time_range: TimeRange / required / 起訖時間，各 48px
  - note_textarea: TextArea / optional
  - submit_standby_btn: Button Primary / required / 「送出申請」
- **states**:
  - 同 leave_request_form

### Section: close_today_accept_switch（T10）

- **layout**: 單欄 padding 16px，背景白色，margin 16px，圓角 12px
- **elements**:
  - section_title: H3 / required / 「關閉本日接單」16px SemiBold
  - toggle_switch: Switch / required / 44×28px，ON/OFF
  - toggle_hint: Body SM / required /
    - OFF：「目前接收新工單」色 #10B981
    - ON + 1h 內無工單：「已關閉接單（立即生效）」色 #F59E0B
    - ON + 有工單：「完成當前 {N} 件工單後生效」色 #F59E0B
  - emergency_override_btn: Button Outline / conditional / 「緊急取消本日（需註明原因）」，僅緊急情境顯示
- **states**:
  - off: 預設開放接單
  - on_immediate: 立即生效
  - on_pending: 等待工單完成

### Section: pending_requests_list（T10）

- **layout**: 單欄 padding 0 16px 16px，背景 #F8FAFC
- **elements**:
  - section_title: H3 / required / 「待審核申請」16px SemiBold padding 16px 0
  - request_card: Card / repeated / padding 12px 背景白色 圓角 8px margin-bottom 8px
    - type_badge: Badge / 休假（橘）/ 備勤（紫）
    - date_range: Body MD / 日期區間
    - status_text: Caption / 「待審核 | 送出於 X 小時前」
    - cancel_btn: Button Ghost / required / 「撤回申請」min touch 44×44px，點擊確認 Dialog
  - empty_state: EmptyBlock / 「沒有待審核申請」
- **states**:
  - default: 列表
  - empty: 顯示 empty_state
  - cancelling: cancel_btn Spinner

---

### Section: bottom_navigation（T10 顯示，T5–T9 隱藏）

- **layout**: 固定底部，高度 56px + safe-area，全寬 max-width 480px，背景白色，上方 1px border，z-index 30
- **elements**:
  - tab_pool: NavTab / required / 圖示 Map + 「案件池」
  - tab_my_orders: NavTab / required / 圖示 ClipboardList + 「我的工單」
  - tab_account: NavTab / required / 圖示 Wallet + 「帳戶」，T10 active 色 #2563EB
- **states**:
  - hidden_on_subflow: T5–T9 子路由時 BottomNav 隱藏（全螢幕沉浸式表單，避免誤觸）
  - visible_on_schedule: T10 顯示，「帳戶」active

---

## [INTERACTION & STATE FLOW]

### 主要互動流程

#### T5 範圍變更

1. 從 `/my-orders/[id]` action_section 點「回報異常 → 範圍變更」→ push `/my-orders/[id]/scope-change`
2. GET `/api/v1/work-orders/[id]` 填入原報價 context
3. 技師填寫事由、至少 2 張現場照片、新增追加工項
4. 系統即時計算新總價 → 若 > 原價 2× 顯示主管審核警示
5. 點「送出範圍變更申請」→ POST `/api/v1/work-orders/{id}/scope-change`（帶 `Idempotency-Key`）
6. 工單狀態轉 `scope_changed`、LINE Flex 推送客戶（原價 vs 新價 + 照片 + 核准/拒絕按鈕）
7. WebSocket `/realtime/work-orders/{id}` 訂閱客戶回應：
   - `customer_approved` → 工單回 `in_progress` + Toast + 返回詳情頁
   - `customer_rejected` → Dialog 三選項（僅完成原範圍 / 取消 / 協商）
   - 24h 無回應 → 管理員介入，技師頁面顯示「已升級管理員」

#### T6 缺料回報

1. 從 action_section「回報異常 → 缺料」push `/my-orders/[id]/material-request`
2. 搜尋零件主檔選缺件 → 即時查詢庫存 ETA（GET `/api/v1/inventory/parts/{id}/eta`）
3. 選擇是否替代、現場決策（完全等待 / 部分完工 / 取消）
4. POST `/api/v1/work-orders/{id}/material-request`
5. 若選「部分完工」→ 後端建立 `linked_work_order_id` 新工單，前端 Dialog 顯示新工單編號
6. 若選「取消」→ 豁免車馬費，狀態轉 `cancelled`
7. 管理員收到 Web Alert、客戶收到 LINE 推送（含 ETA 與選擇按鈕）

#### T7 延遲通知

1. 從 action_section「回報異常 → 延遲」push `/my-orders/[id]/delay`
2. 選延遲事由、datetime-picker 或快選 chip 設定新 ETA
3. `delay_severity_preview` 即時計算嚴重度（輕微/中度/嚴重/超長）
4. 點「送出」→ POST `/api/v1/work-orders/{id}/delay`
5. 後端：
   - SLA 時鐘重置為新 ETA（對齊 `specs/sla-availability-spec.md`）
   - 依嚴重度推送 LINE 客戶（中度：僅告知；嚴重：含改期/取消按鈕）
   - > 2h 額外通知管理員、寫入技師 KPI 延遲紀錄
6. 工單狀態轉 `delayed`，返回詳情頁

#### T8 門面外觀檢核

1. 從 action_section「門面檢核」push `/my-orders/[id]/door-check`
2. Step 1：拍原始狀態（≥ 4 張，勾選必拍 checklist）→ 照片帶 EXIF + SHA-256 hash
3. Step 2：彈出自動生成的「門外觀變更告知書」→ 客戶閱讀打勾 → 點「同意」或「拒絕」
4. 同意 → 跳轉 T9 簽章頁（`document_type=APPEARANCE_CHANGE`）
5. 拒絕 → 替代方案 Dialog（換鎖款 / 轉接片 / 取消）→ 對應 Flow 10 分支
6. 施工完成後返回此頁 Step 3：拍完工對比照（≥ 2 張）
7. 客戶現場按「確認無損壞」或「有異議」
8. POST `/api/v1/work-orders/{id}/door-check` 寫入 `appearance_change_notices` 表

#### T9 雙方電子簽章

1. 從 T8 同意後、完工報告提交前、或退款確認時進入 `/my-orders/[id]/signature`
2. GET 文件類型 + 租戶法律等級（`typed` / `drawn` / `certificate`）
3. 技師先簽（上半區 canvas），`touch-action: none` 防頁面滾動
4. 客戶姓名 checkbox 確認 + 客戶在下半區 canvas 簽
5. `signature_metadata_preview` 即時顯示將寫入的元資料（時間戳、GPS、IP、裝置指紋、SHA-256）
6. 點「完成雙方簽章」→ POST `/api/v1/work-orders/{id}/signature`（含 Idempotency-Key + 兩筆 signature_data）
7. 後端：寫 `digital_signatures` × 2 + 生成 PDF + LINE 推送客戶 + 寫 `audit-events`（entity=signature, type=CREATE）
8. 成功動畫 → 返回詳情頁或繼續 completion_report

#### T10 我的排班

1. 底部 Tab「帳戶」→「我的排班」進入 `/account/schedule`
2. GET `/api/v1/technicians/me/schedule?month=YYYY-MM`
3. 月曆顯示每日工單、休假、備勤標記
4. 點「申請休假」→ BottomSheet 填表 → POST `/api/v1/technicians/me/schedule/leave-request`
5. 點「申請備勤加班」→ 同上 POST
6. Toggle「關閉本日接單」→ PATCH `/api/v1/technicians/me/availability`：
   - 1h 內無工單：立即生效（派工引擎即時收到，透過 WebSocket 廣播）
   - 有工單：標記為「完成後關閉」，系統 watch 最後工單 status
7. 待審核申請列表可撤回（DELETE request_id）

### RWD 行為差異

| 斷點 | 佈局 | 差異說明 |
|------|------|---------|
| Mobile (< 480px) | 單欄全寬（主要設計） | 標準體驗，T5–T9 全螢幕沉浸式表單，無 BottomNav |
| Tablet (481–768px) | 單欄 max-width 480px 居中 | 左右留白，BottomSheet 不延伸 |
| Desktop (≥ 769px) | 不支援（技師端為純 Mobile PWA） | 顯示「請使用手機操作」提示頁 + QR Code 可掃描在手機開啟 |

### 資料更新策略

- **T5–T9 提交**：離線時進入 IndexedDB 佇列，每個動作帶 `Idempotency-Key`（客戶端生成 UUID），恢復連線後 Service Worker Background Sync 依序 replay
- **T5 客戶回應**：透過 WebSocket `wss://.../realtime/work-orders/{id}` 即時推送（`scope_change_approved` / `scope_change_rejected`）+ 60 秒 Polling fallback
- **T6 庫存 ETA**：選擇零件時即時 GET `/api/v1/inventory/parts/{id}/eta`，離線使用最近快取（標示「可能過時」）
- **T7 延遲**：SLA 計算前端 + 後端雙重，前端僅為 preview，實際以後端為準
- **T8 EXIF + GPS**：照片在前端使用 `EXIF.js` 讀取後端存入 `digital_signatures.signature_data` 附件
- **T9 PDF 生成**：後端 async 任務，WebSocket 推送完成事件；若 30 秒未完成前端顯示「PDF 生成中，稍後可於工單附件查看」
- **T10 排班變更**：提交後 WebSocket 廣播 `schedule_updated` → 派工引擎即時收到，管理員端 A25 同步刷新

---

## [DATA & API]

- **uses_api**: true
- **endpoints**:
  - **T5 範圍變更**
    - GET `/api/v1/work-orders/{id}` — 取得原工單含原報價與工項
    - POST `/api/v1/work-orders/{id}/scope-change` — 提交範圍變更。Header 需 `Idempotency-Key: <uuid>`、`X-Tenant-ID`。Body: `{ reason, photos[], new_items[{name, unit_price, qty}], new_total, needs_supervisor_review }`。Response 200：`{ scope_change_id, status: "pending_customer" | "pending_supervisor" }`
    - POST `/api/v1/work-orders/{id}/photos` — 照片上傳（multipart）
  - **T6 缺料**
    - GET `/api/v1/inventory/parts?q=` — 零件主檔搜尋
    - GET `/api/v1/inventory/parts/{id}/eta` — 即時庫存 ETA
    - POST `/api/v1/work-orders/{id}/material-request` — 提交缺料。Header `Idempotency-Key`。Body: `{ missing_parts[{part_id, qty}], has_alternative, alternative_part_id?, price_diff?, decision: "wait" | "partial" | "cancel" }`。Response：若 `decision=partial` 回傳 `{ linked_work_order_id }`
  - **T7 延遲**
    - POST `/api/v1/work-orders/{id}/delay` — 提交延遲。Header `Idempotency-Key`。Body: `{ reason: "traffic" | "prev_overrun" | "equipment" | "other", reason_note?, new_eta: ISO8601 }`。Response：`{ severity: "minor" | "moderate" | "severe" | "extreme", escalated_to_admin: boolean }`
  - **T8 門面檢核**
    - POST `/api/v1/work-orders/{id}/door-check` — Header `Idempotency-Key`。Body: `{ arrival_photos[{url, sha256, exif_gps?}], appearance_notice: {change_reason, affected_area, risk_description}, customer_agreed: boolean, completion_photos[], customer_field_decision: "approved" | "disputed", customer_note? }`
  - **T9 雙方簽章**
    - POST `/api/v1/work-orders/{id}/signature` — Header `Idempotency-Key`。Body: `{ document_type: "WORK_ORDER_COMPLETION" | "APPEARANCE_CHANGE" | "SCOPE_CHANGE", technician_signature: {image_base64, canvas_width, canvas_height}, customer_signature: {...}, customer_name_confirmed, gps?, device_fingerprint }`。Response：`{ signature_ids: [...], pdf_url, audit_event_id }`
  - **T10 排班**
    - GET `/api/v1/technicians/me/schedule?month=YYYY-MM` — 取得月班表（工單、休假、備勤）
    - POST `/api/v1/technicians/me/schedule/leave-request` — Body: `{ start_date, end_date, reason, note? }`
    - POST `/api/v1/technicians/me/schedule/standby-request` — Body: `{ date, start_time, end_time, note? }`
    - PATCH `/api/v1/technicians/me/availability` — Body: `{ close_today: boolean, reason? }`
    - DELETE `/api/v1/technicians/me/schedule/requests/{request_id}` — 撤回申請
  - **WebSocket**
    - `wss://.../realtime/work-orders/{id}` — T5 客戶回應（`scope_change_approved`/`rejected`）、T9 PDF 完成（`signature_pdf_ready`）
    - `wss://.../realtime/technicians/me/schedule` — T10 管理員審核結果推送（`leave_request_approved`/`rejected`）

- **error_cases**:
  - 網路錯誤：
    - T5–T9 寫入：存入 IndexedDB 佇列 + offline_queue_indicator 顯示待同步數量，Service Worker Background Sync 依 Idempotency-Key replay
    - T6 庫存 ETA：使用最近快取，標示「可能過時」
    - 照片上傳：加入 Background Sync 佇列，縮圖右下角顯示 ⏱ 圖示
  - API 錯誤（5xx）：Toast「伺服器忙碌中」+ 自動重試（exponential backoff，最多 3 次），失敗則存佇列
  - 冪等衝突（409 + 已存在 Idempotency-Key）：視為成功，顯示原結果
  - 權限不足（401/403）：導向登入頁 `/login`
  - 狀態衝突（409 狀態錯誤）：Toast「工單狀態已變更」+ GET 最新工單 + 自動返回詳情頁
  - T5 客戶拒絕：Dialog 三選項，不視為錯誤
  - T7 ETA 過早（< now）：前端攔截，紅字提示
  - T8 照片不足 4 張：提交按鈕 disabled
  - T9 簽名 canvas 為空：disabled + 紅字「請完成雙方簽章」
  - T9 PDF 生成失敗：Toast + 允許重試 POST，簽章資料已保存
  - T10 休假衝突工單：警示但允許提交，後端審核時管理員決定是否重派
  - GPS 拒絕：T8/T9 允許關閉但記錄「GPS denied」於稽核

---

## [EXCEPTION TO GLOBAL RULES]

- **T5–T9 全螢幕沉浸式表單**：此 5 個子路由覆蓋 BottomNav（z-index 比 BottomNav 高），避免技師在現場誤觸導航離開未儲存表單。T10 則正常顯示 BottomNav（屬常態自助頁）。
- **T8 / T9 `touch-action: none`**：Canvas 區域攔截所有觸控事件，防止簽名或標記時頁面跟著滾動。需在 Canvas wrapper 設定 `overscroll-behavior: contain`。
- **T5–T9 寫入操作強制 `Idempotency-Key` header**：對齊 `E5x--frontend-architecture.md` §8.1 與 §8.7，離線佇列 replay 時必需，後端以此去重。
- **T8 EXIF 與照片 hash**：照片上傳前前端計算 SHA-256（`crypto.subtle.digest`），EXIF GPS 依 `exif_toggle` 決定是否保留（預設 ON）。對齊 Flow 10 §13.6 證據保存規範。
- **T9 簽章雙 canvas 不可互相覆蓋**：上下區嚴格隔離，同時僅一個 canvas 可繪製（另一個 disabled），避免技師手誤在客戶區簽。
- **T9 PDF 生成 async**：點提交後前端不等待 PDF 完成，立即返回成功頁，PDF 由後端背景任務 + WebSocket 推送。
- **T9 離線雙簽特例**：離線時允許完成雙 canvas，所有元資料（時間、GPS、指紋）於本地記錄，IP 於上線時後端補填，PDF 生成也延後。提交按鈕改為「離線簽章（上線後送出）」背景 #6B7280。
- **T10 月曆格子 `aspect-square`**：強制正方形以保持美觀，格內 Badge 超出時 ellipsis。
- **T5/T6/T7 照片或檔案上傳可跨路由恢復**：若技師意外切離子路由，IndexedDB 保留表單草稿 30 分鐘，回到同一工單子路由時自動恢復（含已拍照片縮圖）。
- **T8 疊圖比對 helper**：使用 Canvas compositing（`globalCompositeOperation: "difference"`）在前端生成差異影像，不依賴後端 Vision 服務（若 vision 服務可用則優先使用）。

---

## [ACCEPTANCE CRITERIA]

### 共用
- [ ] 所有按鈕高度 ≥ 48px、主要 CTA ≥ 56px、字級 ≥ 18px
- [ ] 所有可點擊元素 touch target ≥ 44 × 44px
- [ ] 所有寫入 API 請求帶 `Idempotency-Key` 與 `X-Tenant-ID` header
- [ ] 離線模式：offline_queue_indicator 正確顯示待同步數量
- [ ] 離線操作存入 IndexedDB，恢復連線後 Service Worker Background Sync 依序 replay
- [ ] sub_page_header 返回鈕在提交中 disabled，防止中斷
- [ ] 所有子路由支援 PWA 加到主畫面後直接開啟
- [ ] Loading / Error / Empty 三態完備

### T5 範圍變更
- [ ] 原報價 context 正確載入並顯示
- [ ] 工項動態新增/刪除，小計與新總價即時計算
- [ ] 新報價 > 原報價 2× 顯示主管審核警示
- [ ] 照片 < 2 張、事由空、工項 0 時提交按鈕 disabled
- [ ] 提交後工單狀態轉 `scope_changed`
- [ ] WebSocket 客戶回應即時更新頁面狀態
- [ ] 24 小時未回應時 UI 顯示「已升級管理員」

### T6 缺料回報
- [ ] 零件主檔搜尋 2 字以上觸發 GET，顯示即時 ETA
- [ ] 三種庫存狀態 Badge（現貨 / 需調貨 / 缺貨）正確顯示
- [ ] 替代方案 toggle 正確展開/收合
- [ ] 現場決策三選項單選
- [ ] 選「部分完工」後 Dialog 顯示 `linked_work_order_id`
- [ ] 選「取消」豁免車馬費，Toast 確認

### T7 延遲通知
- [ ] 事由 4 選 1，選其他需補說明
- [ ] datetime-picker + 快選 chip 正確設定新 ETA
- [ ] 嚴重度預覽即時跟隨 ETA 變化
- [ ] 超長延遲（> 2h）按鈕變紅 + 提示升級管理員
- [ ] 提交後工單狀態轉 `delayed`，LINE 推送客戶
- [ ] SLA 時鐘後端重置為新 ETA（驗證後台 API 回傳）

### T8 門面外觀檢核
- [ ] Stepper 三步驟正確切換
- [ ] 抵達拍 ≥ 4 張 + 4 項 checklist 勾完才能進下一步
- [ ] 告知書自動生成，含變更原因、風險、免責聲明
- [ ] 客戶 checkbox 勾選後「同意」按鈕啟用
- [ ] 拒絕進入替代方案 Dialog（換鎖款 / 轉接片 / 取消）
- [ ] 完工 ≥ 2 張對比照，overlay 比對可用
- [ ] 照片 EXIF + SHA-256 hash 一併記錄
- [ ] 客戶按讚/拒絕分別導向 T9 簽章或爭議建立

### T9 雙方電子簽章
- [ ] 文件類型 Badge 正確（WORK_ORDER_COMPLETION / APPEARANCE_CHANGE / SCOPE_CHANGE）
- [ ] 法律等級文案依租戶設定顯示（typed / drawn / certificate）
- [ ] 技師 + 客戶雙 canvas 獨立繪製不互相影響
- [ ] `touch-action: none` 防止簽名時頁面滾動
- [ ] 客戶姓名 checkbox 確認後才可提交
- [ ] signature_metadata_preview 即時顯示時間戳、GPS、IP、裝置指紋、SHA-256
- [ ] GPS 可選擇關閉（記錄於稽核）
- [ ] 提交後生成 PDF，LINE 推送客戶（含原始簽章影像 + 稽核元資料）
- [ ] `audit-events` 寫入（entity=signature, type=CREATE）
- [ ] 離線雙簽存 IndexedDB，上線後 replay + 後端補 IP

### T10 我的排班
- [ ] 月曆顯示每日工單數、休假、備勤、關閉接單標記
- [ ] 切換月份（前後 3 個月內）
- [ ] 休假額度 / 備勤時數即時顯示
- [ ] 申請休假：日期衝突時顯示警示
- [ ] 申請備勤：時段正確驗證
- [ ] 「關閉本日接單」toggle：
  - 1h 內無工單立即生效
  - 有工單改為「完成後關閉」
- [ ] 待審核列表可撤回申請
- [ ] 申請送出後 WebSocket 即時收到審核結果推送
- [ ] 與派工引擎同步（管理員端 A25 即時刷新）

### 視覺 / 設計系統
- [ ] Primary #2563EB 用於主要操作
- [ ] Accent #F59E0B 用於 CTA（提交、完成作業）
- [ ] Secondary #1E293B 用於主要文字
- [ ] BG #F8FAFC 用於頁面背景
- [ ] Font Inter（數字/英文）+ Noto Sans TC（中文）
- [ ] 最小支援寬度 375px
- [ ] Mobile-First 單欄堆疊，底部固定 CTA
- [ ] 所有狀態（default / disabled / loading / error / submitted / offline）視覺明確

---

## T1.4 補強：客戶 LINE Flex RSVP 端（Flow 11 閉環）

> 補 Flow 11 客戶不在場 / Flow 5 延遲改期時「客戶側確認新時段」UI 缺口。雖非 Web 頁，但屬完整互動流程必要組件。

### [FLEX MESSAGE SPEC] reschedule_rsvp

觸發：技師經 T11 改期日曆送出 1-3 個備選時段後，後端 push LINE Flex 給客戶。

**Hero**：工單地址 map thumbnail + 技師姓名/照片

**Body**：
- title「很抱歉需要調整服務時間」
- work_order_line「工單 #WO-042」
- reason_line 技師自填訊息（120 字上限，後端 escape XSS）
- slot_count_hint「請從以下 N 個時段選擇您方便的」

**Slot 按鈕區（1-3 個）**：
- 每鈕顯示 `2026-04-25（四）14:00-16:00`
- `postback` action with `data=rsvp&wo_id=xxx&slot_index=N`
- 點過後其他鈕 disabled + 該鈕標「已選擇」

**Footer**：
- reject_btn「都不方便，請客服聯繫」→ postback rsvp_reject
- expires_at「請於 2026-04-24 23:59 前回覆」（24h TTL）

### 後端處理（對齊 Flow 11）

```
LINE Webhook 收到 postback
 → 解析 wo_id + slot_index
 → 驗證 RSVP 未逾期 + 工單仍為 awaiting_customer_reschedule_confirm
 → UPDATE work_orders.scheduled_time
 → 回覆 LINE 新 Flex「已確認」
 → WS 推給技師（/realtime/work-orders/{id}）
 → 技師端 T11 頁面自動關閉
```

### 例外處理

| 情境 | 客戶看到 | 後端行為 |
|:---|:---|:---|
| RSVP 逾期（24h 未回）| 按鈕全 disabled + 「已過期」 | 工單 → `reschedule_expired`，通知技師 |
| 時段被他單搶先 | Toast「此時段剛被使用」+ 自動重發 Flex | 技師端重走 T11 |
| 客戶選 reject | LINE 自動進人工對話 | 工單保持、`support_agent` 跟進 |

### [DATA & API] T1.4 補

客戶端 RSVP 走 LINE Webhook：
```
POST /webhook (LINE Messaging API)
Body: { events: [{ type: postback, data: "rsvp&wo_id=...&slot_index=0" }] }
```

內部處理端點：
```
POST /internal/work-orders/{id}/reschedule/rsvp
Body: { slot_index: int, line_user_id: str, confirmed_at: ISO8601 }
```

### [ACCEPTANCE CRITERIA] T1.4

- [ ] LINE Flex 正確生成（1-3 個時段按鈕）
- [ ] 24h TTL 到期按鈕 disabled
- [ ] 客戶選擇後 scheduled_time 立即更新
- [ ] 技師 T11 接收 WS 自動關閉
- [ ] 時段被搶先偵測 → 自動重發 Flex
- [ ] reject 路徑進客服佇列
- [ ] 稽核 `work_order.reschedule_confirmed_by_customer` 正確產出

### 校對檢核表（T1.4）

- [ ] 24h TTL 是否合理？緊急工單需更短？
- [ ] LINE Flex 3 slot 按鈕 + reject 共 4 個是否超 LINE primary action 上限？
- [ ] 客戶 reject 後是否改排客服電話主動聯繫？
- [ ] 技師訊息 120 字是否足夠？
