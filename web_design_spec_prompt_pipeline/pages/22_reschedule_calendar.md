# Page-Level Prompt: 技師端 — 改期日曆

> IA 編號 **T11**。技師 / 客戶改期工單的日曆選擇 UI。與 Flow 5 延遲通知、Flow 11 客戶不在場、Flow 14 排班衝突整合。

---

## [PAGE META]

- **page_name**: 改期日曆 Reschedule Calendar
- **route_path**: `/my-orders/[id]/reschedule`（技師端） / 客戶走 LINE Flex RSVP（見 Flow 11）
- **page_type**: modal-style workflow
- **ia_pages**: T11
- **openapi_ops**: proposeReschedule, getTechnicianAvailability
- **asyncapi_ops**: subscribeWorkOrderUpdates
- **primary_goal**: 讓技師快速選擇新的工單時段，並觸發客戶確認流程
- **secondary_goal**: 顯示可用時段避免衝突、預覽客戶工作時間偏好
- **target_users**:
  - 主要：技師（當預計延遲 / 客戶不在場 / 自助改期）
  - 次要：客戶（透過 LINE Flex 看相同時段選項並 RSVP）
  - 次要：`dispatch_officer`（手動協助改期）
- **entry_point**:
  - T3 工單詳情「改期」按鈕
  - T7 延遲通知頁「直接改期」CTA
  - Flow 11 客戶不在場 → 技師返回後選擇「請客戶改期」
  - A37 派工人工介入「改期 + 通知客戶」按鈕
- **expected_time_on_page**: 30 秒 – 2 分鐘（技師端）

---

## [STRUCTURE: SECTIONS]

1. **wo_summary_header**
   - section_type: summary_header
   - section_purpose: 固定在頂部的工單摘要（客戶、地點、當前預約時間）

2. **customer_availability_hint**
   - section_type: info_card
   - section_purpose: 顯示客戶偏好時段（依歷史）與勿擾時段

3. **calendar_view**
   - section_type: calendar_picker
   - section_purpose: 7 日視圖，顯示技師當前排班 + 可用時段

4. **time_slot_picker**
   - section_type: time_slot_grid
   - section_purpose: 選定日期後，30 分鐘 granularity 時段網格

5. **conflict_warning**
   - section_type: alert_banner
   - section_purpose: 所選時段若觸發衝突（Flow 14）即時警示

6. **customer_notification_preview**
   - section_type: preview_card
   - section_purpose: 預覽將發送給客戶的 LINE Flex Message

7. **action_bar**
   - section_type: sticky_action
   - section_purpose: 底部「送出改期請求 / 取消」

8. **offline_queue_banner**
   - section_type: status_banner
   - section_purpose: 離線模式提示

---

## [SECTION COMPONENT SPEC]

### Section: wo_summary_header

- **layout**: 頂部 sticky，高度 96px，背景 surface.subtle
- **elements**:
  - wo_number: Heading H3 / 工單編號
  - customer_name: Body / 客戶姓名（去識別化）
  - address: Caption / 地址 + 距離
  - current_scheduled_time: Badge / 「原預約：2026-04-24 14:00」
  - close_btn: IconButton X / 返回 T3

### Section: customer_availability_hint

- **layout**: 次頂部，可折疊 info card
- **elements**:
  - preferred_hours: Chips / 「客戶偏好週間 09:00-18:00」（依 Profile + 歷史工單統計）
  - dnd_hours: Chips / 「勿擾 22:00-08:00」（紅標）
  - past_reschedule_count: Chip / 「此工單已改期 N 次」（N >= 2 時顯示警告色）
- **states**:
  - hidden if 無歷史資料
  - warning if N >= 3（建議人工協調）

### Section: calendar_view

- **layout**: 7 日水平 strip（手機）/ 月視圖（平板/桌面）
- **elements**:
  - date_cells: 每格顯示日期 + 可用時段數 + 當日 utilization bar
  - today_marker: 當日以粗框標記
  - holiday_badge: 假日顯示 icon（依客戶國/區設定）
  - navigation: 上一週 / 下一週 / 跳到指定日
- **states**:
  - selected: 藍底白字
  - unavailable: 灰色（技師請假日）
  - fully_booked: 斜線遮罩
- **copy_constraints**: 日期 Inter 14px，可用時段數 Caption

### Section: time_slot_picker

- **layout**: 所選日期下方，時段網格 4 欄 × N 列
- **elements**:
  - slot_chip: 每 30 分鐘一格（08:00 / 08:30 / 09:00 ...）
  - utilization_label: 每格標註「可用」/「緊鄰其他工單」/「不可用」
  - estimated_duration_highlight: 根據工單預估工時（例 1.5h）自動高亮連續可用時段
- **states**:
  - available: 白底
  - selected: 主色填滿
  - soft_conflict: 黃框 + warning icon（與鄰近工單太近）
  - hard_conflict: 禁止（灰底不可點）
  - customer_preferred: 淡綠背景提示

### Section: conflict_warning

- **layout**: 時段網格下方 alert banner
- **elements**:
  - alert_icon: severity icon
  - message: 依衝突類型：
    - soft: 「此時段前 45 分有另一工單，預計移動時間不足」
    - customer_dnd: 「此時段在客戶勿擾時段內」
    - holiday: 「此為假日，收費標準不同」
  - acknowledge_btn: 「了解並繼續」（`warning_acknowledged_at`）
  - change_btn: 「換個時段」
- **states**:
  - hidden if 無衝突
  - info / warning / critical 三色

### Section: customer_notification_preview

- **layout**: 可折疊區，預設展開
- **elements**:
  - flex_preview: LINE Flex Message 預覽（縮圖）
  - message_text: 可編輯的訊息開頭（預設「很抱歉需要調整時間，請問以下時段是否方便？」）
  - slot_options_count: 「將提供 3 個備選時段給客戶」（技師可選 1-3 個）
  - send_via: 單選「LINE Push」/「LINE + SMS」（SMS 需管理員授權）
- **states**:
  - editing: textarea focus
  - preview: 渲染 Flex

### Section: action_bar

- **layout**: 底部 sticky，高度 72px
- **elements**:
  - cancel_btn: Button Secondary / 「取消」→ 返回 T3
  - send_btn: Button Primary / 「送出改期請求」→ 送出並關閉
  - save_draft_btn: Button Tertiary / 「存草稿」（IndexedDB）
- **states**:
  - disabled if 無選擇時段 + 未 acknowledge 警告
  - sending: spinner + disabled
  - offline: 改為「離線暫存」

### Section: offline_queue_banner

- **layout**: 頂部（wo_summary_header 下方）
- **elements**:
  - icon: offline
  - text: 「已離線，改期請求將在連線後自動送出」
- **states**: 僅離線時顯示

---

## [INTERACTION & STATE FLOW]

### 進入流程

| 來源 | 帶入參數 | 初始狀態 |
|:---|:---|:---|
| T3 改期按鈕 | `work_order_id` | 今日日期選中、顯示客戶偏好 |
| T7 延遲通知 | `work_order_id, from=delay` | 預選「當日 + 原時間 + 延遲量」 |
| Flow 11 客戶不在場 | `work_order_id, from=no_show` | 隔日或客戶建議時段 |
| A37 派工介入 | `work_order_id, assisted_by=staff` | 顯示 staff 身份 banner |

### 核心互動

1. 載入 wo_summary + customer_availability_hint + calendar_view（預設今日）
2. 技師選日期 → time_slot_picker 載入當日可用時段
3. 選時段（可多選 1-3 個備選）→ conflict_warning 即時檢測
4. 編輯 customer_notification_preview 訊息
5. 點「送出」→ API 呼叫 → 客戶 LINE Flex 推送 → 工單狀態 → `awaiting_customer_reschedule_confirm`
6. 客戶端 LINE Flex 選擇 → webhook 回寫 → 工單新 scheduled_time + WS 推給技師

### Dirty State

| 動作 | 處置 |
|:---|:---|
| 選時段後關閉 | prompt「有未送出的改期，確定離開？」 |
| 存草稿按鈕 | IndexedDB store `reschedule_drafts` by work_order_id |
| 重進同工單 | 自動還原草稿（技師可決定用 or 重開）|

### 錯誤狀態

| 情境 | 行為 |
|:---|:---|
| 時段已被他工單佔（WS 推送 Flow 14 衝突）| 即時禁用該格 + Toast |
| 客戶已在另一流程（如爭議中）| 送出時 409 `CONFLICT` + 禁止改期 |
| 離線 | queue via Service Worker BG Sync |
| 客戶 LINE 封鎖公司帳號 | 送出後 fallback 為 SMS（若有授權） |

### 即時更新

訂閱 `/realtime/work-orders/{id}`：
- 客戶已 RSVP 新時段 → 技師端自動顯示「客戶已確認 X 時段」+ 關閉此頁

---

## [DATA & API]

### 查詢可用時段

```
GET /api/v1/technicians/me/availability?work_order_id={id}&date={YYYY-MM-DD}
Response 200: {
  slots: [
    {
      start: ISO8601, end: ISO8601,
      status: "available" | "soft_conflict" | "hard_conflict",
      conflict_reason: "buffer_insufficient" | "another_order" | "customer_dnd" | null
    }
  ],
  customer_preferences: {
    preferred_hours: ["09:00-18:00"],
    dnd_hours: ["22:00-08:00"]
  },
  past_reschedule_count: 1
}
```

### 送出改期請求

```
POST /api/v1/work-orders/{id}/reschedule
Headers: Idempotency-Key: <uuid>
Body: {
  proposed_slots: [
    { start: ISO8601, end: ISO8601 },
    ...  // 1-3 個
  ],
  message_to_customer: string,
  warning_acknowledged_at: ISO8601 | null,  // 若有 soft conflict
  send_via: "line" | "line_and_sms"
}
Response 200: WorkOrderEnvelope (status=awaiting_customer_reschedule_confirm)
Response 409: WORK_ORDER_CONFLICT (客戶另流程中)
Response 422: VALIDATION_ERROR (時段格式不合)
```

### 取消改期請求（送出後）

```
POST /api/v1/work-orders/{id}/reschedule/cancel
```

### 離線佇列

Service Worker 攔截 POST `/reschedule` 失敗 → IndexedDB queue：
```
{
  endpoint: "/api/v1/work-orders/{id}/reschedule",
  method: "POST",
  body: {...},
  idempotency_key: "...",
  queued_at: ISO8601
}
```

### WebSocket

訂閱 `/realtime/work-orders/{id}`：
- `work_order.reschedule_confirmed_by_customer` → 關閉此頁返回 T3
- `work_order.reschedule_rejected_by_customer` → 顯示拒絕理由 + 重選

---

## [EXCEPTION TO GLOBAL RULES]

- 同工單 24h 內改期次數 >= 3 → 禁止（`VALIDATION_ERROR`，顯示「請聯繫客服」）
- 客戶勿擾時段選擇需 acknowledge
- 假日時段自動附加費用提示（對齊 `E5x--work-order-flows-supplement.md §17`）
- 離線情境：UI 允許完整操作，實際送出等連線；最多 24h 未送達則提醒重新確認

---

## [ACCEPTANCE CRITERIA]

- [ ] 進入後 < 1 秒載入 7 日可用性
- [ ] 時段衝突即時反映（WS + 本地快取）
- [ ] 送出後客戶 LINE Flex < 5 秒抵達
- [ ] 客戶 RSVP 後技師頁面自動關閉（WS）
- [ ] 離線暫存且連線後自動補送（成功率 > 99%）
- [ ] 假日 / 勿擾時段有明確視覺警示
- [ ] 3 次改期限制有效執行
- [ ] 支援手機 / 平板 / 桌面三種 viewport

---

## 導航與狀態 (Navigation & State)

對齊 `docs/02-design/E5x--frontend-navigation-matrix.md §1.3`：

- **Upstream**: T3 改期按鈕、T7 延遲通知頁、Flow 11 返回後、A37 派工介入
- **Downstream**: T3 工單詳情（送出後返回）、客戶 LINE Flex（外部流程）
- **State Persistence**: 草稿 via IndexedDB（長期編輯型）；選擇 via URL query（日期）
- **Error Navigation**: 離線排入 queue、409 停留並提示
- **Deep Link**: supported（技師 PWA 直達）
- **Multi-tab Sync**: WS + BroadcastChannel（同工單其他 tab 開啟時同步關閉）

---

## 校對檢核表

- [ ] 30 分鐘 granularity 是否足夠？某些工項可能需要更細粒度
- [ ] 客戶偏好時段的計算邏輯（歷史統計 vs Profile 設定）是否需單獨定義？
- [ ] 3 個備選時段是否為業界慣例？LINE Flex 最多支援幾個按鈕？
- [ ] SMS fallback 需管理員授權 — 授權流程在哪定義？
- [ ] 24h 3 次改期限制是否過嚴？緊急情況如何處理？
- [ ] 假日附加費用提示的金額來源是否對齊 pricing rules？
- [ ] 客戶端 LINE Flex RSVP 流程是否需要獨立頁面 spec？（目前歸 Flow 11）
